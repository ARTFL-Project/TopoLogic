# coding: utf-8
import itertools

from dill import dump, load
from scipy import spatial
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.metrics import pairwise_distances
from sklearn.metrics.pairwise import cosine_similarity

import networkx as nx
import pandas
from networkx.readwrite import json_graph
from nltk.corpus import stopwords
import numpy as np

__author__ = "Adrien Guille, Pavel Soriano"
__email__ = "adrien.guille@univ-lyon2.fr"


def fast_cosine(X, Y):
    return np.inner(X, Y) / np.sqrt(np.dot(X, X) * np.dot(Y, Y))


class Corpus:
    def __init__(
        self,
        source_file_path,
        language=None,
        n_gram=1,
        vectorization="tfidf",
        max_relative_frequency=1.0,
        min_absolute_frequency=0,
        max_features=2000,
        sample=None,
        vectorizer=None,
    ):

        self._source_file_path = source_file_path
        self._language = language
        self._n_gram = n_gram
        self._vectorization = vectorization
        self._max_relative_frequency = max_relative_frequency
        self._min_absolute_frequency = min_absolute_frequency

        self.max_features = max_features
        self.data_frame = pandas.read_csv(source_file_path, sep="\t", encoding="utf-8")
        if sample:
            self.data_frame = self.data_frame.sample(frac=0.8)
        self.data_frame.fillna(" ")
        self.size = self.data_frame.count(0)[0]

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

            self.sklearn_vector_space = self.vectorizer.fit_transform(t for t in self.data_frame["text"])
        else:
            self.vectorizer = vectorizer
            self.sklearn_vector_space = self.vectorizer.transform(t for t in self.data_frame["text"])
        vocab = self.vectorizer.get_feature_names()
        self.vocabulary = dict([(i, s) for i, s in enumerate(vocab)])
        self.similarity_matrix = pairwise_distances(self.sklearn_vector_space, metric="cosine", n_jobs=1)

    def export(self, file_path):
        self.data_frame.to_csv(path_or_buf=file_path, sep="\t", encoding="utf-8")

    def full_text(self, doc_id):
        return self.data_frame.iloc[doc_id]["text"]

    def title(self, doc_id):
        return self.data_frame.iloc[doc_id]["title"]

    def date(self, doc_id):
        return self.data_frame.iloc[doc_id]["date"]

    def author(self, doc_id):
        aut_str = str(self.data_frame.iloc[doc_id]["author"])
        return aut_str.split(", ")

    def affiliation(self, doc_id):
        aff_str = str(self.data_frame.iloc[doc_id]["affiliation"])
        return aff_str.split(", ")

    def documents_by_author(self, author, date=None):
        ids = []
        potential_ids = range(self.size)
        if date:
            potential_ids = self.doc_ids(date)
        for i in potential_ids:
            if self.is_author(author, i):
                ids.append(i)
        return ids

    def all_authors(self):
        author_list = []
        for doc_id in range(self.size):
            author_list.extend(self.author(doc_id))
        return list(set(author_list))

    def is_author(self, author, doc_id):
        return author in self.author(doc_id)

    def docs_for_word(self, word_id):
        ids = []
        for i in range(self.size):
            vector = self.vector_for_document(i)
            if vector[word_id] > 0:
                ids.append(i)
        return ids

    def doc_ids(self, date):
        return self.data_frame[self.data_frame["date"] == date].index.tolist()

    def vector_for_document(self, doc_id):
        vector = self.sklearn_vector_space[doc_id]
        cx = vector.tocoo()
        weights = [0.0] * len(self.vocabulary)
        for row, word_id, weight in itertools.zip_longest(cx.row, cx.col, cx.data):
            weights[word_id] = weight
        return weights

    def word_for_id(self, word_id):
        return self.vocabulary.get(word_id)

    def id_for_word(self, word):
        for i, s in self.vocabulary.items():
            if s == word:
                return i
        return -1

    def similar_documents(self, doc_id, num_docs):
        similarities = [
            (d, 1.0 - self.topic_distances[doc_id][d]) for d in np.argsort(self.topic_distances[doc_id]) if d != doc_id
        ]
        return similarities[:num_docs]

    def similar_documents_by_topic_distribution(self, topic_model):
        self.topic_distances = pairwise_distances(topic_model.document_topic_matrix, metric="cosine")

    def collaboration_network(self, doc_ids=None, nx_format=False):
        nx_graph = nx.Graph(name="")
        for doc_id in doc_ids:
            authors = self.author(doc_id)
            for author in authors:
                nx_graph.add_node(author)
            for i in range(0, len(authors)):
                for j in range(i + 1, len(authors)):
                    nx_graph.add_edge(authors[i], authors[j])
        bb = nx.betweenness_centrality(nx_graph)
        nx.set_node_attributes(nx_graph, "betweenness", bb)
        if nx_format:
            return nx_graph
        else:
            return json_graph.node_link_data(nx_graph)


def save_corpus(corpus):
    with open("input/corpus", "wb") as output_file:
        dump(corpus, output_file)


def load_corpus(path):
    with open(path, "rb") as input_file:
        corpus = load(input_file)
    return corpus
