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
from collections import Counter
from itertools import repeat
from math import log

import duckdb
import numpy as np
from multiprocess import Pool, cpu_count
from sklearn.metrics import pairwise_distances
from topologic import year_normalizer
from tqdm import tqdm, trange

VALID_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

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
        label_map = {}
        if topics_over_time_interval != 1:
            for year in range(min_year, max_year + 1):
                label_map[year] = year_normalizer(year, topics_over_time_interval)
        else:
            label_map = {year: year for year in range(min_year, max_year + 1)}
        cls.year_label_map = label_map
        docs_per_year = Counter()
        for doc in range(cls.model.corpus.size):
            try:
                docs_per_year[label_map[int(cls.metadata[doc]["year"])]] += 1
            except (KeyError, ValueError):
                pass  # document has been excluded by start or end date or has not date
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
        # Get word weights across docs
        word_weights = {}
        for doc_id, doc_vector in tqdm(
            enumerate(cls.model.corpus.sklearn_vector_space),
            leave=False,
            total=cls.model.corpus.size,
            desc="Getting all token weights across docs",
        ):
            doc_vector = doc_vector.toarray()[0]
            for word_id in np.argsort(doc_vector)[::-1]:
                weight = doc_vector[word_id]
                if weight <= 0.0:
                    break
                if word_id not in word_weights:
                    word_weights[word_id] = []
                word_weights[word_id].append((doc_id, weight))

        for word_id, docs in tqdm(
            word_weights.items(),
            leave=False,
            desc="Generating TF-IDF scores for all tokens",
        ):
            word = cls.model.corpus.feature_names[word_id]
            idf = log(cls.model.corpus.size / len(docs))
            sorted_docs = sorted(
                [(doc_id, float(weight * idf)) for doc_id, weight in docs],
                key=lambda x: x[1],
                reverse=True,
            )
            word_distribution = cls.model.topic_distribution_for_word(word_id)
            topics = []
            weights = []
            for i in range(len(word_distribution)):
                topics.append(i)
                weights.append(float(word_distribution[i]))

            similar_words_topic_array = 1.0 - word_similarities_by_topic[word_id]
            similar_words_by_topic = [
                {"word": cls.model.corpus.feature_names[other_word],
                 "weight": float(similar_words_topic_array[other_word])}
                for other_word in np.argsort(similar_words_topic_array)[::-1]
            ]

            similar_words_cooc_array = 1.0 - word_similarities_by_cooc[word_id]
            similar_words_by_cooc = [
                {"word": cls.model.corpus.feature_names[other_word],
                 "weight": float(similar_words_cooc_array[other_word])}
                for other_word in np.argsort(similar_words_cooc_array)[::-1]
            ]

            cls.db.execute(
                "INSERT INTO words (word_id, word, distribution_across_topics, docs, "
                "similar_words_by_topic, similar_words_by_cooc) VALUES (?, ?, ?, ?, ?, ?)",
                [
                    int(word_id),
                    word,
                    json.dumps({"labels": topics, "data": weights}),
                    json.dumps(sorted_docs),
                    json.dumps(similar_words_by_topic),
                    json.dumps(similar_words_by_cooc),
                ],
            )
        cls.db.execute("CREATE INDEX word_id_index ON words(word_id)")
        cls.db.execute("CREATE INDEX word_index ON words(word)")

    @classmethod
    def save_docs(cls):
        metadata_col_defs = ", ".join(
            f'"{f}" INTEGER' if f == "year" else f'"{f}" VARCHAR'
            for f in cls.field_names
        )
        cls.db.execute("DROP TABLE IF EXISTS docs")
        cls.db.execute(
            "CREATE TABLE docs(doc_id INTEGER, topic_distribution JSON, "
            "topic_similarity JSON, vector_similarity JSON, word_list JSON"
            + (f", {metadata_col_defs}" if metadata_col_defs else "")
            + ")"
        )
        field_ids = ", ".join(f'"{f}"' for f in cls.field_names)
        placeholders = ", ".join("?" for _ in cls.field_names)
        insert_query = (
            "INSERT INTO docs (doc_id, topic_distribution, topic_similarity, "
            "vector_similarity, word_list"
            + (f", {field_ids}" if field_ids else "")
            + ") VALUES (?, ?, ?, ?, ?"
            + (f", {placeholders}" if placeholders else "")
            + ")"
        )
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
        topics = []
        weights = []
        distribution = cls.model.topic_distribution_for_document(doc_id)
        for i in range(len(distribution)):
            topics.append(i)
            weights.append(float(distribution[i]))
        topic_distribution = json.dumps({"labels": topics, "data": weights})

        topic_similarity = json.dumps(
            [
                (int(another_doc), round(float(score), 3))
                for another_doc, score in cls.model.corpus.similar_docs_by_topic_distribution(doc_id, 20, cls.model)
            ]
        )
        vector_similarity = json.dumps(
            [
                (int(another_doc), round(float(score), 3))
                for another_doc, score in cls.model.corpus.similar_docs_by_vector(doc_id, 20)
            ]
        )

        vector = cls.model.corpus.sklearn_vector_space[doc_id].toarray()[0]
        nz_ids = np.flatnonzero(vector)
        ordered = nz_ids[np.argsort(vector[nz_ids])[::-1]]
        word_list = json.dumps(
            [
                (
                    cls.model.corpus.feature_names[i],
                    float(vector[i]),
                    int(i),
                )
                for i in ordered
            ]
        )

        field_values = []
        for field in cls.field_names:
            try:
                field_values.append(cls.metadata[doc_id][field])
            except KeyError:
                field_values.append("")
            if field == "year" and not field_values[-1]:
                field_values.pop()
                field_values.append(0)
        values = tuple([doc_id, topic_distribution, topic_similarity, vector_similarity, word_list] + field_values)
        return values

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
                            "frequency": frequency,
                            "description": ", ".join(description),
                            "top_words": top_words,
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
        words, weights = zip(*cls.model.top_words(topic_id, 50))
        word_distribution = json.dumps({"labels": list(words), "data": [float(w) for w in weights]})

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

            dates, frequencies = zip(*list(years.items()))
            frequencies = [round(float(f), 4) for f in frequencies]
            topic_evolution = json.dumps({"labels": list(dates), "data": frequencies})

        ids = cls.model.top_documents(topic_id)
        documents = []
        for document_id, weight in ids:
            document_array = cls.model.corpus.sklearn_vector_space[document_id]
            if np.max(document_array.todense()) > 0:
                documents.append((int(document_id), float(weight)))
        frequency = cls.model.get_topic_frequency(topic_id)
        docs = json.dumps(documents)
        description = []
        for weighted_word in cls.model.top_words(topic_id, 10):
            description.append(weighted_word[0])
        top_words = [[w, float(weight)] for w, weight in cls.model.top_words(topic_id, 20)]
        return (
            topic_id,
            word_distribution,
            topic_evolution,
            frequency,
            docs,
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
