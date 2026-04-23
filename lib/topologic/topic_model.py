#!/usr/bin/env python3

from abc import ABCMeta, abstractmethod

import numpy as np
from annoy import AnnoyIndex
from multiprocess import cpu_count
from scipy.sparse import csr_matrix
from sklearn.decomposition import NMF
from sklearn.decomposition import LatentDirichletAllocation as LDA
from sklearn.metrics import pairwise_distances
from tqdm import tqdm


class TopicModel(object):
    __metaclass__ = ABCMeta

    def __init__(self, corpus, max_iter=None):
        self.corpus = corpus  # a Corpus object
        self.document_topic_matrix = None  # document x topic matrix
        self.topic_word_matrix = None  # topic x word matrix
        self.nb_topics = None  # a scalar value > 1
        self.model = None
        self.max_iter = max_iter
        self.annoy_index = None
        self.topic_frequencies = None

    @abstractmethod
    def infer_topics(self, num_topics=10, **kwargs):
        pass

    def _store_matrices(self, topic_document):
        """Pack the fitted estimator's outputs into sparse CSR matrices."""
        self.topic_word_matrix = csr_matrix(self.model.components_)
        self.document_topic_matrix = csr_matrix(np.asarray(topic_document))

    def infer_and_replace(self, corpus):
        """Replace resulting matrices from training with full corpus."""
        self.corpus = corpus
        topic_document = self.model.transform(corpus.sklearn_vector_space)
        self._store_matrices(topic_document)

        topic_sums = np.asarray(self.document_topic_matrix.sum(axis=0)).ravel()
        total = topic_sums.sum()
        self.topic_frequencies = topic_sums / total if total else topic_sums

        self.annoy_index = AnnoyIndex(self.document_topic_matrix.shape[1], "angular")
        for i, doc_vector in tqdm(
            enumerate(self.document_topic_matrix),
            total=self.document_topic_matrix.shape[0],
            desc="Building Annoy index of document-topic vectors",
            leave=False,
        ):
            self.annoy_index.add_item(i, doc_vector.toarray()[0])
        self.annoy_index.build(1000, n_jobs=cpu_count() - 1)

    def most_similar_topic_by_doc_distribution(self):
        return pairwise_distances(self.document_topic_matrix.transpose())

    def top_words(self, topic_id, num_words):
        row = self.topic_word_matrix[topic_id].toarray()[0]
        order = np.argsort(row, kind="stable")[::-1][:num_words]
        return [(self.corpus.feature_names[i], float(row[i])) for i in order]

    def top_documents(self, topic_id, num_docs=None):
        col = self.document_topic_matrix[:, topic_id].toarray().ravel()
        order = np.argsort(col, kind="stable")[::-1]
        if num_docs is not None:
            order = order[:num_docs]
        else:
            order = order[col[order] > 0]
        return [(int(i), float(col[i])) for i in order]

    def word_distribution_for_topic(self, topic_id):
        return self.topic_word_matrix[topic_id].toarray()[0]

    def topic_distribution_for_document(self, doc_id):
        return self.document_topic_matrix[doc_id].toarray()[0]

    def topic_distribution_for_word(self, word_id):
        return self.topic_word_matrix[:, word_id].toarray().ravel()

    def get_topic_frequency(self, topic_id):
        return self.topic_frequencies[topic_id]

    def most_likely_topics_for_document(self, doc_id):
        topic_vector = self.topic_distribution_for_document(doc_id)
        topics = np.argsort(topic_vector)
        return zip(topics, (topic_vector[t] for t in topics))


class LatentDirichletAllocation(TopicModel):
    def infer_topics(self, num_topics=10, algorithm="variational", **kwargs):
        self.nb_topics = num_topics
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
        self._store_matrices(topic_document)


class NonNegativeMatrixFactorization(TopicModel):
    def infer_topics(self, num_topics=10, **kwargs):
        self.nb_topics = num_topics
        self.model = NMF(
            n_components=num_topics,
            init="nndsvda",
            solver="mu",
            beta_loss="kullback-leibler",
            alpha_H=0.00025 * num_topics,  # keeps the top word from dominating
            max_iter=self.max_iter,
            random_state=0,
            verbose=True,
        )
        topic_document = self.model.fit_transform(self.corpus.sklearn_vector_space)
        self._store_matrices(topic_document)
