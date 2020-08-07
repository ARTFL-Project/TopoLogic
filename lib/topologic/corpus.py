#!/usr/bin/env python3`

import itertools
import os
import random
import json
from math import floor
import pickle

import numpy as np
from dill import dump, load
from scipy import spatial
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.metrics import pairwise_distances
from sklearn.metrics.pairwise import linear_kernel, cosine_similarity
from scipy.spatial.distance import cdist


class savedTexts:
    def __init__(self, text_path, min_tokens_per_doc=0):
        self.text_path = text_path
        self.number_of_texts = 0
        for text_collection in os.scandir(text_path):
            self.number_of_texts += len(os.listdir(text_collection.path + "/texts"))
        self.min_tokens = min_tokens_per_doc

    def __iter__(self):
        files = []
        for text_collection in os.scandir(self.text_path):
            for input_file in os.scandir(os.path.join(text_collection.path, "texts")):
                files.append((input_file.path, int(input_file.name)))
        files.sort(key=lambda x: x[1])
        for file, _ in files:
            with open(file) as input_file:
                text = input_file.read()
                if len(text.split()) >= self.min_tokens:
                    yield text

    def random_sample(self, proportion=0.8):
        for text_collection in os.scandir(self.text_path):
            sample_size = floor(len(os.listdir(text_collection.path + "/texts")) * proportion)
            for file in random.sample([f.path for f in os.scandir(self.text_path)], sample_size):
                with open(file) as input_file:
                    text = input_file.read()
                    if len(text.split()) >= self.min_tokens:
                        yield text


class Corpus:
    def __init__(
        self,
        source_files_path,
        language=None,
        ngram=(1, 1),
        vectorization="tfidf",
        max_relative_frequency=1.0,
        min_absolute_frequency=0,
        max_features=None,
        vectorizer=None,
        min_tokens_per_doc=0,
    ):

        self._source_files = source_files_path
        self.metadata = self.__get_metadata(source_files_path)
        self.ngram = ngram
        self._language = language
        self._vectorization = vectorization
        self._max_relative_frequency = max_relative_frequency
        self._min_absolute_frequency = min_absolute_frequency
        self.max_features = max_features
        self.texts_to_vectorize = savedTexts(source_files_path, min_tokens_per_doc)
        self._vectorization = vectorization
        if len(ngram) == 1:
            ngram = (ngram[0], ngram[0])
        if vectorizer is None:
            if vectorization == "tfidf":
                self.vectorizer = TfidfVectorizer(
                    ngram_range=ngram,
                    max_df=max_relative_frequency,
                    min_df=min_absolute_frequency,
                    max_features=self.max_features,
                    smooth_idf=True,
                    sublinear_tf=True,
                )
            elif vectorization == "tf":
                self.vectorizer = CountVectorizer(
                    ngram_range=ngram,
                    max_df=max_relative_frequency,
                    min_df=min_absolute_frequency,
                    max_features=self.max_features,
                )
            else:
                raise ValueError("Unknown vectorization type: %s" % vectorization)
            self.sklearn_vector_space = self.vectorizer.fit_transform(t for t in self.texts_to_vectorize)
        else:
            self.vectorizer = vectorizer
            self.sklearn_vector_space = self.vectorizer.transform(t for t in self.texts_to_vectorize)
        self.size = self.sklearn_vector_space.shape[0]
        self.feature_names = self.vectorizer.get_feature_names()

    def __get_metadata(self, data_path):
        metadata = {}
        for text_collection in os.scandir(data_path):
            with open(os.path.join(text_collection.path, "metadata.pickle"), "rb") as metadata_file:
                metadata.update(pickle.load(metadata_file))
        return metadata

    def sample_corpus(self):
        self.sklearn_vector_space = self.vectorizer.transform(t for t in self.texts_to_vectorize.random_sample())

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
        for _, word_id, weight in itertools.zip_longest(cx.row, cx.col, cx.data):
            weights[word_id] = weight
        return weights

    def id_for_word(self, word_id):
        try:
            return self.vectorizer.vocabulary_[word_id]
        except KeyError:
            return -1

    def similar_docs_by_vector(self, doc_id, num_docs, topic_model_doc_matrix):
        if self._vectorization == "tfidf":
            vectors = linear_kernel(topic_model_doc_matrix[doc_id], topic_model_doc_matrix)
        else:
            vectors = cosine_similarity(topic_model_doc_matrix[doc_id], topic_model_doc_matrix)
        for d in np.argsort(vectors)[0][::-1][: num_docs + 1]:
            if d != doc_id:
                yield (d, vectors[0, d])

    def similar_docs_by_topic_distribution(self, doc_id, num_docs):
        vectors = cosine_similarity(self.sklearn_vector_space[doc_id], self.sklearn_vector_space)
        for d in np.argsort(vectors)[0][::-1][: num_docs + 1]:
            if d != doc_id:
                yield (d, vectors[0, d])
