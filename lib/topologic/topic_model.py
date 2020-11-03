#!/usr/bin/env python3

import itertools
import os
from abc import ABCMeta, abstractmethod

import numpy as np
from scipy.sparse import coo_matrix
from sklearn.decomposition import NMF
from sklearn.decomposition import LatentDirichletAllocation as LDA
from sklearn.metrics import pairwise_distances
from annoy import AnnoyIndex
from tqdm import tqdm
from multiprocess import cpu_count


class TopicModel(object):
    __metaclass__ = ABCMeta

    def __init__(self, corpus, max_iter=None):
        self.corpus = corpus  # a Corpus object
        self.document_topic_matrix = None  # document x topic matrix
        self.topic_word_matrix = None  # topic x word matrix
        self.nb_topics = None  # a scalar value > 1
        self.model = None
        self.max_iter = max_iter

    @abstractmethod
    def infer_topics(self, num_topics=10, **kwargs):
        pass

    def infer_and_replace(self, corpus):
        """Replace resulting matrices from training with full corpus"""
        self.corpus = corpus
        topic_document = self.model.transform(corpus.sklearn_vector_space)
        self.topic_word_matrix = []
        self.document_topic_matrix = []
        vocabulary_size = len(self.corpus.vectorizer.vocabulary_)
        row = []
        col = []
        data = []
        for topic_idx, topic in enumerate(self.model.components_):
            for i in range(vocabulary_size):
                row.append(topic_idx)
                col.append(i)
                data.append(topic[i])
        self.topic_word_matrix = coo_matrix(
            (data, (row, col)), shape=(self.nb_topics, len(self.corpus.vectorizer.vocabulary_))
        ).tocsr()
        row = []
        col = []
        data = []
        doc_count = 0
        for doc in topic_document:
            topic_count = 0
            for topic_weight in doc:
                row.append(doc_count)
                col.append(topic_count)
                data.append(topic_weight)
                topic_count += 1
            doc_count += 1
        self.document_topic_matrix = coo_matrix((data, (row, col)), shape=(self.corpus.size, self.nb_topics)).tocsr()
        topic_frequencies = np.sum(self.document_topic_matrix.transpose(), axis=1)
        self.topic_frequencies = topic_frequencies / np.sum(topic_frequencies)
        self.annoy_index = AnnoyIndex(self.document_topic_matrix.shape[1], "angular")
        for i, doc_vector in tqdm(
            enumerate(self.document_topic_matrix),
            total=self.document_topic_matrix.shape[0],
            desc="Building Annoy index of document-topic vectors",
            leave=False,
        ):
            self.annoy_index.add_item(i, doc_vector[0].toarray()[0])
        self.annoy_index.build(1000, n_jobs=cpu_count() - 1)

    def most_similar_topic_by_doc_distribution(self):
        return pairwise_distances(self.document_topic_matrix.transpose())

    def top_words(self, topic_id, num_words):
        vector = self.topic_word_matrix[topic_id]
        cx = vector.tocoo()
        weighted_words = [()] * len(self.corpus.vectorizer.vocabulary_)
        for word_id, weight in itertools.zip_longest(cx.col, cx.data):
            weighted_words[word_id] = (self.corpus.feature_names[word_id], weight)
        weighted_words.sort(key=lambda x: x[1], reverse=True)
        return weighted_words[:num_words]

    def top_documents(self, topic_id, num_docs=None):
        vector = self.document_topic_matrix[:, topic_id]
        cx = vector.tocoo()
        weighted_docs = [()] * self.corpus.size
        for doc_id, topic_id, weight in itertools.zip_longest(cx.row, cx.col, cx.data):
            weighted_docs[doc_id] = (doc_id, weight)
        weighted_docs.sort(key=lambda x: x[1], reverse=True)
        if num_docs is not None:
            return weighted_docs[:num_docs]
        else:
            return [d for d in weighted_docs if d[1] > 0]

    def word_distribution_for_topic(self, topic_id):
        vector = self.topic_word_matrix[topic_id].toarray()
        return vector[0]

    def topic_distribution_for_document(self, doc_id):
        vector = self.document_topic_matrix[doc_id].toarray()
        return vector[0]

    def topic_distribution_for_word(self, word_id):
        vector = self.topic_word_matrix[:, word_id].toarray()
        return vector.T[0]

    def get_topic_frequency(self, topic_id):
        return self.topic_frequencies[topic_id, 0]

    def most_likely_topics_for_document(self, doc_id):
        topic_vector = self.topic_distribution_for_document(doc_id)
        topics = np.argsort(topic_vector)
        weights = zip(topics, (topic_vector[topic] for topic in topics))
        return weights


class LatentDirichletAllocation(TopicModel):
    def infer_topics(self, num_topics=10, algorithm="variational", **kwargs):
        self.nb_topics = num_topics
        lda_model = None
        topic_document = None
        self.model = LDA(
            n_components=num_topics,
            learning_method="batch",
            n_jobs=-1,
            random_state=0,
            max_iter=self.max_iter,
            doc_topic_prior=1.0 / num_topics,
            topic_word_prior=0.01 / num_topics,
        )
        topic_document = self.model.fit_transform(self.corpus.sklearn_vector_space)
        self.topic_word_matrix = []
        self.document_topic_matrix = []
        vocabulary_size = len(self.corpus.vectorizer.vocabulary_)
        row = []
        col = []
        data = []
        for topic_idx, topic in enumerate(self.model.components_):
            for i in range(vocabulary_size):
                row.append(topic_idx)
                col.append(i)
                data.append(topic[i])
        self.topic_word_matrix = coo_matrix(
            (data, (row, col)), shape=(self.nb_topics, len(self.corpus.vectorizer.vocabulary_))
        ).tocsr()
        row = []
        col = []
        data = []
        doc_count = 0
        for doc in topic_document:
            topic_count = 0
            for topic_weight in doc:
                row.append(doc_count)
                col.append(topic_count)
                data.append(topic_weight)
                topic_count += 1
            doc_count += 1
        self.document_topic_matrix = coo_matrix((data, (row, col)), shape=(self.corpus.size, self.nb_topics)).tocsr()


class NonNegativeMatrixFactorization(TopicModel):
    def infer_topics(self, num_topics=10, **kwargs):
        self.nb_topics = num_topics
        self.model = NMF(
            n_components=num_topics, init="nndsvda", solver="cd", max_iter=self.max_iter, random_state=0, verbose=True
        )
        topic_document = self.model.fit_transform(self.corpus.sklearn_vector_space)
        self.topic_word_matrix = []
        self.document_topic_matrix = []
        vocabulary_size = len(self.corpus.vectorizer.vocabulary_)
        row = []
        col = []
        data = []
        for topic_idx, topic in enumerate(self.model.components_):
            for i in range(vocabulary_size):
                row.append(topic_idx)
                col.append(i)
                data.append(topic[i])
        self.topic_word_matrix = coo_matrix(
            (data, (row, col)), shape=(self.nb_topics, len(self.corpus.vectorizer.vocabulary_))
        ).tocsr()
        row = []
        col = []
        data = []
        doc_count = 0
        for doc in topic_document:
            topic_count = 0
            for topic_weight in doc:
                row.append(doc_count)
                col.append(topic_count)
                data.append(topic_weight)
                topic_count += 1
            doc_count += 1
        document_topic_matrix = coo_matrix((data, (row, col)), shape=(self.corpus.size, self.nb_topics)).tocsr()
        self.annoy_index = None

