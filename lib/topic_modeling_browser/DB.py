#!/usr/bin/env python3

import codecs
import json
import os
from math import log
from itertools import repeat

import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor
from tqdm import trange, tqdm
from multiprocess import Pool, cpu_count


class DBHandler:

    db = None
    cursor = None
    model = None
    metadata = None
    table = None

    def __init__(self):
        pass

    @classmethod
    def set_class_attributes(cls, config, table, model, corpus, metadata):
        cls.db = psycopg2.connect(
            user=config["database_user"], password=config["database_password"], database=config["database_name"]
        )
        cls.cursor = cls.db.cursor()
        cls.model = model
        cls.metadata = metadata
        cls.table = table
        return cls()

    @classmethod
    def save_words(cls):
        cls.cursor.execute(f"DROP TABLE IF EXISTS {cls.table}_words")
        cls.cursor.execute(
            f"CREATE TABLE {cls.table}_words(word_id INTEGER, word TEXT, distribution_across_topics JSONB, docs JSONB, docs_by_topic JSONB)"
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

        for word_id, docs in tqdm(word_weights.items(), leave=False, desc="Generating TF-IDF scores for all tokens"):
            word = cls.model.corpus.feature_names[word_id]
            idf = log(cls.model.corpus.size / len(docs))
            sorted_docs = sorted(
                [(doc_id, float(weight * idf)) for doc_id, weight in docs], key=lambda x: x[1], reverse=True
            )
            word_distribution = cls.model.topic_distribution_for_word(word_id)
            topics = []
            weights = []
            for i in range(len(word_distribution)):
                topics.append(i)
                weights.append(word_distribution[i])

            sim_doc_by_distribution = []
            cls.cursor.execute(
                f"INSERT INTO {cls.table}_words (word_id, word, distribution_across_topics, docs, docs_by_topic) VALUES (%s, %s, %s, %s, %s)",
                (
                    int(word_id),
                    word,
                    json.dumps({"labels": topics, "data": weights}),
                    json.dumps(sorted_docs),
                    json.dumps(sim_doc_by_distribution),
                ),
            )
        cls.cursor.execute(f"CREATE INDEX {cls.table}_word_id_index ON {cls.table}_words USING HASH(word_id)")
        cls.cursor.execute(f"CREATE INDEX {cls.table}_word_index ON {cls.table}_words USING HASH(word)")
        cls.db.commit()

    @classmethod
    def save_docs(cls):
        field_names = list(cls.metadata[0].keys())
        metadata_fields = []
        for field in field_names:
            if field == "year":
                metadata_fields.append(f"{field} INTEGER")
            else:
                metadata_fields.append(f"{field} TEXT")
        cls.cursor.execute(f"DROP TABLE IF EXISTS {cls.table}_docs")
        cls.cursor.execute(
            f"CREATE TABLE {cls.table}_docs(doc_id INTEGER, topic_distribution JSONB, topic_similarity JSONB, vector_similarity JSONB, word_list JSONB, {', '.join(metadata_fields)})"
        )
        with tqdm(total=cls.model.corpus.size, leave=False, desc="Generating doc stats") as pbar:
            with Pool(cpu_count() - 1) as pool:
                for values in pool.imap_unordered(cls.compute_doc, range(cls.model.corpus.size)):
                    cls.cursor.execute(
                        f"INSERT INTO {cls.table}_docs (doc_id, topic_distribution, topic_similarity, vector_similarity, word_list, {', '.join(field_names)}) VALUES (%s, %s, %s, %s, %s, {', '.join(['%s' for _ in range(len(field_names))])})",
                        values,
                    )
                    pbar.update()
        cls.cursor.execute(f"CREATE INDEX {cls.table}_doc_id_index ON {cls.table}_docs USING HASH(doc_id)")
        for field in field_names:
            cls.cursor.execute(f"CREATE INDEX {cls.table}_{field}_index ON {cls.table}_docs USING HASH({field})")
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
                for another_doc, score in cls.model.corpus.similar_docs_by_vector(
                    doc_id, 20, cls.model.document_topic_matrix
                )
            ]
        )
        vector_similarity = json.dumps(
            [
                (int(another_doc), round(float(score), 3))
                for another_doc, score in cls.model.corpus.similar_docs_by_topic_distribution(doc_id, 20)
            ]
        )

        # Get word_list
        vector = cls.model.corpus.sklearn_vector_space[doc_id].toarray()[0]
        non_zero = vector != 0
        word_list = json.dumps(
            [
                (cls.model.corpus.feature_names[word_id], float(vector[word_id]), int(word_id))
                for word_id in np.where(non_zero, vector, np.nan).argsort()[: non_zero.sum()][::-1]
            ]
        )
        field_values = []
        for field in cls.metadata[0].keys():
            try:
                field_values.append(cls.metadata[doc_id][field])
            except KeyError:
                field_values.append("")
        values = tuple([doc_id, topic_distribution, topic_similarity, vector_similarity, word_list] + field_values)
        return values

    @classmethod
    def save_topics(cls, topic_words_path, start_date, end_date, step=1):
        topic_words = []
        cls.cursor.execute(f"DROP TABLE IF EXISTS {cls.table}_topics")
        cls.cursor.execute(
            f"CREATE TABLE {cls.table}_topics(topic_id INTEGER, word_distribution JSONB, topic_evolution JSONB, frequency FLOAT, docs JSONB)"
        )
        with tqdm(total=cls.model.nb_topics, leave=False, desc="Generating topic stats") as pbar:
            with Pool(cpu_count() - 1) as pool:
                for (topic_id, word_distribution, topic_evolution, frequency, docs, description) in pool.imap_unordered(
                    cls.compute_topic,
                    zip(range(cls.model.nb_topics), repeat(start_date), repeat(end_date), repeat(step)),
                ):
                    cls.cursor.execute(
                        f"INSERT INTO {cls.table}_topics (topic_id, word_distribution, topic_evolution, frequency, docs) VALUES (%s, %s, %s, %s, %s)",
                        (topic_id, word_distribution, topic_evolution, frequency, docs),
                    )
                    topic_words.append(
                        {"name": topic_id, "frequency": frequency, "description": ", ".join(description)}
                    )
                    pbar.update()

        topic_words.sort(key=lambda x: x["name"])
        with open(topic_words_path, "w") as out_file:
            json.dump(topic_words, out_file)

        cls.cursor.execute(f"CREATE INDEX {cls.table}_topic_id_index on {cls.table}_topics USING HASH(topic_id)")
        cls.db.commit()

    @classmethod
    def compute_topic(cls, topic):
        topic_id, start_date, end_date, step = topic
        # Get word distributions
        words, weights = zip(*cls.model.top_words(topic_id, 50))
        word_distribution = json.dumps({"labels": words, "data": weights})

        # Compute topic evolution
        years = {year: 0.0 for year in range(start_date, end_date + step, step)}
        for doc_id in range(cls.model.corpus.size):
            year = int(cls.metadata[doc_id]["year"])
            years[year] += float(cls.model.topic_distribution_for_document(doc_id)[topic_id])
        dates, frequencies = zip(*list(years.items()))
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
        return topic_id, word_distribution, topic_evolution, frequency, docs, description


class DBSearch:
    def __init__(self, config, table):
        self.db = psycopg2.connect(
            user=config["database_user"], password=config["database_password"], database=config["database_name"]
        )
        self.cursor = self.db.cursor(cursor_factory=RealDictCursor)
        self.table = table

    def get_vocabulary(self):
        self.cursor.execute(f"SELECT word FROM {self.table}_words")
        return sorted([result["word"] for result in self.cursor])

    def get_doc_data(self, doc_id):
        self.cursor.execute(f"SELECT * FROM {self.table}_docs WHERE doc_id=%s", (doc_id,))
        return self.cursor.fetchone()

    def get_metadata(self, doc_id, metadata_fields):
        self.cursor.execute(f"SELECT {', '.join(metadata_fields)} FROM {self.table}_docs WHERE doc_id=%s", (doc_id,))
        return self.cursor.fetchone()

    def get_doc_ids_by_metadata(self, field, value):
        self.cursor.execute(f"SELECT distinct doc_id FROM {self.table}_docs WHERE {field}=%s", (value,))
        return set(row["doc_id"] for row in self.cursor)

    def get_topic_data(self, topic_id):
        self.cursor.execute(f"SELECT * FROM {self.table}_topics WHERE topic_id=%s", (topic_id,))
        return self.cursor.fetchone()

    def get_topic_evolutions(self, topic_id):
        self.cursor.execute(
            f"SELECT topic_id, topic_evolution FROM {self.table}_topics WHERE topic_id!=%s", (topic_id,)
        )
        return [(row["topic_id"], row["topic_evolution"]) for row in self.cursor]

    def get_word_data(self, word):
        self.cursor.execute(f"SELECT * FROM {self.table}_words WHERE word=%s", (word,))
        return self.cursor.fetchone()

    def get_word_from_id(self, word_id):
        self.cursor.execute(f"SELECT word FROM {self.table}_words WHERE word_id=%s", (word_id,))
        return self.cursor.fetchone()[0]

    def get_all_metadata_values(self, field):
        self.cursor.execute(f"SELECT DISTINCT {field} FROM {self.table}_docs")
        return sorted([row[field] for row in self.cursor if row[field]])

    def get_topic_distribution_by_metadata(self, field, field_value):
        topic_distribution = []
        self.cursor.execute(f"SELECT * FROM {self.table}_docs WHERE {field}=%s", (field_value,))
        for row in self.cursor:
            if not topic_distribution:
                topic_distribution = [
                    {"name": pos, "frequency": weight} for pos, weight in enumerate(row["topic_distribution"]["data"])
                ]
            else:
                for pos, weight in enumerate(row["topic_distribution"]["data"]):
                    topic_distribution[pos]["frequency"] += weight
        coeff = 1.0 / sum([topic["frequency"] for topic in topic_distribution])
        topic_distribution = [
            {"name": pos, "frequency": topic["frequency"] * coeff} for pos, topic in enumerate(topic_distribution)
        ]
        return topic_distribution

    def get_topic_distributions_over_time(self, interval):
        distributions_over_time = []
        self.cursor.execute(f"SELECT topic_id, topic_evolution FROM {self.table}_topics")
        for row in self.cursor:
            distributions_over_time.append({"topic": row["topic_id"], "topic_evolution": row["topic_evolution"]})
        return distributions_over_time
