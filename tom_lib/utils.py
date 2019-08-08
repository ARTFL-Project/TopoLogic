#!/usr/bin/env python3

import codecs
import json
import pickle
import sqlite3
import os
import numpy as np
from math import log
from tqdm import trange


__author__ = "Adrien Guille, Pavel Soriano"
__email__ = "adrien.guille@univ-lyon2.fr"


def print_matrix(matrix):
    n_r = len(matrix[:, 0])
    for i in range(n_r):
        print(matrix[i, :])


class DBHandler:
    def __init__(self, db_path):
        self.db = sqlite3.connect(os.path.join(db_path, "topic_model_data.db"))
        self.db.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
        self.cursor = self.db.cursor()

    def save_topics(self, topic_model, corpus, start_date, end_date, step=1):
        # Save topics
        json_graph = {}
        json_nodes = []
        json_links = []
        for i in range(topic_model.nb_topics):
            description = []
            for weighted_word in topic_model.top_words(i, 10):
                description.append(weighted_word[0])
            json_nodes.append({"name": i, "frequency": topic_model.topic_frequency(i), "description": ", ".join(description), "group": i})
        json_graph["nodes"] = json_nodes
        json_graph["links"] = json_links
        with open("./", "w") as out_file:
            json.dump(json_graph, out_file)

        self.cursor.execute("DROP TABLE IF EXISTS topics")
        self.cursor.execute(
            "CREATE TABLE topics(topic_id INTEGER, word_distribution TEXT, topic_evolution TEXT, frequency FLOAT, docs TEXT)"
        )
        for topic_id in trange(topic_model.nb_topics, leave=False):
            # Get word distributions
            words, weights = zip(*topic_model.top_words(topic_id, 20))
            word_distribution = json.dumps({"labels": words, "data": weights})

            # Compute topic evolution
            evolution = []
            for date in range(start_date, end_date + step, step):
                evolution.append((date, topic_model.topic_frequency(topic_id, date=date)))
            dates, frequencies = zip(*evolution)
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
                "INSERT INTO topics (topic_id, word_distribution, topic_evolution, frequency, docs) VALUES (?, ?, ?, ?, ?)",
                (topic_id, word_distribution, topic_evolution, frequency, docs),
            )
        self.cursor.execute("CREATE INDEX topic_id_index on topics(topic_id)")
        self.db.commit()

    def save_docs(self, topic_model, corpus, metadata):
        metadata_fields = []
        field_names = list(metadata[0].keys())
        for field in field_names:
            if field == "year":
                metadata_fields.append(f"{field} INTEGER")
            else:
                metadata_fields.append(f"{field} TEXT")
        self.cursor.execute("DROP TABLE IF EXISTS docs")
        self.cursor.execute(
            f"CREATE TABLE docs(doc_id INTEGER, topic_distribution TEXT, topic_similarity TEXT, vector_similarity TEXT, word_list TEXT, {', '.join(metadata_fields)})"
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
                topic_similarity.append(
                    (
                        corpus.title(another_doc).capitalize(),
                        ", ".join(corpus.author(another_doc)),
                        int(corpus.date(another_doc)),
                        another_doc,
                        round(score, 3),
                    )
                )
            vector_similarity = []
            for another_doc, score in (
                (d, 1.0 - corpus.similarity_matrix[doc_id][d]) for d in np.argsort(corpus.similarity_matrix[doc_id])[:21] if d != doc_id
            ):
                another_doc = int(another_doc)
                score = float(score)
                vector_similarity.append(
                    (
                        corpus.title(another_doc).capitalize(),
                        ", ".join(corpus.author(another_doc)),
                        int(corpus.date(another_doc)),
                        another_doc,
                        round(score, 3),
                    )
                )
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

            field_values = [metadata[doc_id][field] for field in field_names]
            values = tuple([doc_id, topic_distribution, topic_similarity, vector_similarity, word_list] + field_values)
            self.cursor.execute(
                f"INSERT INTO docs (doc_id, topic_distribution, topic_similarity, vector_similarity, word_list, {', '.join(field_names)}) VALUES (?, ?, ?, ?, ?, {', '.join(['?' for _ in range(len(field_names))])})",
                values,
            )
        self.cursor.execute("CREATE INDEX doc_id_index ON docs(doc_id)")
        self.db.commit()

    def save_words(self, topic_model, corpus):
        self.cursor.execute("DROP TABLE IF EXISTS words")
        self.cursor.execute("CREATE TABLE words(word_id INTEGER, word TEXT, distribution_across_topics TEXT, docs TEXT)")

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
            sorted_docs = sorted([(doc_id, float(weight * idf)) for doc_id, weight in docs], key=lambda x: x[1], reverse=True)
            word_distribution = topic_model.topic_distribution_for_word(word_id)
            topics = []
            weights = []
            for i in range(len(word_distribution)):
                topics.append(i)
                weights.append(word_distribution[i])
            self.cursor.execute(
                "INSERT INTO words (word_id, word, distribution_across_topics, docs) VALUES (?, ?, ?, ?)",
                (int(word_id), word, json.dumps({"labels": topics, "data": weights}), json.dumps(sorted_docs)),
            )
        self.cursor.execute("CREATE INDEX word_id_index ON words(word_id)")
        self.db.commit()

    def get_vocabulary(self):
        self.cursor.execute("SELECT word_id, word FROM words")
        word_list = []
        for result in self.cursor:
            word_list.append((result["word_id"], result["word"]))
        return word_list

    def get_doc_data(self, doc_id):
        self.cursor.execute("SELECT * FROM docs WHERE doc_id=?", (doc_id,))
        return self.cursor.fetchone()

    def get_metadata(self, doc_id, metadata_fields):
        self.cursor.execute(f"SELECT {', '.join(metadata_fields)} FROM docs WHERE doc_id=?", (doc_id,))
        return self.cursor.fetchone()

    def get_topic_data(self, topic_id):
        self.cursor.execute("SELECT * FROM topics WHERE topic_id=?", (topic_id,))
        return self.cursor.fetchone()

    def get_word_data(self, word_id):
        self.cursor.execute("SELECT * FROM words WHERE word_id=?", (word_id,))
        return self.cursor.fetchone()

    def get_word_from_id(self, word_id):
        self.cursor.execute("SELECT word FROM words WHERE word_id=?", (word_id,))
        return self.cursor.fetchone()[0]


def save_json_object(json_object, file_path):
    with codecs.open(file_path, "w", encoding="utf-8") as fp:
        json.dump(json_object, fp, indent=4, separators=(",", ": "))
