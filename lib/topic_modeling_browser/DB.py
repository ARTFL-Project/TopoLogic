#!/usr/bin/env python3

import codecs
import json
import pickle
from psycopg2.extras import RealDictCursor
import psycopg2
import os
import numpy as np
from math import log
from tqdm import trange


def print_matrix(matrix):
    n_r = len(matrix[:, 0])
    for i in range(n_r):
        print(matrix[i, :])


class DBHandler:
    def __init__(self, config, table):
        self.db = psycopg2.connect(
            user=config["database_user"], password=config["database_password"], database=config["database_name"]
        )
        self.cursor = self.db.cursor(cursor_factory=RealDictCursor)
        self.table = table

    def save_topics(self, topic_words_path, topic_model, corpus, start_date, end_date, metadata, step=1):
        # Save topics
        topic_words = []
        for i in range(topic_model.nb_topics):
            description = []
            for weighted_word in topic_model.top_words(i, 10):
                description.append(weighted_word[0])
            topic_words.append(
                {
                    "name": i,
                    "frequency": topic_model.topic_frequency(i),
                    "description": ", ".join(description),
                    "group": i,
                }
            )
        with open(topic_words_path, "w") as out_file:
            json.dump(topic_words, out_file)

        self.cursor.execute(f"DROP TABLE IF EXISTS {self.table}_topics")
        self.cursor.execute(
            f"CREATE TABLE {self.table}_topics(topic_id INTEGER, word_distribution TEXT, topic_evolution TEXT, frequency FLOAT, docs TEXT)"
        )
        for topic_id in trange(topic_model.nb_topics, leave=False):
            # Get word distributions
            words, weights = zip(*topic_model.top_words(topic_id, 20))
            word_distribution = json.dumps({"labels": words, "data": weights})

            # Compute topic evolution
            evolution = []
            years = {year: 0.0 for year in range(start_date, end_date + step, step)}
            for doc_id in range(corpus.size):
                year = int(metadata[doc_id]["year"])
                topic = topic_model.most_likely_topic_for_document(doc_id)
                if topic == topic_id:
                    years[year] += 1.0 / corpus.size
            dates, frequencies = zip(*list(years.items()))
            topic_evolution = json.dumps({"labels": dates, "data": frequencies})

            # Get top documents per topic
            ids = topic_model.top_documents(topic_id)
            documents = []
            for document_id, weight in ids:
                document_array = corpus.sklearn_vector_space[document_id]
                if np.max(document_array.todense()) > 0:
                    documents.append((int(document_id), float(weight)))
            frequency = float(round(topic_model.topic_frequency(topic_id) * 100, 2))
            docs = json.dumps(documents)

            self.cursor.execute(
                f"INSERT INTO {self.table}_topics (topic_id, word_distribution, topic_evolution, frequency, docs) VALUES (%s, %s, %s, %s, %s)",
                (topic_id, word_distribution, topic_evolution, frequency, docs),
            )
        self.cursor.execute(f"CREATE INDEX topic_id_index on {self.table}_topics USING HASH(topic_id)")
        self.db.commit()

    def save_docs(self, topic_model, corpus, metadata):
        metadata_fields = []
        field_names = list(metadata[0].keys())
        for field in field_names:
            if field == "year":
                metadata_fields.append(f"{field} INTEGER")
            else:
                metadata_fields.append(f"{field} TEXT")
        self.cursor.execute(f"DROP TABLE IF EXISTS {self.table}_docs")
        self.cursor.execute(
            f"CREATE TABLE {self.table}_docs(doc_id INTEGER, topic_distribution TEXT, topic_similarity TEXT, vector_similarity TEXT, word_list TEXT, {', '.join(metadata_fields)})"
        )
        for doc_id in trange(topic_model.corpus.size, leave=False):
            # Get topic distributions
            topics = []
            weights = []
            distribution = topic_model.topic_distribution_for_document(doc_id)
            for i in range(len(distribution)):
                topics.append(i)
                weights.append(distribution[i])
            topic_distribution = json.dumps({"labels": topics, "data": weights})

            # Get similar docs
            topic_similarity = []
            for another_doc, score in corpus.similar_documents(doc_id, 20):
                another_doc = int(another_doc)
                score = float(score)
                topic_similarity.append((another_doc, round(score, 3)))
            vector_similarity = []
            for another_doc, score in (
                (d, 1.0 - corpus.similarity_matrix[doc_id][d])
                for d in np.argsort(corpus.similarity_matrix[doc_id])[:21]
                if d != doc_id
            ):
                another_doc = int(another_doc)
                score = float(score)
                vector_similarity.append((another_doc, round(score, 3)))
            topic_similarity = json.dumps(topic_similarity)
            vector_similarity = json.dumps(vector_similarity)

            # Get word_list
            vector = corpus.sklearn_vector_space[doc_id].toarray()[0]
            word_list = []
            for word_id, weight in enumerate(vector):
                if weight > 0:
                    word_list.append((corpus.word_for_id(word_id), weight, word_id))
            word_list.sort(key=lambda x: x[1])
            word_list.reverse()
            word_list = json.dumps(word_list)

            field_values = []
            for field in field_names:
                try:
                    field_values.append(metadata[doc_id][field])
                except KeyError:
                    field_values.append("")
            values = tuple([doc_id, topic_distribution, topic_similarity, vector_similarity, word_list] + field_values)
            self.cursor.execute(
                f"INSERT INTO {self.table}_docs (doc_id, topic_distribution, topic_similarity, vector_similarity, word_list, {', '.join(field_names)}) VALUES (%s, %s, %s, %s, %s, {', '.join(['%s' for _ in range(len(field_names))])})",
                values,
            )
        self.cursor.execute(f"CREATE INDEX doc_id_index ON {self.table}_docs USING HASH(doc_id)")
        self.db.commit()

    def save_words(self, topic_model, corpus):
        self.cursor.execute(f"DROP TABLE IF EXISTS {self.table}_words")
        self.cursor.execute(
            f"CREATE TABLE {self.table}_words(word_id INTEGER, word TEXT, distribution_across_topics TEXT, docs TEXT)"
        )

        # Get word weights across docs
        word_weights = {}
        for doc_id, doc_vector in enumerate(corpus.sklearn_vector_space):
            doc_vector = doc_vector.toarray()[0]
            for word_id in np.argsort(doc_vector)[::-1]:
                weight = doc_vector[word_id]
                if weight <= 0.0:
                    break
                if word_id not in word_weights:
                    word_weights[word_id] = []
                word_weights[word_id].append((doc_id, weight))

        for word_id, docs in word_weights.items():
            word = corpus.word_for_id(word_id)
            idf = log(corpus.size / len(docs))
            sorted_docs = sorted(
                [(doc_id, float(weight * idf)) for doc_id, weight in docs], key=lambda x: x[1], reverse=True
            )
            word_distribution = topic_model.topic_distribution_for_word(word_id)
            topics = []
            weights = []
            for i in range(len(word_distribution)):
                topics.append(i)
                weights.append(word_distribution[i])
            self.cursor.execute(
                f"INSERT INTO {self.table}_words (word_id, word, distribution_across_topics, docs) VALUES (%s, %s, %s, %s)",
                (int(word_id), word, json.dumps({"labels": topics, "data": weights}), json.dumps(sorted_docs)),
            )
        self.cursor.execute(f"CREATE INDEX word_id_index ON {self.table}_words USING HASH(word_id)")
        self.cursor.execute(f"CREATE INDEX word_index ON {self.table}_words USING HASH(word)")
        self.db.commit()

    def get_vocabulary(self):
        self.cursor.execute(f"SELECT word_id, word FROM {self.table}_words")
        word_list = []
        for result in self.cursor:
            word_list.append((result["word_id"], result["word"]))
        return word_list

    def get_doc_data(self, doc_id):
        self.cursor.execute(f"SELECT * FROM {self.table}_docs WHERE doc_id=%s", (doc_id,))
        return self.cursor.fetchone()

    def get_metadata(self, doc_id, metadata_fields):
        self.cursor.execute(f"SELECT {', '.join(metadata_fields)} FROM {self.table}_docs WHERE doc_id=%s", (doc_id,))
        return self.cursor.fetchone()

    def get_topic_data(self, topic_id):
        self.cursor.execute(f"SELECT * FROM {self.table}_topics WHERE topic_id=%s", (topic_id,))
        return self.cursor.fetchone()

    def get_word_data(self, word):
        self.cursor.execute(f"SELECT * FROM {self.table}_words WHERE word=%s", (word,))
        return self.cursor.fetchone()

    def get_word_from_id(self, word_id):
        self.cursor.execute(f"SELECT word FROM {self.table}_words WHERE word_id=%s", (word_id,))
        return self.cursor.fetchone()[0]
