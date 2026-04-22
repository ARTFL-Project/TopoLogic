#!/usr/bin/env python3

import json
import re
from collections import Counter
from itertools import repeat
from math import log

import numpy as np
import psycopg2
from psycopg2 import sql, extensions as psycopg2_extensions
from psycopg2.extras import RealDictCursor

# psycopg2 doesn't know how to adapt numpy scalars; in numpy 2.0 their repr
# became "np.float64(x)" rather than "x", producing malformed SQL.
psycopg2_extensions.register_adapter(np.int64, lambda v: psycopg2_extensions.AsIs(int(v)))
psycopg2_extensions.register_adapter(np.int32, lambda v: psycopg2_extensions.AsIs(int(v)))
psycopg2_extensions.register_adapter(np.float64, lambda v: psycopg2_extensions.AsIs(float(v)))
psycopg2_extensions.register_adapter(np.float32, lambda v: psycopg2_extensions.AsIs(float(v)))
from multiprocess import Pool, cpu_count
from sklearn.metrics import pairwise_distances
from topologic import year_normalizer
from tqdm import tqdm, trange

VALID_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _check_identifier(name):
    """Validate that a name is safe to use as a SQL identifier."""
    if not VALID_IDENTIFIER_RE.match(name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")


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

    db = None
    cursor = None
    model = None
    metadata = None
    table = None
    docs_per_year = None
    field_names = None
    time_series_enabled = True

    def __init__(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *args):
        if exc_type is not None:
            cls = type(self)
            cls.db.rollback()
        if type(self).db is not None:
            type(self).cursor.close()
            type(self).db.close()

    @classmethod
    def set_class_attributes(
        cls,
        config,
        table,
        model,
        corpus,
        min_year,
        max_year,
        topics_over_time_interval,
        time_series_enabled=True,
    ):
        cls.db = psycopg2.connect(
            user=config["database_user"],
            password=config["database_password"],
            database=config["database_name"],
        )
        cls.cursor = cls.db.cursor()
        cls.model = model
        cls.metadata = corpus.metadata
        field_names = set()
        for doc_metadata in cls.metadata.values():
            field_names.update(doc_metadata.keys())
        cls.field_names = list(field_names)
        cls.table = table
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
        words_table = sql.Identifier(f"{cls.table}_words")
        cls.cursor.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(words_table))
        cls.cursor.execute(
            sql.SQL("CREATE TABLE {}(word_id INTEGER, word TEXT, distribution_across_topics JSONB, docs JSONB, similar_words_by_topic JSONB, similar_words_by_cooc JSONB)").format(words_table)
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
                weights.append(word_distribution[i])

            similar_words_topic_array = 1.0 - word_similarities_by_topic[word_id]  # convert distance to similarity
            similar_words_by_topic = []
            for other_word in np.argsort(similar_words_topic_array)[::-1]:
                similar_words_by_topic.append(
                    {
                        "word": cls.model.corpus.feature_names[other_word],
                        "weight": similar_words_topic_array[other_word],
                    }
                )

            similar_words_cooc_array = 1.0 - word_similarities_by_cooc[word_id]  # convert distance to similarity
            similar_words_by_cooc = []
            for other_word in np.argsort(similar_words_cooc_array)[::-1]:
                similar_words_by_cooc.append(
                    {
                        "word": cls.model.corpus.feature_names[other_word],
                        "weight": similar_words_cooc_array[other_word],
                    }
                )

            cls.cursor.execute(
                sql.SQL("INSERT INTO {} (word_id, word, distribution_across_topics, docs, similar_words_by_topic, similar_words_by_cooc) VALUES (%s, %s, %s, %s, %s, %s)").format(words_table),
                (
                    int(word_id),
                    word,
                    json.dumps({"labels": topics, "data": weights}),
                    json.dumps(sorted_docs),
                    json.dumps(similar_words_by_topic),
                    json.dumps(similar_words_by_cooc),
                ),
            )
        cls.cursor.execute(sql.SQL("CREATE INDEX {} ON {} USING HASH(word_id)").format(
            sql.Identifier(f"{cls.table}_word_id_index"), words_table
        ))
        cls.cursor.execute(sql.SQL("CREATE INDEX {} ON {} USING HASH(word)").format(
            sql.Identifier(f"{cls.table}_word_index"), words_table
        ))
        cls.db.commit()

    @classmethod
    def save_docs(cls):
        docs_table = sql.Identifier(f"{cls.table}_docs")
        metadata_col_defs = sql.SQL(", ").join(
            sql.SQL("{} INTEGER").format(sql.Identifier(f)) if f == "year"
            else sql.SQL("{} TEXT").format(sql.Identifier(f))
            for f in cls.field_names
        )
        cls.cursor.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(docs_table))
        cls.cursor.execute(
            sql.SQL("CREATE TABLE {}(doc_id INTEGER, topic_distribution JSONB, topic_similarity JSONB, vector_similarity JSONB, word_list JSONB, {})").format(
                docs_table, metadata_col_defs
            )
        )
        field_ids = sql.SQL(", ").join(sql.Identifier(f) for f in cls.field_names)
        placeholders = sql.SQL(", ").join(sql.Placeholder() for _ in range(len(cls.field_names)))
        insert_query = sql.SQL("INSERT INTO {} (doc_id, topic_distribution, topic_similarity, vector_similarity, word_list, {}) VALUES (%s, %s, %s, %s, %s, {})").format(
            docs_table, field_ids, placeholders
        )
        with tqdm(total=cls.model.corpus.size, leave=False, desc="Generating doc stats") as pbar:
            with Pool(cpu_count() - 1) as pool:
                for values in pool.imap_unordered(cls.compute_doc, range(cls.model.corpus.size)):
                    cls.cursor.execute(insert_query, values)
                    pbar.update()
        cls.cursor.execute(sql.SQL("CREATE INDEX {} ON {} USING HASH(doc_id)").format(
            sql.Identifier(f"{cls.table}_doc_id_index"), docs_table
        ))
        for field in cls.field_names:
            cls.cursor.execute(sql.SQL("CREATE INDEX {} ON {} USING HASH({})").format(
                sql.Identifier(f"{cls.table}_{field}_index"), docs_table, sql.Identifier(field)
            ))
        cls.db.commit()

    @classmethod
    def compute_doc(cls, doc_id):
        topics = []
        weights = []
        distribution = cls.model.topic_distribution_for_document(doc_id)
        for i in range(len(distribution)):
            topics.append(i)
            weights.append(distribution[i])
        topic_distribution = json.dumps({"labels": topics, "data": weights})

        # Get similar docs
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

        # Get word_list
        vector = cls.model.corpus.sklearn_vector_space[doc_id].toarray()[0]
        non_zero = vector != 0
        word_list = json.dumps(
            [
                (
                    cls.model.corpus.feature_names[word_id],
                    float(vector[word_id]),
                    int(word_id),
                )
                for word_id in np.where(non_zero, vector, np.nan).argsort()[: non_zero.sum()][::-1]
            ]
        )

        # Get metadata values
        field_values = []
        for field in cls.field_names:
            try:
                field_values.append(cls.metadata[doc_id][field])
            except KeyError:
                field_values.append("")
            if field == "year" and not field_values[-1]:  # in case the doc has no year
                field_values.pop()
                field_values.append(0)
        values = tuple([doc_id, topic_distribution, topic_similarity, vector_similarity, word_list] + field_values)
        return values

    @classmethod
    def save_topics(cls, topic_words_path, start_date, end_date, year_interval, topic_labeling=None):
        topic_words = []
        topics_table = sql.Identifier(f"{cls.table}_topics")
        cls.cursor.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(topics_table))
        cls.cursor.execute(
            sql.SQL("CREATE TABLE {}(topic_id INTEGER, word_distribution JSONB, topic_evolution JSONB, frequency FLOAT, docs JSONB)").format(topics_table)
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
                    cls.cursor.execute(
                        sql.SQL("INSERT INTO {} (topic_id, word_distribution, topic_evolution, frequency, docs) VALUES (%s, %s, %s, %s, %s)").format(topics_table),
                        (topic_id, word_distribution, topic_evolution, frequency, docs),
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

        cls.cursor.execute(sql.SQL("CREATE INDEX {} ON {} USING HASH(topic_id)").format(
            sql.Identifier(f"{cls.table}_topic_id_index"), topics_table
        ))
        cls.db.commit()

    @classmethod
    def compute_topic(cls, topic):
        topic_id, start_date, end_date, year_interval = topic
        # Get word distributions
        words, weights = zip(*cls.model.top_words(topic_id, 50))
        word_distribution = json.dumps({"labels": words, "data": weights})

        # Compute topic evolution
        if start_date is None or end_date is None:
            topic_evolution = json.dumps({"labels": [], "data": []})
        else:
            years = {year: 0.0 for year in range(start_date, end_date, year_interval)}
            for doc_id in range(cls.model.corpus.size):
                try:
                    year = cls.year_label_map[int(cls.metadata[doc_id]["year"])]
                    years[year] += (
                        float(cls.model.topic_distribution_for_document(doc_id)[topic_id]) / cls.docs_per_year[year]
                    )
                except (KeyError, ValueError):  # account for various issues with year field
                    pass

            dates, frequencies = zip(*list(years.items()))
            # Round to kill float-accumulation artifacts like 0.6999999999999996
            # that leak into chart axis labels.
            frequencies = [round(float(f), 2) for f in frequencies]
            topic_evolution = json.dumps({"labels": dates, "data": frequencies})

        # Get top documents per topic
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
        # Richer top-20-with-weights payload, used by the LLM labeler.
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
    def __init__(self, config, table, object_level):
        _check_identifier(table)
        self.db = psycopg2.connect(
            user=config["database_user"],
            password=config["database_password"],
            database=config["database_name"],
        )
        self.cursor = self.db.cursor(cursor_factory=RealDictCursor)
        self.table = table
        self.object_level = object_level
        self._words_table = sql.Identifier(f"{table}_words")
        self._docs_table = sql.Identifier(f"{table}_docs")
        self._topics_table = sql.Identifier(f"{table}_topics")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.cursor.close()
        self.db.close()

    @staticmethod
    def _validate_field(field):
        """Validate field name is a safe SQL identifier."""
        _check_identifier(field)

    def get_vocabulary(self):
        self.cursor.execute(sql.SQL("SELECT word FROM {}").format(self._words_table))
        return sorted([result["word"] for result in self.cursor])

    def get_all_metadata_values(self, field, frequency_filter=1):
        self._validate_field(field)
        field_id = sql.Identifier(field)
        if frequency_filter == 1:
            self.cursor.execute(sql.SQL("SELECT DISTINCT {} FROM {}").format(field_id, self._docs_table))
            return sorted([row[field] for row in self.cursor if row[field]])
        self.cursor.execute(sql.SQL("SELECT {}, COUNT(*) AS field_count FROM {} GROUP BY {}").format(
            field_id, self._docs_table, field_id
        ))
        return sorted([row[field] for row in self.cursor if row[field] and row["field_count"] >= frequency_filter])

    def get_doc_data(self, philo_id, philo_db):
        _check_identifier(self.object_level)
        philo_id = " ".join(philo_id.split()[: OBJECT_LEVELS[self.object_level]])
        self.cursor.execute(
            sql.SQL("SELECT * FROM {} WHERE {} = %s AND philo_db = %s").format(
                self._docs_table, sql.Identifier(f"philo_{self.object_level}_id")
            ),
            (philo_id, philo_db),
        )
        return self.cursor.fetchone()

    def get_metadata(self, doc_id, metadata_fields):
        for f in metadata_fields:
            self._validate_field(f)
        fields = sql.SQL(", ").join(sql.Identifier(f) for f in metadata_fields)
        self.cursor.execute(
            sql.SQL("SELECT {} FROM {} WHERE doc_id = %s").format(fields, self._docs_table),
            (doc_id,),
        )
        return self.cursor.fetchone()

    def get_metadata_batch(self, doc_ids, metadata_fields):
        if not doc_ids:
            return {}
        for f in metadata_fields:
            self._validate_field(f)
        fields = sql.SQL(", ").join(sql.Identifier(f) for f in ["doc_id", *metadata_fields])
        self.cursor.execute(
            sql.SQL("SELECT {} FROM {} WHERE doc_id = ANY(%s)").format(fields, self._docs_table),
            (list(doc_ids),),
        )
        return {row["doc_id"]: row for row in self.cursor.fetchall()}

    def get_doc_ids_by_metadata(self, field, value, end_value=None):
        self._validate_field(field)
        field_id = sql.Identifier(field)
        if end_value is None:
            self.cursor.execute(
                sql.SQL("SELECT DISTINCT doc_id FROM {} WHERE {} = %s").format(self._docs_table, field_id),
                (value,),
            )
        else:
            self.cursor.execute(
                sql.SQL("SELECT DISTINCT doc_id, year FROM {} WHERE {} >= %s AND {} < %s").format(
                    self._docs_table, field_id, field_id
                ),
                (value, end_value),
            )
        return set(row["doc_id"] for row in self.cursor)

    def get_topic_data(
        self,
        topic_id,
        metadata_fields,
        correlation_interval=1,
        direction="positive",
    ):
        self.cursor.execute(sql.SQL("SELECT * FROM {} WHERE topic_id = %s").format(self._topics_table), (topic_id,))
        topic_data = self.cursor.fetchone()
        documents = []
        for document_id, weight in topic_data["docs"][:50]:
            metadata = self.get_metadata(document_id, metadata_fields)
            documents.append({"doc_id": document_id, "metadata": metadata, "score": weight})
        # Bar chart uses the raw per-year series (client rebuckets for display).
        current_topic_evolution = topic_data["topic_evolution"]
        similar_topics = []
        # For the correlation panel: re-bucket, smooth once, and compute Pearson on
        # the same smoothed series that the chart will display. This keeps the
        # chart and the correlation metric in sync — what the user sees IS what
        # the score is computed from.
        #
        # Smoothing window grows sub-linearly with the interval (see _smoothing_window
        # for the exact rule). Keeps year-level views honest while damping
        # bucket-to-bucket jumps at coarser intervals.
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

            # "positive": rise and fall together (highest r first).
            # "negative": one rises when the other falls (most-negative r first).
            # "both": sort by magnitude so strong correlations of either sign surface.
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
            # Raw per-year series for the bar chart (client rebuckets freely).
            "topic_evolution": current_topic_evolution,
            # Rebucketed + smoothed current topic for overlay on the correlation
            # chart, matching what the similar-topics series have been through.
            "current_smoothed_evolution": smoothed_current_for_display,
            "documents": documents,
            "frequency": topic_data["frequency"],
            "similar_topics": similar_topics,
        }

    def get_topic_data_by_year(self, topic_id, year, interval, metadata_fields, limit):
        self.cursor.execute(sql.SQL("SELECT * FROM {} WHERE topic_id = %s").format(self._topics_table), (topic_id,))
        topic_data = self.cursor.fetchone()
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
        self.cursor.execute(
            sql.SQL("SELECT topic_id, topic_evolution FROM {} WHERE topic_id != %s").format(self._topics_table),
            (topic_id,),
        )
        return [(row["topic_id"], row["topic_evolution"]) for row in self.cursor]

    def get_word_data(self, word):
        self.cursor.execute(sql.SQL("SELECT * FROM {} WHERE word = %s").format(self._words_table), (word,))
        return self.cursor.fetchone()

    def get_word_from_id(self, word_id):
        self.cursor.execute(sql.SQL("SELECT word FROM {} WHERE word_id = %s").format(self._words_table), (word_id,))
        row = self.cursor.fetchone()
        return row["word"] if row else None

    def get_topic_distribution_by_metadata(self, field, field_value):
        self._validate_field(field)
        topic_distribution = []
        self.cursor.execute(
            sql.SQL("SELECT * FROM {} WHERE {} = %s").format(self._docs_table, sql.Identifier(field)),
            (field_value,),
        )
        for row in self.cursor:
            if not topic_distribution:
                topic_distribution = [
                    {"name": pos, "frequency": weight} for pos, weight in enumerate(row["topic_distribution"]["data"])
                ]
            else:
                for pos, weight in enumerate(row["topic_distribution"]["data"]):
                    topic_distribution[pos]["frequency"] += weight
        total = sum(topic["frequency"] for topic in topic_distribution)
        if total == 0:
            return topic_distribution
        coeff = 1.0 / total
        topic_distribution = [
            {"name": pos, "frequency": topic["frequency"] * coeff} for pos, topic in enumerate(topic_distribution)
        ]
        return topic_distribution

    def get_topic_distributions_over_time(self):
        distributions_over_time = []
        self.cursor.execute(sql.SQL("SELECT topic_id, topic_evolution FROM {} ORDER BY topic_id ASC").format(self._topics_table))
        for row in self.cursor:
            distributions_over_time.append({"topic": row["topic_id"], "topic_evolution": row["topic_evolution"]})
        return distributions_over_time
