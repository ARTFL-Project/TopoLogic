#!/usr/bin/env python3`
import itertools
import os

import numpy as np
from dill import dump, load
from scipy import spatial
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.metrics import pairwise_distances
from sklearn.metrics.pairwise import cosine_similarity

import networkx as nx
from networkx.readwrite import json_graph
from nltk.corpus import stopwords


def fast_cosine(X, Y):
    return np.inner(X, Y) / np.sqrt(np.dot(X, X) * np.dot(Y, Y))


class savedTexts:
    def __init__(self, text_path, min_tokens_per_doc=0):
        self.text_path = text_path
        self.min_tokens = min_tokens_per_doc

    def __iter__(self):
        for file in os.scandir(self.text_path):
            with open(file.path) as input_file:
                text = input_file.read()
                if len(text) >= self.min_tokens:
                    yield text


class Corpus:
    def __init__(
        self,
        source_files_path,
        metadata,
        language=None,
        n_gram=1,
        vectorization="tfidf",
        max_relative_frequency=1.0,
        min_absolute_frequency=0,
        max_features=2000,
        sample=None,
        vectorizer=None,
        min_tokens_per_doc=0,
    ):

        self._source_files = source_files_path
        self.metadata = metadata
        self._language = language
        self._n_gram = n_gram
        self._vectorization = vectorization
        self._max_relative_frequency = max_relative_frequency
        self._min_absolute_frequency = min_absolute_frequency

        self.max_features = max_features
        self.size = len(os.listdir(source_files_path))
        texts_to_vectorize = savedTexts(source_files_path, min_tokens_per_doc)

        if vectorizer is None:
            stop_words = []
            if language is not None:
                stop_words = stopwords.words(language)
            if vectorization == "tfidf":
                self.vectorizer = TfidfVectorizer(
                    ngram_range=(1, n_gram),
                    max_df=max_relative_frequency,
                    min_df=min_absolute_frequency,
                    max_features=self.max_features,
                    stop_words=stop_words,
                    smooth_idf=True,
                    sublinear_tf=True,
                )
            elif vectorization == "tf":
                self.vectorizer = CountVectorizer(
                    ngram_range=(1, n_gram),
                    max_df=max_relative_frequency,
                    min_df=min_absolute_frequency,
                    max_features=self.max_features,
                    stop_words=stop_words,
                )
            else:
                raise ValueError("Unknown vectorization type: %s" % vectorization)
            self.sklearn_vector_space = self.vectorizer.fit_transform(t for t in texts_to_vectorize)
        else:
            self.vectorizer = vectorizer
            self.sklearn_vector_space = self.vectorizer.transform(t for t in texts_to_vectorize)
        self.feature_names = self.vectorizer.get_feature_names()
        self.similarity_matrix = pairwise_distances(self.sklearn_vector_space, metric="cosine", n_jobs=1)

    def docs_for_word(self, word_id):
        ids = []
        for i in range(self.size):
            vector = self.sklearn_vector_space[i].toarray()[0]
            if vector[word_id] > 0:
                ids.append(i)
        return ids

    def vector_for_document(self, doc_id):
        vector = self.sklearn_vector_space[doc_id]
        cx = vector.tocoo()
        weights = [0.0] * len(self.vectorizer.vocabulary_)
        for row, word_id, weight in itertools.zip_longest(cx.row, cx.col, cx.data):
            weights[word_id] = weight
        return weights

    def word_for_id(self, word):
        return self.feature_names[word]

    def id_for_word(self, word_id):
        try:
            return self.vectorizer.vocabulary_[word_id]
        except KeyError:
            return -1

    def similar_documents(self, doc_id, num_docs):
        similarities = [
            (d, 1.0 - self.topic_distances[doc_id][d])
            for d in np.argsort(self.topic_distances[doc_id])[: num_docs + 1]
            if d != doc_id
        ]
        return similarities

    def similar_documents_by_topic_distribution(self, topic_model):
        self.topic_distances = pairwise_distances(topic_model.document_topic_matrix, metric="cosine")


def save_corpus(path, corpus):
    with open(os.path.join(path, "corpus"), "wb") as output_file:
        dump(corpus, output_file)


def load_corpus(path):
    with open(path, "rb") as input_file:
        corpus = load(input_file)
    return corpus
