#!/usr/bin/env python3

import itertools
import os
from abc import ABCMeta, abstractmethod

import numpy as np
from scipy import cluster, spatial
from scipy.sparse import coo_matrix
from sklearn.decomposition import NMF
from sklearn.decomposition import LatentDirichletAllocation as LDA
from sklearn.metrics import pairwise_distances
from multiprocess import Pool
from tqdm import tqdm

from .corpus import Corpus
from .stats import agreement_score, symmetric_kl


class TopicModel(object):
    __metaclass__ = ABCMeta

    def __init__(self, corpus):
        self.corpus = corpus  # a Corpus object
        self.document_topic_matrix = None  # document x topic matrix
        self.topic_word_matrix = None  # topic x word matrix
        self.nb_topics = None  # a scalar value > 1

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

    def most_similar_topic_by_doc_distribution(self):
        return pairwise_distances(self.document_topic_matrix.transpose())

    def greene_metric(self, corpus, min_num_topics=10, step=5, max_num_topics=50, top_n_words=10, tao=10, workers=4):
        """
        Implements Greene metric to compute the optimal number of topics. Taken from How Many Topics?
        Stability Analysis for Topic Models from Greene et al. 2014.
        :param step:
        :param min_num_topics: Minimum number of topics to test
        :param max_num_topics: Maximum number of topics to test
        :param top_n_words: Top n words for topic to use
        :param tao: Number of sampled models to build
        :return: A list of len (max_num_topics - min_num_topics) with the stability of each tested k
        """
        # Build reference topic model
        # Generate tao topic models with tao samples of the corpus
        # stability = []
        # for k in range(min_num_topics, max_num_topics + 1, step):
        #     self.infer_topics(k)
        #     reference_rank = [list(zip(*self.top_words(i, top_n_words)))[0] for i in range(k)]
        #     agreement_score_list = []
        #     for t in range(tao):
        #         print(f"\rEvaluating {k} topics... {t}/{tao}", end="", flush=True)
        #         corpus.sample_corpus()
        #         tao_model = type(self)(corpus)
        #         tao_model.infer_topics(k)
        #         tao_rank = [next(zip(*tao_model.top_words(i, top_n_words))) for i in range(k)]
        #         agreement_score_list.append(agreement_score(reference_rank, tao_rank))
        #     stability.append(np.mean(agreement_score_list))
        # print()

        def inner_greene(k):
            self.infer_topics(k)
            reference_rank = [list(zip(*self.top_words(i, top_n_words)))[0] for i in range(k)]
            agreement_score_list = []
            for t in range(tao):
                corpus.sample_corpus()
                tao_model = type(self)(corpus)
                tao_model.infer_topics(k)
                tao_rank = [next(zip(*tao_model.top_words(i, top_n_words))) for i in range(k)]
                agreement_score_list.append(agreement_score(reference_rank, tao_rank))
            return k, np.mean(agreement_score_list)

        steps = list(range(min_num_topics, max_num_topics + 1, step))
        stability = []
        with tqdm(total=len(steps), smoothing=0, leave=False, desc="Evaluating topic numbers") as pbar:
            with Pool(workers) as pool:
                for result in pool.imap_unordered(inner_greene, steps):
                    stability.append(result)
                    pbar.update()
        stability = [i for _, i in sorted(stability, key=lambda x: x[0])]
        return stability

    def print_topics(self, num_words=10, sort_by_freq=""):
        frequency = self.topics_frequency()
        topic_list = []
        for topic_id in range(self.nb_topics):
            word_list = []
            for weighted_word in self.top_words(topic_id, num_words):
                word_list.append(weighted_word[0])
            topic_list.append((topic_id, frequency[topic_id], word_list))
        if sort_by_freq == "asc":
            topic_list.sort(key=lambda x: x[1], reverse=False)
        elif sort_by_freq == "desc":
            topic_list.sort(key=lambda x: x[1], reverse=True)
        for topic_id, frequency, topic_desc in topic_list:
            print("topic %d\t%f\t%s" % (topic_id, frequency, " ".join(topic_desc)))

    def top_words(self, topic_id, num_words):
        vector = self.topic_word_matrix[topic_id]
        cx = vector.tocoo()
        weighted_words = [()] * len(self.corpus.vectorizer.vocabulary_)
        for row, word_id, weight in itertools.zip_longest(cx.row, cx.col, cx.data):
            weighted_words[word_id] = (self.corpus.word_for_id(word_id), weight)
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

    def most_likely_topic_for_document(self, doc_id):
        weights = list(self.topic_distribution_for_document(doc_id))
        return weights.index(max(weights))

    def topic_frequency(self, topic, date=None):
        return self.topics_frequency(date=date)[topic]

    def topics_frequency(self, date=None):
        frequency = np.zeros(self.nb_topics)
        if date is None:
            ids = range(self.corpus.size)
        else:
            ids = self.corpus.doc_ids(date)
        for i in ids:
            topic = self.most_likely_topic_for_document(i)
            frequency[topic] += 1.0 / len(ids)
        return frequency

    def documents_for_topic(self, topic_id):
        doc_ids = []
        for doc_id in range(self.corpus.size):
            most_likely_topic = self.most_likely_topic_for_document(doc_id)
            if most_likely_topic == topic_id:
                doc_ids.append(doc_id)
        return doc_ids

    def documents_per_topic(self):
        topic_associations = {}
        for i in range(self.corpus.size):
            topic_id = self.most_likely_topic_for_document(i)
            if topic_associations.get(topic_id):
                documents = topic_associations[topic_id]
                documents.append(i)
                topic_associations[topic_id] = documents
            else:
                documents = [i]
                topic_associations[topic_id] = documents
        return topic_associations


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
            max_iter=20,
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
        self.model = NMF(n_components=num_topics, init="nndsvd", solver="cd", random_state=0)
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
