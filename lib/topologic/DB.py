#!/usr/bin/env python3

"""DuckDB-backed storage for a single trained topic model.

Each deployed model has its own `.duckdb` file (typically alongside the
model's webapp directory). Tables live at well-known names inside the file
(`words`, `docs`, `topics`); no shared database server, no permission setup.

`DBHandler` is the write-side class used during training.
`DBSearch`   is the read-side class used by the API at query time.
"""

import json
import re
from collections import Counter, defaultdict
from itertools import repeat
from math import log

import duckdb
import numpy as np
from multiprocess import Pool, cpu_count
from sklearn.metrics import pairwise_distances
from topologic import year_normalizer
from tqdm import tqdm, trange

VALID_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

# Shared saturation/lightness for the per-topic palette. Matches what looks
# readable on both white card backgrounds and as a thin legend swatch.
_PALETTE_SATURATION = 0.62
_PALETTE_LIGHTNESS = 0.52


def _topic_color(topic_id, nb_topics):
    """Deterministic color for a topic, stable across runs and consistent across
    every view (TimeView, Topic detail, landscape heatmap, sankey, topical read).

    Uses a golden-ratio hue step so adjacent topic ids land far apart on the color
    wheel. Returns a hex string like "#4f9de2".
    """
    golden = 0.6180339887498949
    hue = (topic_id * golden) % 1.0
    import colorsys
    r, g, b = colorsys.hls_to_rgb(hue, _PALETTE_LIGHTNESS, _PALETTE_SATURATION)
    return "#{:02x}{:02x}{:02x}".format(
        round(r * 255), round(g * 255), round(b * 255)
    )

# Columns stored as JSON — we json.loads them when wrapping rows as dicts.
_JSON_COLUMNS = {
    "docs",
    "topic_evolution",
    "topic_distribution",
    "topic_similarity",
    "vector_similarity",
    "word_list",
    "word_distribution",
    "distribution_across_topics",
    "similar_words_by_topic",
    "similar_words_by_cooc",
    "chunks",
    "distinctive_topics",
    "peers",
    "trajectory",
    "exemplars",
    "anomalies",
}


def _check_identifier(name):
    """Validate that a name is safe to use as a SQL identifier."""
    if not VALID_IDENTIFIER_RE.match(name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")


def _row_to_dict(cursor, row):
    if row is None:
        return None
    cols = [d[0] for d in cursor.description]
    out = {}
    for col, val in zip(cols, row):
        if col in _JSON_COLUMNS and isinstance(val, str):
            out[col] = json.loads(val)
        else:
            out[col] = val
    return out


def _rows_to_dicts(cursor, rows):
    cols = [d[0] for d in cursor.description]
    results = []
    for row in rows:
        result = {}
        for col, val in zip(cols, row):
            if col in _JSON_COLUMNS and isinstance(val, str):
                result[col] = json.loads(val)
            else:
                result[col] = val
        results.append(result)
    return results


def _smooth(series, window):
    """Centered moving average. Returns a list of the same length as the input."""
    if window <= 1 or len(series) <= 1:
        return list(series)
    arr = np.asarray(series, dtype=float)
    kernel = np.ones(window) / window
    return np.convolve(arr, kernel, mode="same").tolist()


def _pearson(a, b):
    """Pearson correlation coefficient; returns 0.0 when either series is constant."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    a_std = a.std()
    b_std = b.std()
    if a_std == 0 or b_std == 0:
        return 0.0
    return float(((a - a.mean()) * (b - b.mean())).mean() / (a_std * b_std))


def _smoothing_window(interval):
    """Number of buckets to use for the centered rolling mean, given the
    display interval. Derived from the user-visible rule:

        side_years = interval / divisor,    divisor = 2 + floor(log10(interval))
        total_span = 2 * side_years + interval    (one center bucket + both sides)

    interval=1 is a special case with side_years=1 (divisor would be 2 → side=0).
    side_years is capped at 20 to stop very coarse intervals from smoothing
    away all signal.
    """
    import math
    if interval <= 1:
        return 3
    divisor = 2 + int(math.log10(interval))
    side_years = min(20, interval // divisor)
    total_span = 2 * side_years + interval
    return max(1, round(total_span / interval))


def _rebucket(evolution, interval_years):
    """Aggregate a per-year evolution series into `interval_years`-wide buckets,
    aligned to multiples of `interval_years` (e.g., interval=10 → buckets start
    at 1770, 1780, 1790, not 1774, 1784).

    `evolution` is the stored dict {"labels": [years...], "data": [vals...]}.
    Returns a new dict with the same shape, downsampled by averaging.
    `interval_years=1` is a no-op.
    """
    if interval_years <= 1:
        return evolution
    labels = evolution.get("labels") or []
    data = evolution.get("data") or []
    if not labels:
        return evolution
    first = labels[0]
    last = labels[-1]
    # Index labels by year for fast lookup.
    by_year = dict(zip(labels, data))
    buckets_labels = []
    buckets_data = []
    bucket_start = (first // interval_years) * interval_years
    while bucket_start <= last:
        bucket_end = bucket_start + interval_years  # exclusive
        vals = [by_year[y] for y in range(bucket_start, bucket_end) if y in by_year]
        if vals:
            buckets_labels.append(bucket_start)
            buckets_data.append(round(sum(vals) / len(vals), 4))
        bucket_start = bucket_end
    return {"labels": buckets_labels, "data": buckets_data}


OBJECT_LEVELS = {"doc": 1, "div1": 2, "div2": 3, "para": 4, "sent": 5}


class DBHandler:
    """Write-side connection used during training."""

    db = None
    model = None
    metadata = None
    db_path = None
    docs_per_year = None
    field_names = None
    time_series_enabled = True

    def __init__(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *args):
        cls = type(self)
        if cls.db is not None:
            if exc_type is None:
                cls.db.commit()
            cls.db.close()
            cls.db = None

    @classmethod
    def set_class_attributes(
        cls,
        db_path,
        model,
        corpus,
        min_year,
        max_year,
        topics_over_time_interval,
        time_series_enabled=True,
    ):
        cls.db = duckdb.connect(db_path)
        cls.db_path = db_path
        cls.model = model
        cls.metadata = corpus.metadata
        field_names = set()
        for doc_metadata in cls.metadata.values():
            field_names.update(doc_metadata.keys())
        # Validate early so an invalid field name fails the training run, not
        # some later SQL execution.
        for f in field_names:
            _check_identifier(f)
        cls.field_names = list(field_names)
        cls.time_series_enabled = time_series_enabled
        if not time_series_enabled:
            cls.year_label_map = {}
            cls.docs_per_year = Counter()
            return cls()
        if topics_over_time_interval != 1:
            label_map = {
                year: year_normalizer(year, topics_over_time_interval)
                for year in range(min_year, max_year + 1)
            }
        else:
            label_map = {year: year for year in range(min_year, max_year + 1)}
        cls.year_label_map = label_map
        docs_per_year = Counter()
        for doc in range(cls.model.corpus.size):
            try:
                docs_per_year[label_map[int(cls.metadata[doc]["year"])]] += 1
            except (KeyError, ValueError):
                pass
        cls.docs_per_year = docs_per_year
        return cls()

    @classmethod
    def save_words(cls):
        cls.db.execute("DROP TABLE IF EXISTS words")
        cls.db.execute(
            "CREATE TABLE words(word_id INTEGER, word VARCHAR, "
            "distribution_across_topics JSON, docs JSON, "
            "similar_words_by_topic JSON, similar_words_by_cooc JSON)"
        )

        # Compute word similarity based on topic distributions
        print("Compute word similarity by distribution over topics...", flush=True)
        word_similarities_by_topic = pairwise_distances(
            cls.model.topic_word_matrix.transpose(), metric="cosine", n_jobs=-1
        )

        # Compute word similarity based on document co-occurrence
        print("Compute word similarity by document co-occurrence...", flush=True)
        word_similarities_by_cooc = pairwise_distances(
            cls.model.corpus.sklearn_vector_space.transpose(),
            metric="cosine",
            n_jobs=-1,
        )
        feature_names = cls.model.corpus.feature_names
        N = cls.model.corpus.size

        def _rank_similar(sim_array):
            order = np.argsort(sim_array)[::-1]
            return [{"word": feature_names[i], "weight": float(sim_array[i])} for i in order]

        # Column-oriented view: each column is one word's (doc_id, weight) list
        # already in sparse form. Avoids densifying row by row.
        csc = cls.model.corpus.sklearn_vector_space.tocsc()
        topic_word_dense = cls.model.topic_word_matrix.toarray()  # topics × words, one densify
        topic_ids = list(range(topic_word_dense.shape[0]))

        batch = []
        for word_id in tqdm(
            range(csc.shape[1]),
            leave=False,
            desc="Generating TF-IDF scores for all tokens",
        ):
            start, end = csc.indptr[word_id], csc.indptr[word_id + 1]
            doc_ids = csc.indices[start:end]
            weights = csc.data[start:end]
            mask = weights > 0
            if not mask.any():
                continue
            doc_ids = doc_ids[mask]
            weights = weights[mask]

            idf = log(N / len(doc_ids))
            # Sublinear TF: 1 + log(tf). Dampens the effect of high raw counts
            # so that a word appearing 100× doesn't dominate one appearing 10×.
            scores = (1.0 + np.log(weights)) * idf
            order = np.argsort(-scores, kind="stable")
            sorted_docs = [
                (int(doc_ids[i]), float(scores[i])) for i in order
            ]

            topic_weights = [float(w) for w in topic_word_dense[:, word_id]]

            batch.append([
                int(word_id),
                feature_names[word_id],
                json.dumps({"labels": topic_ids, "data": topic_weights}),
                json.dumps(sorted_docs),
                json.dumps(_rank_similar(1.0 - word_similarities_by_topic[word_id])),
                json.dumps(_rank_similar(1.0 - word_similarities_by_cooc[word_id])),
            ])
            if len(batch) >= 1000:
                cls.db.executemany(
                    "INSERT INTO words (word_id, word, distribution_across_topics, docs, "
                    "similar_words_by_topic, similar_words_by_cooc) VALUES (?, ?, ?, ?, ?, ?)",
                    batch,
                )
                batch = []
        if batch:
            cls.db.executemany(
                "INSERT INTO words (word_id, word, distribution_across_topics, docs, "
                "similar_words_by_topic, similar_words_by_cooc) VALUES (?, ?, ?, ?, ?, ?)",
                batch,
            )
        cls.db.execute("CREATE INDEX word_id_index ON words(word_id)")
        cls.db.execute("CREATE INDEX word_index ON words(word)")

    @classmethod
    def save_docs(cls):
        fixed_col_defs = (
            "doc_id INTEGER",
            "topic_distribution JSON",
            "topic_similarity JSON",
            "vector_similarity JSON",
            "word_list JSON",
        )
        metadata_col_defs = tuple(
            f'"{f}" INTEGER' if f == "year" else f'"{f}" VARCHAR'
            for f in cls.field_names
        )
        all_cols = ("doc_id", "topic_distribution", "topic_similarity",
                    "vector_similarity", "word_list", *cls.field_names)
        cls.db.execute("DROP TABLE IF EXISTS docs")
        cls.db.execute(
            f"CREATE TABLE docs({', '.join(fixed_col_defs + metadata_col_defs)})"
        )
        col_list = ", ".join(f'"{c}"' for c in all_cols)
        placeholders = ", ".join("?" for _ in all_cols)
        insert_query = f"INSERT INTO docs ({col_list}) VALUES ({placeholders})"
        with tqdm(total=cls.model.corpus.size, leave=False, desc="Generating doc stats") as pbar:
            with Pool(cpu_count() - 1) as pool:
                for values in pool.imap_unordered(cls.compute_doc, range(cls.model.corpus.size)):
                    cls.db.execute(insert_query, list(values))
                    pbar.update()
        cls.db.execute("CREATE INDEX doc_id_index ON docs(doc_id)")
        for field in cls.field_names:
            cls.db.execute(f'CREATE INDEX "{field}_index" ON docs("{field}")')

    @classmethod
    def compute_doc(cls, doc_id):
        distribution = cls.model.topic_distribution_for_document(doc_id)
        topic_distribution = json.dumps({
            "labels": list(range(len(distribution))),
            "data": [float(w) for w in distribution],
        })

        topic_similarity = json.dumps([
            (int(other), round(float(score), 3))
            for other, score in cls.model.corpus.similar_docs_by_topic_distribution(doc_id, 20, cls.model)
        ])
        vector_similarity = json.dumps([
            (int(other), round(float(score), 3))
            for other, score in cls.model.corpus.similar_docs_by_vector(doc_id, 20)
        ])

        vector = cls.model.corpus.sklearn_vector_space[doc_id].toarray()[0]
        nz_ids = np.flatnonzero(vector)
        ordered = nz_ids[np.argsort(vector[nz_ids])[::-1]]
        word_list = json.dumps([
            (cls.model.corpus.feature_names[i], float(vector[i]), int(i))
            for i in ordered
        ])

        doc_metadata = cls.metadata[doc_id]
        field_values = []
        for field in cls.field_names:
            val = doc_metadata.get(field, "")
            if field == "year" and not val:
                val = 0
            field_values.append(val)
        return (doc_id, topic_distribution, topic_similarity, vector_similarity, word_list, *field_values)


    @classmethod
    def save_doc_chunks(cls, inference_databases, top_k=8, max_chunk_size=None):
        """Structural chunking + HTML rendering for the topical-reading view.

        Each doc's `words_and_philo_ids/*.lz4` JSONL records are grouped by
        paragraph (the 5-tuple `position[:5]`, which is the paragraph level in
        PhiloLogic's hierarchy), then grouped into chunks of at most
        `max_chunk_size` preprocessed tokens. Paragraphs with no surviving
        preprocessed tokens (fully-stopworded captions, headers) contribute
        nothing to the count and so fold into a neighbour rather than standing
        alone.

        For each chunk we:
          1. Render HTML by calling `philologic.runtime.get_text.get_text_obj`
             on each constituent paragraph's philo_id and concatenating. This
             matches exactly what PhiloLogic's navigation report would render
             — formatting, italics, page breaks, notes — only pre-baked.
          2. Compute a top-K topic distribution by folding in against the
             trained topic-word matrix, using a sliding window that includes
             the previous and next chunks' tokens for θ stability.

        Chunking is the same `group_by_counts` used to build the model's own
        training and embedding chunks, so the passages a reader sees are the
        passages the model scored — not a second, parallel estimate that can
        disagree with the document it describes.

        Results are written to a new `chunks JSON` column on the `docs` table
        as `[{paragraph_philo_ids: [...], html: "...", top_topics: [[id, w], ...],
        tokens: N}, ...]`. Query time is a single SELECT — no HTTP to
        PhiloLogic, no philologic runtime import on the API server.

        `inference_databases`: per-db config from training, shaped
        `{db_name: {"db_path": ..., "text_object_level": ..., ...}}`.
        """
        import json as _json
        import os as _os
        import lz4.frame

        from topologic.chunking import assign_preproc_tokens, group_by_counts

        # Preprocessed tokens, not raw words: max_chunk_size is stated in raw
        # words, and the two differ by roughly 5x on real corpora. Scale so a
        # reading chunk covers about as much text as an embedding chunk.
        chunk_cap = max(int((max_chunk_size or 500) / 5), 20)
        from collections import namedtuple
        from philologic.runtime.DB import DB as PhiloDB
        from philologic.runtime.get_text import get_text_obj
        from text_preprocessing.spacy_helpers import Tokens

        _PhiloConfig = namedtuple("PhiloConfig", [
            "db_path", "page_images_url_root", "page_image_extension",
            "page_external_page_images",
        ])
        _PhiloRequest = namedtuple("PhiloRequest", [
            "byte", "start_byte", "end_byte", "passages",
        ])
        empty_request = _PhiloRequest("", "", "", [])

        vectorizer = cls.model.corpus.vectorizer
        preproc_text_root = cls.model.corpus.texts_to_vectorize.text_path

        # Caches shared across docs for the life of save_doc_chunks —
        # several training docs typically share the same .lz4 file (sub-doc
        # training levels) and the same PhiloLogic DB handle.
        lz4_cache = {}
        philo_db_cache = {}
        philo_config_cache = {}

        def _get_philo_db(db_name, db_path):
            if db_name in philo_db_cache:
                return philo_db_cache[db_name]
            pdb = PhiloDB(_os.path.join(db_path, "data"), width=7)
            philo_db_cache[db_name] = pdb
            philo_config_cache[db_name] = _PhiloConfig(db_path, "", "", "")
            return pdb

        def _load_lz4(path):
            if path in lz4_cache:
                return lz4_cache[path]
            tokens = []
            try:
                with lz4.frame.open(path, "rb") as fh:
                    for line in fh:
                        line = line.decode("utf-8", errors="replace").strip()
                        if not line:
                            continue
                        try:
                            rec = _json.loads(line)
                        except Exception:
                            continue
                        sb = rec.get("start_byte", 0)
                        eb = rec.get("end_byte", 0)
                        if eb <= sb:
                            continue
                        pos = (rec.get("position") or "").split()
                        tokens.append((
                            sb, eb,
                            rec.get("token", ""),
                            pos,
                            rec.get("philo_type", "word"),
                        ))
            except FileNotFoundError:
                tokens = None
            lz4_cache[path] = tokens
            return tokens

        cls.db.execute("ALTER TABLE docs ADD COLUMN chunks JSON")

        written = 0
        for doc_id, meta in tqdm(
            cls.metadata.items(), total=len(cls.metadata),
            leave=False, desc="Chunking + rendering HTML",
        ):
            philo_db_name = meta.get("philo_db")
            if not philo_db_name or philo_db_name not in inference_databases:
                continue
            db_config = inference_databases[philo_db_name]
            db_path = db_config["db_path"]
            level = db_config["text_object_level"]
            level_depth = OBJECT_LEVELS.get(level)
            if level_depth is None:
                continue

            philo_id_field = f"philo_{level}_id"
            raw_pid = str(meta.get(philo_id_field, "")).strip()
            if not raw_pid:
                continue
            pid_parts = raw_pid.split()[:level_depth]
            if not pid_parts:
                continue

            lz4_path = _os.path.join(
                db_path, "data", "words_and_philo_ids", f"{pid_parts[0]}.lz4"
            )
            all_tokens = _load_lz4(lz4_path)
            if not all_tokens:
                continue

            # Tokens under this training-level object, sorted by byte offset.
            level_tokens = [
                t for t in all_tokens if t[3][:level_depth] == pid_parts
            ]
            if not level_tokens:
                continue
            level_tokens.sort(key=lambda t: t[0])

            # Group by paragraph (position[:5] is the para level in PhiloLogic).
            paragraphs = []
            cur_key = None
            cur = []

            def _emit(key, toks):
                paragraphs.append({
                    "philo_id": key,
                    "tokens": toks,
                    "start_byte": toks[0][0],
                    "end_byte": max(t[1] for t in toks),
                })

            for sb, eb, tok, pos, ptype in level_tokens:
                key = tuple(pos[:5]) if len(pos) >= 5 else tuple(pos)
                if key != cur_key:
                    if cur:
                        _emit(cur_key, cur)
                    cur_key = key
                    cur = []
                cur.append((sb, eb, tok, ptype))
            if cur:
                _emit(cur_key, cur)
            if not paragraphs:
                continue

            # Load the preprocessor's own output for this doc. Each
            # PreprocessorToken keeps `ext["start_byte"]` from the source, so
            # we can assign it to its paragraph by byte range, then count and
            # fold-in on TRUE preprocessed (stemmed / stopword-filtered)
            # tokens — exactly what the vectorizer was fit on.
            pkl_path = _os.path.join(
                preproc_text_root, philo_db_name, "tokens", f"{int(doc_id)}.pkl"
            )
            try:
                preproc_tokens_obj = Tokens.load(pkl_path)
            except FileNotFoundError:
                preproc_tokens_obj = None

            para_preproc_tokens = assign_preproc_tokens(paragraphs, preproc_tokens_obj)

            # Build chunks. Count is preprocessed tokens per paragraph (what
            # actually contributes to the vectorizer's BOW). Paragraphs with
            # zero preproc tokens (fully-stopworded captions, etc.) naturally
            # fold forward — they don't advance the counter on their own.
            chunks_para_indices = group_by_counts(
                [len(t) for t in para_preproc_tokens], chunk_cap
            )

            # Materialize chunks as (paragraph_list, preproc_token_list) pairs.
            chunks = [
                [paragraphs[i] for i in idx_group]
                for idx_group in chunks_para_indices
            ]
            per_chunk_preproc = [
                [tok for i in idx_group for tok in para_preproc_tokens[i]]
                for idx_group in chunks_para_indices
            ]

            # Per-chunk preprocessed token strings for fold-in. Since these
            # are the exact tokens the vectorizer was fit on, transform hits
            # the vocabulary cleanly (no silent misses from inflected forms).
            per_chunk_text = [" ".join(toks) for toks in per_chunk_preproc]

            # Sliding inference window: each chunk infers from prev + self + next.
            inference_texts = []
            for i in range(len(chunks)):
                parts = []
                if i > 0:
                    parts.append(per_chunk_text[i - 1])
                parts.append(per_chunk_text[i])
                if i < len(chunks) - 1:
                    parts.append(per_chunk_text[i + 1])
                inference_texts.append(" ".join(parts))

            bow = vectorizer.transform(inference_texts)  # n_chunks × vocab
            # Not `bow @ beta.T`: that is dominated by topic row mass rather
            # than passage content. See TopicModel.fold_in.
            theta_norm = cls.model.fold_in(bow)

            # Render HTML by asking PhiloLogic to format each paragraph
            # object; concatenate for a chunk that spans multiple paragraphs.
            philo_db = _get_philo_db(philo_db_name, db_path)
            philo_config = philo_config_cache[philo_db_name]
            word_regex = philo_db.locals["token_regex"]

            chunks_out = []
            for i, chunk_paras in enumerate(chunks):
                theta = theta_norm[i]
                if theta.sum() == 0:
                    top = []
                else:
                    top_ids = np.argsort(-theta)[:top_k]
                    top = [
                        [int(t), round(float(theta[t]), 4)]
                        for t in top_ids if theta[t] > 0
                    ]
                para_ids = []
                html_parts = []
                for p in chunk_paras:
                    pid = " ".join(str(v) for v in p["philo_id"])
                    para_ids.append(pid)
                    try:
                        obj = philo_db[pid]
                        rendered, _ = get_text_obj(
                            obj, philo_config, empty_request, word_regex,
                        )
                        if isinstance(rendered, bytes):
                            rendered = rendered.decode("utf-8", errors="replace")
                        html_parts.append(rendered)
                    except Exception:
                        # A missing or malformed paragraph shouldn't take down
                        # the whole doc — skip and keep going.
                        pass
                chunks_out.append({
                    "paragraph_philo_ids": para_ids,
                    "html": "".join(html_parts),
                    "top_topics": top,
                    "tokens": len(per_chunk_preproc[i]),
                })

            cls.db.execute(
                "UPDATE docs SET chunks = ? WHERE doc_id = ?",
                [_json.dumps(chunks_out), int(doc_id)],
            )
            written += 1

        print(
            f"Built structural chunks + HTML for {written}/{len(cls.metadata)} docs.",
            flush=True,
        )

    @classmethod
    def save_metadata_profiles(
        cls,
        min_docs=2,
        min_avg_docs_per_value=4.0,
        top_distinctive=10,
        top_trajectory=6,
        top_peers=5,
        top_exemplars=5,
        top_anomalies=5,
    ):
        """Precompute a rich per-metadata-value profile used by the metadata view.

        For every string metadata field and every value with at least `min_docs`
        documents, writes one row to the `metadata_profiles` table carrying:

        - `topic_distribution`: the value's centroid (mean topic vector across
          its docs). Full vector — frontend slices what it needs.
        - `distinctive_topics`: top-K topics by lift (value's weight ÷ corpus
          mean), filtered to topics with non-trivial weight so lift ratios
          computed off tiny denominators don't dominate.
        - `focus_score`: 1 − normalized entropy of the centroid. 1 = all mass on
          one topic (specialist), 0 = flat distribution (generalist).
        - `peers`: top-N closest other values in the same field by cosine on the
          centroid. Each carries the peer's top-3 topics for quick scan.
        - `trajectory`: per-year mean topic weight for this value's top-K
          topics, alongside the corpus baseline for the same years and topics.
        - `exemplars`: per top topic, a pointer `(doc_id, chunk_index, weight)`
          to the chunk in this value's works with the highest weight on that
          topic. API materializes the HTML + citation at query time.
        - `anomalies`: this value's own documents ranked by L2 distance from
          the centroid; the outliers are the "unusual works."

        All math uses the topic distributions already stored on `docs`, so the
        pass is purely post-processing — no retraining, no text rereading.
        """
        nb_topics = int(cls.model.nb_topics)

        cls.db.execute("DROP TABLE IF EXISTS metadata_profiles")
        cls.db.execute(
            "CREATE TABLE metadata_profiles("
            "field_name VARCHAR, field_value VARCHAR, doc_count INTEGER, "
            "focus_score DOUBLE, topic_distribution JSON, "
            "distinctive_topics JSON, peers JSON, trajectory JSON, "
            "exemplars JSON, anomalies JSON)"
        )

        # Pull dense (doc_id × topic) matrix once. With typical corpora
        # (~tens of thousands of docs × a few hundred topics) this is modest
        # memory and lets everything downstream be numpy math.
        doc_rows = cls.db.execute(
            "SELECT doc_id, topic_distribution FROM docs ORDER BY doc_id"
        ).fetchall()
        doc_ids = np.array([int(r[0]) for r in doc_rows], dtype=np.int64)
        id_to_row = {int(d): i for i, d in enumerate(doc_ids)}
        dist = np.zeros((len(doc_rows), nb_topics), dtype=np.float32)
        for i, (_, td_json) in enumerate(doc_rows):
            data = json.loads(td_json)["data"]
            # Tolerate ragged/shorter vectors defensively; zero-pad.
            n = min(len(data), nb_topics)
            dist[i, :n] = data[:n]

        # Corpus mean — denominator for the lift computation. Guard against
        # a topic that genuinely has zero corpus mass (would otherwise divide
        # by zero) with a small epsilon relative to the typical mass.
        corpus_mean = dist.mean(axis=0)
        eps_corpus = max(float(corpus_mean.mean()) * 1e-3, 1e-9)

        # Per-year corpus mean, used as the trajectory baseline overlay.
        # Missing year → doc ignored in the baseline (but still profiled).
        doc_year = [None] * len(doc_rows)
        year_to_rows = defaultdict(list)
        # Load year column in one shot if present on docs.
        has_year = cls.db.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'docs' AND column_name = 'year' LIMIT 1"
        ).fetchone() is not None
        if has_year:
            yr_rows = cls.db.execute("SELECT doc_id, year FROM docs").fetchall()
            for did, y in yr_rows:
                if y is None:
                    continue
                try:
                    yi = int(y)
                except (TypeError, ValueError):
                    continue
                if yi <= 0:
                    continue
                ri = id_to_row.get(int(did))
                if ri is None:
                    continue
                doc_year[ri] = yi
                year_to_rows[yi].append(ri)
        corpus_year_mean = {
            y: dist[rows_for_y].mean(axis=0)
            for y, rows_for_y in year_to_rows.items()
        }

        # Pull chunks' top_topics (not the HTML — we don't need it at build
        # time) for every doc once so we can scan them per value cheaply.
        # Each entry: doc_id -> list of (chunk_index, [(tid, weight), ...]).
        doc_chunk_index = {}
        chunk_rows = cls.db.execute(
            "SELECT doc_id, chunks FROM docs WHERE chunks IS NOT NULL"
        ).fetchall()
        for did, ch_json in chunk_rows:
            if not ch_json:
                continue
            try:
                chunks = json.loads(ch_json)
            except (TypeError, ValueError):
                continue
            if not chunks:
                continue
            doc_chunk_index[int(did)] = [
                (i, c.get("top_topics") or [])
                for i, c in enumerate(chunks)
            ]

        # Candidate profile fields: strings only, excluding year and known
        # PhiloLogic/infrastructure columns that carry IDs, bytes, filenames,
        # or navigation pointers — nothing a human would browse by. Anything
        # not on this blacklist is kept (opt-out, so corpus-specific metadata
        # added later flows through without config changes).
        blacklist = {
            "year",
            # PhiloLogic internal identifiers and navigation
            "philo_id", "philo_doc_id", "philo_div1_id", "philo_div2_id",
            "philo_div3_id", "philo_name", "philo_db", "philo_type",
            "philo_seq", "parent", "prev", "next",
            # File / byte offsets and counts
            "filename", "parsed_filename", "start_byte", "end_byte",
            "word_count", "page", "id", "head", "type",
            # Date fields — covered by the time-series view via `year`; a
            # separate Explorer browse would duplicate that without extra signal.
            "pub_date", "create_date",
        }
        profile_fields = [f for f in cls.field_names if f not in blacklist]

        insert_sql = (
            "INSERT INTO metadata_profiles (field_name, field_value, doc_count, "
            "focus_score, topic_distribution, distinctive_topics, peers, "
            "trajectory, exemplars, anomalies) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )

        log_nb_topics = log(nb_topics) if nb_topics > 1 else 1.0

        for field in profile_fields:
            # Group doc row indices by field value. Skip null/empty.
            rows = cls.db.execute(
                f'SELECT doc_id, "{field}" FROM docs'
            ).fetchall()
            groups = defaultdict(list)
            for did, val in rows:
                if val is None or val == "":
                    continue
                ri = id_to_row.get(int(did))
                if ri is None:
                    continue
                groups[val].append(ri)

            # Only values with enough docs get a profile; centroid of a single
            # doc is just that doc and the peer graph collapses.
            eligible = {v: r for v, r in groups.items() if len(r) >= min_docs}
            if not eligible:
                continue

            # Near-identifier guard: fields like `title` or `keywords` have
            # values that are nearly unique per doc — they pass the min_docs
            # filter only on a handful of accidental collisions (reprints,
            # shared keyword sets). Avg docs-per-profiled-value separates those
            # from real categorical fields (author, genre, publisher…). Below
            # the floor, the field has no browsing value and shouldn't appear
            # in the Metadata Explorer.
            covered = sum(len(r) for r in eligible.values())
            avg_docs_per_value = covered / len(eligible)
            if avg_docs_per_value < min_avg_docs_per_value:
                continue

            values_list = list(eligible.keys())
            centroids = np.stack([
                dist[eligible[v]].mean(axis=0) for v in values_list
            ])

            # Cosine similarity across all eligible values in this field
            # (one matmul). Self-similarity is masked out below.
            norms = np.linalg.norm(centroids, axis=1, keepdims=True)
            centroids_unit = centroids / np.maximum(norms, 1e-12)
            sim = centroids_unit @ centroids_unit.T

            batch = []
            for i, value in enumerate(values_list):
                centroid = centroids[i]
                row_ids = eligible[value]

                # Topic ranking for this value (used for trajectory, exemplars).
                order = np.argsort(-centroid)
                top_traj_ids = [int(t) for t in order[:top_trajectory]]
                top_exemplar_ids = [int(t) for t in order[:top_exemplars]]

                # Distinctive = lift vs corpus. Filter to topics with enough
                # weight that lift isn't noise from a near-zero denominator.
                weight_cutoff = max(float(centroid.mean()) * 0.5, 1e-4)
                lift = centroid / np.maximum(corpus_mean, eps_corpus)
                cand = [
                    (int(t), float(centroid[t]), float(lift[t]))
                    for t in range(nb_topics)
                    if centroid[t] >= weight_cutoff
                ]
                cand.sort(key=lambda x: -x[2])
                distinctive = [
                    [t, round(w, 6), round(l, 4)]
                    for t, w, l in cand[:top_distinctive]
                ]

                # Focus: 1 − H(centroid)/log(K). Centroid is already a prob-
                # like vector (mean of per-doc distributions that each sum to
                # ~1), so renormalize softly for robustness.
                p = centroid / max(float(centroid.sum()), 1e-12)
                nz = p > 0
                ent = float(-np.sum(p[nz] * np.log(p[nz])))
                focus = 1.0 - ent / log_nb_topics if log_nb_topics > 0 else 0.0
                focus = max(0.0, min(1.0, focus))

                # Peers: top-N by cosine in the same field, excluding self.
                sim_row = sim[i].copy()
                sim_row[i] = -np.inf
                peer_idx = np.argsort(-sim_row)[:top_peers]
                peers = []
                for pi in peer_idx:
                    if not np.isfinite(sim_row[pi]):
                        continue
                    pvec = centroids[pi]
                    top3 = np.argsort(-pvec)[:3].tolist()
                    peers.append([
                        values_list[pi],
                        round(float(sim_row[pi]), 4),
                        [int(t) for t in top3],
                    ])

                # Trajectory: for each year this value has docs in, mean topic
                # weight across those docs. Baseline: corpus mean for that year.
                years_map = defaultdict(list)
                for ri in row_ids:
                    y = doc_year[ri]
                    if y is not None:
                        years_map[y].append(ri)
                sorted_years = sorted(years_map.keys())
                traj_topics = {}
                traj_baseline = {}
                for tid in top_traj_ids:
                    series = []
                    baseline = []
                    for y in sorted_years:
                        year_mean = dist[years_map[y]].mean(axis=0)
                        series.append(round(float(year_mean[tid]), 6))
                        cb = corpus_year_mean.get(y)
                        baseline.append(
                            round(float(cb[tid]), 6) if cb is not None else 0.0
                        )
                    traj_topics[str(tid)] = series
                    traj_baseline[str(tid)] = baseline
                trajectory = {
                    "years": sorted_years,
                    "topics": traj_topics,
                    "baseline": traj_baseline,
                }

                # Exemplars: scan this value's chunks once, track the best
                # (max weight) chunk for each of the top exemplar topics.
                exemplars = {}
                best = {tid: None for tid in top_exemplar_ids}
                target = set(top_exemplar_ids)
                for ri in row_ids:
                    did = int(doc_ids[ri])
                    chunks = doc_chunk_index.get(did)
                    if not chunks:
                        continue
                    for ci, top_topics in chunks:
                        for tid, w in top_topics:
                            tid_i = int(tid)
                            if tid_i not in target:
                                continue
                            w_f = float(w)
                            cur = best[tid_i]
                            if cur is None or w_f > cur[2]:
                                best[tid_i] = (did, ci, w_f)
                for tid, pick in best.items():
                    if pick is None:
                        continue
                    exemplars[str(tid)] = {
                        "doc_id": int(pick[0]),
                        "chunk_index": int(pick[1]),
                        "weight": round(float(pick[2]), 4),
                    }

                # Anomalies: this value's docs, ranked by L2 distance to centroid.
                doc_dist = np.linalg.norm(dist[row_ids] - centroid, axis=1)
                worst = np.argsort(-doc_dist)[:top_anomalies]
                anomalies = [
                    {
                        "doc_id": int(doc_ids[row_ids[j]]),
                        "distance": round(float(doc_dist[j]), 4),
                    }
                    for j in worst
                ]

                batch.append([
                    field,
                    str(value),
                    len(row_ids),
                    round(float(focus), 4),
                    json.dumps({
                        "labels": list(range(nb_topics)),
                        "data": [round(float(w), 6) for w in centroid],
                    }),
                    json.dumps(distinctive),
                    json.dumps(peers),
                    json.dumps(trajectory),
                    json.dumps(exemplars),
                    json.dumps(anomalies),
                ])

                if len(batch) >= 500:
                    cls.db.executemany(insert_sql, batch)
                    batch = []
            if batch:
                cls.db.executemany(insert_sql, batch)

        # Drop fields that ended up with fewer than two profiled values — a
        # field with a single value can't produce peers or meaningful
        # comparisons, and surfacing it in the explorer dropdown just adds
        # noise.
        cls.db.execute(
            "DELETE FROM metadata_profiles WHERE field_name IN ("
            "  SELECT field_name FROM metadata_profiles "
            "  GROUP BY field_name HAVING COUNT(*) < 2"
            ")"
        )

        cls.db.execute(
            "CREATE INDEX metadata_profiles_lookup "
            "ON metadata_profiles(field_name, field_value)"
        )

    @classmethod
    def save_topics(cls, topic_words_path, start_date, end_date, year_interval, topic_labeling=None):
        topic_words = []
        cls.db.execute("DROP TABLE IF EXISTS topics")
        cls.db.execute(
            "CREATE TABLE topics(topic_id INTEGER, word_distribution JSON, "
            "topic_evolution JSON, frequency DOUBLE, docs JSON)"
        )
        with tqdm(total=cls.model.nb_topics, leave=False, desc="Generating topic stats") as pbar:
            with Pool(cpu_count() - 1) as pool:
                for (
                    topic_id,
                    word_distribution,
                    topic_evolution,
                    frequency,
                    docs,
                    description,
                    top_words,
                ) in pool.imap_unordered(
                    cls.compute_topic,
                    zip(
                        range(cls.model.nb_topics),
                        repeat(start_date),
                        repeat(end_date),
                        repeat(year_interval),
                    ),
                ):
                    cls.db.execute(
                        "INSERT INTO topics (topic_id, word_distribution, topic_evolution, "
                        "frequency, docs) VALUES (?, ?, ?, ?, ?)",
                        [int(topic_id), word_distribution, topic_evolution, float(frequency), docs],
                    )
                    topic_words.append(
                        {
                            "name": topic_id,
                            # float(): the DuckDB insert above already coerces
                            # this, but the JSON copy did not -- so any backend
                            # whose topic_frequencies are not float64 (np.float32
                            # is not a Python float) failed here at the very end
                            # of a build.
                            "frequency": float(frequency),
                            "description": ", ".join(description),
                            "top_words": top_words,
                            "color": _topic_color(topic_id, cls.model.nb_topics),
                        }
                    )
                    pbar.update()

        topic_words.sort(key=lambda x: x["name"])
        with open(topic_words_path, "w") as out_file:
            json.dump(topic_words, out_file)

        if topic_labeling and topic_labeling.get("enabled"):
            import subprocess

            print("Labeling topics with LLM...", flush=True)
            result = subprocess.run(
                [
                    "topologic-labeler",
                    topic_words_path,
                    "--model", topic_labeling.get("model", "google/gemma-4-E2B-it"),
                    "--language", topic_labeling.get("language", "English"),
                ],
                check=False,
            )
            if result.returncode != 0:
                print(
                    f"topologic-labeler returned {result.returncode}; topics will fall "
                    "back to their top-word description.",
                    flush=True,
                )

        cls.db.execute("CREATE INDEX topic_id_index ON topics(topic_id)")

    @classmethod
    def compute_topic(cls, topic):
        topic_id, start_date, end_date, year_interval = topic
        top50 = cls.model.top_words(topic_id, 50)
        word_distribution = json.dumps({
            "labels": [w for w, _ in top50],
            "data": [float(wt) for _, wt in top50],
        })

        if start_date is None or end_date is None:
            topic_evolution = json.dumps({"labels": [], "data": []})
        else:
            years = {year: 0.0 for year in range(start_date, end_date + 1, year_interval)}
            for doc_id in range(cls.model.corpus.size):
                try:
                    year = cls.year_label_map[int(cls.metadata[doc_id]["year"])]
                    years[year] += (
                        float(cls.model.topic_distribution_for_document(doc_id)[topic_id]) / cls.docs_per_year[year]
                    )
                except (KeyError, ValueError):
                    pass
            topic_evolution = json.dumps({
                "labels": list(years.keys()),
                "data": [round(float(f), 4) for f in years.values()],
            })

        documents = [
            (int(doc_id), float(weight))
            for doc_id, weight in cls.model.top_documents(topic_id)
            if cls.model.corpus.sklearn_vector_space[doc_id].max() > 0
        ]

        top20 = cls.model.top_words(topic_id, 20)
        description = [w for w, _ in top20[:10]]
        top_words = [[w, float(wt)] for w, wt in top20]

        return (
            topic_id,
            word_distribution,
            topic_evolution,
            cls.model.get_topic_frequency(topic_id),
            json.dumps(documents),
            description,
            top_words,
        )


class DBSearch:
    """Read-side connection used by the API."""

    def __init__(self, db_path, object_level):
        # read_only=True allows multiple API workers to open the same file
        # concurrently without write-lock contention.
        self.db = duckdb.connect(db_path, read_only=True)
        self.object_level = object_level

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.db.close()

    @staticmethod
    def _validate_field(field):
        _check_identifier(field)

    def _exec_one(self, query, params=None):
        cur = self.db.execute(query, params or [])
        row = cur.fetchone()
        return _row_to_dict(cur, row)

    def _exec_all(self, query, params=None):
        cur = self.db.execute(query, params or [])
        rows = cur.fetchall()
        return _rows_to_dicts(cur, rows)

    def get_vocabulary(self):
        rows = self.db.execute("SELECT word FROM words").fetchall()
        return sorted(row[0] for row in rows)

    def get_all_metadata_values(self, field, frequency_filter=1):
        self._validate_field(field)
        if frequency_filter == 1:
            rows = self.db.execute(f'SELECT DISTINCT "{field}" FROM docs').fetchall()
            return sorted(r[0] for r in rows if r[0])
        rows = self.db.execute(
            f'SELECT "{field}", COUNT(*) AS field_count FROM docs GROUP BY "{field}"'
        ).fetchall()
        return sorted(r[0] for r in rows if r[0] and r[1] >= frequency_filter)

    def get_doc_data(self, philo_id, philo_db):
        _check_identifier(self.object_level)
        philo_id = " ".join(philo_id.split()[: OBJECT_LEVELS[self.object_level]])
        col = f"philo_{self.object_level}_id"
        self._validate_field(col)
        return self._exec_one(
            f'SELECT * FROM docs WHERE "{col}" = ? AND philo_db = ?',
            [philo_id, philo_db],
        )

    def get_doc_chunks(self, philo_id, philo_db):
        """Fetch precomputed chunks + doc-level topic distribution for the
        topical-reading view. Chunks are the per-chunk top-K topic estimates
        written by `DBHandler.save_doc_chunks()` at training time.
        """
        _check_identifier(self.object_level)
        philo_id = " ".join(philo_id.split()[: OBJECT_LEVELS[self.object_level]])
        col = f"philo_{self.object_level}_id"
        self._validate_field(col)
        return self._exec_one(
            f'SELECT doc_id, chunks, topic_distribution FROM docs '
            f'WHERE "{col}" = ? AND philo_db = ?',
            [philo_id, philo_db],
        )

    def get_metadata(self, doc_id, metadata_fields):
        for f in metadata_fields:
            self._validate_field(f)
        field_list = ", ".join(f'"{f}"' for f in metadata_fields)
        return self._exec_one(
            f"SELECT {field_list} FROM docs WHERE doc_id = ?",
            [doc_id],
        )

    def get_metadata_batch(self, doc_ids, metadata_fields):
        if not doc_ids:
            return {}
        for f in metadata_fields:
            self._validate_field(f)
        fields = ["doc_id", *metadata_fields]
        field_list = ", ".join(f'"{f}"' for f in fields)
        placeholders = ", ".join("?" for _ in doc_ids)
        rows = self._exec_all(
            f"SELECT {field_list} FROM docs WHERE doc_id IN ({placeholders})",
            list(doc_ids),
        )
        return {row["doc_id"]: row for row in rows}

    def get_doc_ids_by_metadata(self, field, value, end_value=None):
        self._validate_field(field)
        if end_value is None:
            rows = self.db.execute(
                f'SELECT DISTINCT doc_id FROM docs WHERE "{field}" = ?', [value]
            ).fetchall()
        else:
            rows = self.db.execute(
                f'SELECT DISTINCT doc_id, year FROM docs WHERE "{field}" >= ? AND "{field}" < ?',
                [value, end_value],
            ).fetchall()
        return set(r[0] for r in rows)

    def get_topic_data(
        self,
        topic_id,
        metadata_fields,
        correlation_interval=1,
        direction="positive",
    ):
        topic_data = self._exec_one(
            "SELECT * FROM topics WHERE topic_id = ?", [topic_id]
        )
        documents = []
        for document_id, weight in topic_data["docs"][:50]:
            metadata = self.get_metadata(document_id, metadata_fields)
            documents.append({"doc_id": document_id, "metadata": metadata, "score": weight})
        current_topic_evolution = topic_data["topic_evolution"]
        similar_topics = []
        window = _smoothing_window(correlation_interval)
        rebucketed_current = _rebucket(current_topic_evolution, correlation_interval)
        smoothed_current_for_display = None
        if rebucketed_current["data"]:
            current_smoothed = _smooth(rebucketed_current["data"], window)
            smoothed_current_for_display = {
                "labels": rebucketed_current["labels"],
                "data": [round(v, 4) for v in current_smoothed],
            }

            for topic, topic_evolution in self.get_topic_evolutions(int(topic_id)):
                rebucketed_other = _rebucket(topic_evolution, correlation_interval)
                other_smoothed = _smooth(rebucketed_other["data"], window)
                r = _pearson(current_smoothed, other_smoothed)
                similar_topics.append(
                    {
                        "topic": topic,
                        "topic_evolution": {
                            "labels": rebucketed_other["labels"],
                            "data": [round(v, 4) for v in other_smoothed],
                        },
                        "score": float(r),
                    }
                )

            if direction == "negative":
                similar_topics.sort(key=lambda x: x["score"])
            elif direction == "both":
                similar_topics.sort(key=lambda x: abs(x["score"]), reverse=True)
            else:
                similar_topics.sort(key=lambda x: x["score"], reverse=True)
        word_distribution = {"data": [], "labels": []}
        for weight, word in zip(topic_data["word_distribution"]["data"], topic_data["word_distribution"]["labels"]):
            if len(word_distribution["data"]) < 50:
                word_distribution["data"].append(weight)
                word_distribution["labels"].append(word)
        return {
            "word_distribution": word_distribution,
            "topic_evolution": current_topic_evolution,
            "current_smoothed_evolution": smoothed_current_for_display,
            "documents": documents,
            "frequency": topic_data["frequency"],
            "similar_topics": similar_topics,
        }

    def get_topic_data_by_year(self, topic_id, year, interval, metadata_fields, limit):
        topic_data = self._exec_one(
            "SELECT * FROM topics WHERE topic_id = ?", [topic_id]
        )
        if interval == 1:
            doc_ids = self.get_doc_ids_by_metadata("year", year)
        else:
            doc_ids = self.get_doc_ids_by_metadata("year", year, end_value=int(year) + interval)
        documents = []
        doc_counts = 0
        for doc_id, weight in topic_data["docs"]:
            if doc_id in doc_ids:
                metadata = self.get_metadata(doc_id, metadata_fields)
                documents.append({"doc_id": doc_id, "metadata": metadata, "score": weight})
                doc_counts += 1
            if doc_counts == 50:
                break
        return documents

    def get_topic_evolutions(self, topic_id):
        rows = self._exec_all(
            "SELECT topic_id, topic_evolution FROM topics WHERE topic_id != ?",
            [topic_id],
        )
        return [(r["topic_id"], r["topic_evolution"]) for r in rows]

    def get_word_data(self, word):
        return self._exec_one("SELECT * FROM words WHERE word = ?", [word])

    def get_word_from_id(self, word_id):
        row = self.db.execute(
            "SELECT word FROM words WHERE word_id = ?", [word_id]
        ).fetchone()
        return row[0] if row else None

    def get_profiled_fields(self):
        """Fields the Metadata Explorer can browse. Each entry has a `kind`:

        - `profile`: categorical field with a row in `metadata_profiles`;
          clicking a value opens the rich profile view.
        - `navigate`: near-identifier field (currently `title`) where each
          value maps to one document and a profile would be degenerate;
          clicking a value jumps straight to the document view.

        Returns [] if the `metadata_profiles` table is absent (older DBs).
        """
        has_table = self.db.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name = 'metadata_profiles' LIMIT 1"
        ).fetchone() is not None
        if not has_table:
            return []
        rows = self.db.execute(
            "SELECT field_name, COUNT(*) AS c FROM metadata_profiles "
            "GROUP BY field_name HAVING c >= 2 ORDER BY c DESC, field_name"
        ).fetchall()
        result = [
            {"field": r[0], "value_count": int(r[1]), "kind": "profile"}
            for r in rows
        ]

        # Navigation-only fields: surfaced in the Explorer so users can jump
        # to a document by title, but not profiled (one doc per value →
        # profile components collapse and duplicate the Document view).
        has_title = self.db.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'docs' AND column_name = 'title' LIMIT 1"
        ).fetchone() is not None
        if has_title:
            row = self.db.execute(
                "SELECT COUNT(DISTINCT title) FROM docs "
                "WHERE title IS NOT NULL AND title != ''"
            ).fetchone()
            count = int(row[0]) if row else 0
            if count > 0:
                result.append({
                    "field": "title",
                    "value_count": count,
                    "kind": "navigate",
                })
        return result

    def get_field_navigation_values(self, field):
        """Values + document coordinates for a navigation-only field. Each
        entry is `(value, philo_db, philo_id, philo_type)` — enough for the
        frontend to render a direct router-link to the Document view.

        Returns values in alphabetical order (case-insensitive) so the
        explorer's letter-bucketed grid groups them intuitively.
        """
        self._validate_field(field)
        rows = self.db.execute(
            f'SELECT "{field}", philo_db, philo_id, philo_type FROM docs '
            f'WHERE "{field}" IS NOT NULL AND "{field}" != \'\' '
            f'ORDER BY LOWER("{field}"), "{field}"'
        ).fetchall()
        seen = set()
        out = []
        for val, philo_db, philo_id, philo_type in rows:
            # De-duplicate on (value, philo_db) — two editions with the same
            # title on the same db would otherwise produce dupes in the grid.
            key = (val, philo_db)
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "value": val,
                "philo_db": philo_db,
                "philo_id": philo_id,
                "philo_type": philo_type,
            })
        return out

    def get_metadata_profile(self, field, field_value, metadata_fields):
        """Return the precomputed profile for a metadata value plus the
        citation metadata needed to render its exemplars and anomaly docs.

        Returns None if no profile exists — typically because the value has
        fewer documents than the `min_docs` floor used by `save_metadata_profiles`.
        """
        self._validate_field(field)
        row = self._exec_one(
            "SELECT field_name, field_value, doc_count, focus_score, "
            "topic_distribution, distinctive_topics, peers, trajectory, "
            "exemplars, anomalies FROM metadata_profiles "
            "WHERE field_name = ? AND field_value = ?",
            [field, field_value],
        )
        if row is None:
            return None

        exemplars = row.get("exemplars") or {}
        anomalies = row.get("anomalies") or []

        referenced_ids = set()
        for entry in exemplars.values():
            did = entry.get("doc_id")
            if did is not None:
                referenced_ids.add(int(did))
        for entry in anomalies:
            did = entry.get("doc_id")
            if did is not None:
                referenced_ids.add(int(did))

        # Single roundtrip: metadata + per-doc chunks for the exemplar HTML.
        enriched = {}
        if referenced_ids:
            for f in metadata_fields:
                self._validate_field(f)
            select_fields = ["doc_id", "chunks", *metadata_fields]
            field_list = ", ".join(f'"{f}"' for f in select_fields)
            placeholders = ", ".join("?" for _ in referenced_ids)
            rows = self._exec_all(
                f"SELECT {field_list} FROM docs WHERE doc_id IN ({placeholders})",
                list(referenced_ids),
            )
            for r in rows:
                did = int(r["doc_id"])
                metadata = {f: r.get(f) for f in metadata_fields}
                enriched[did] = {
                    "metadata": metadata,
                    "chunks": r.get("chunks") or [],
                }

        # Materialize exemplars: attach chunk HTML + citation metadata. Drop
        # entries whose referenced chunk is missing (shouldn't happen, but
        # don't crash the page if the training data changed under us).
        exemplar_docs = []
        for tid, entry in exemplars.items():
            did = int(entry.get("doc_id", -1))
            ci = int(entry.get("chunk_index", -1))
            doc_bundle = enriched.get(did)
            if doc_bundle is None or ci < 0 or ci >= len(doc_bundle["chunks"]):
                continue
            chunk = doc_bundle["chunks"][ci]
            exemplar_docs.append({
                "topic_id": int(tid),
                "doc_id": did,
                "metadata": doc_bundle["metadata"],
                "weight": float(entry.get("weight", 0.0)),
                "html": chunk.get("html", ""),
                "tokens": chunk.get("tokens", 0),
                "top_topics": chunk.get("top_topics", []),
            })
        # Present in the order of the value's top topics — i.e. by exemplar
        # weight on the topic, desc, but actually the author's centroid
        # ranking: we lost that when we keyed by tid, so re-sort here by
        # that value's own distinctive-topic rank if we have it.
        distinctive = row.get("distinctive_topics") or []
        tid_rank = {int(d[0]): i for i, d in enumerate(distinctive)}
        exemplar_docs.sort(
            key=lambda e: tid_rank.get(int(e["topic_id"]), 1_000_000)
        )

        anomaly_docs = []
        for entry in anomalies:
            did = int(entry.get("doc_id", -1))
            doc_bundle = enriched.get(did)
            if doc_bundle is None:
                continue
            anomaly_docs.append({
                "doc_id": did,
                "metadata": doc_bundle["metadata"],
                "distance": float(entry.get("distance", 0.0)),
            })

        return {
            "field_name": row["field_name"],
            "field_value": row["field_value"],
            "doc_count": row["doc_count"],
            "focus_score": row["focus_score"],
            "topic_distribution": row["topic_distribution"],
            "distinctive_topics": distinctive,
            "peers": row.get("peers") or [],
            "trajectory": row.get("trajectory") or {},
            "exemplars": exemplar_docs,
            "anomalies": anomaly_docs,
        }

    def get_topic_distribution_by_metadata(self, field, field_value):
        self._validate_field(field)
        # Push the per-topic summation into SQL — UNNEST the topic-weight array
        # from each matching doc, SUM by ordinal position. Avoids pulling every
        # row into Python and iterating dicts.
        rows = self.db.execute(
            "SELECT (ord - 1) AS topic_id, SUM(w) AS weight "
            "FROM docs, UNNEST(CAST(json_extract(topic_distribution, '$.data') AS DOUBLE[])) "
            f'WITH ORDINALITY AS t(w, ord) WHERE "{field}" = ? '
            "GROUP BY ord ORDER BY ord",
            [field_value],
        ).fetchall()
        if not rows:
            return []
        total = sum(r[1] for r in rows)
        if total == 0:
            return [{"name": r[0], "frequency": 0.0} for r in rows]
        coeff = 1.0 / total
        return [{"name": r[0], "frequency": r[1] * coeff} for r in rows]

    def get_corpus_overview(self, metadata_fields):
        """Corpus-level metadata histograms for the home-page overview.

        - Year histogram (if the `year` column exists): all years with a
          positive count, ordered chronologically.
        - Per-field top-20 (or fewer) by document count, for each string
          metadata field requested.
        """
        overview = {"year_distribution": [], "field_distributions": {}}
        has_year = self.db.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'docs' AND column_name = 'year' LIMIT 1"
        ).fetchone() is not None
        if has_year:
            rows = self.db.execute(
                "SELECT year, COUNT(*) FROM docs "
                "WHERE year IS NOT NULL AND year > 0 "
                "GROUP BY year ORDER BY year"
            ).fetchall()
            overview["year_distribution"] = [
                {"year": int(r[0]), "count": int(r[1])} for r in rows
            ]
        for field in metadata_fields:
            self._validate_field(field)
            rows = self.db.execute(
                f'SELECT "{field}" AS v, COUNT(*) AS c FROM docs '
                f'WHERE "{field}" IS NOT NULL AND "{field}" != \'\' '
                f'GROUP BY "{field}" ORDER BY c DESC LIMIT 10'
            ).fetchall()
            overview["field_distributions"][field] = [
                {"value": r[0], "count": int(r[1])} for r in rows
            ]
        return overview

    def get_topic_distributions_over_time(self):
        rows = self._exec_all(
            "SELECT topic_id, topic_evolution FROM topics ORDER BY topic_id ASC"
        )
        return [
            {"topic": r["topic_id"], "topic_evolution": r["topic_evolution"]}
            for r in rows
        ]

