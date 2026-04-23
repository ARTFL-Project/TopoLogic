#!/usr/bin/env python3

import os
import pickle
import random
from math import floor

from annoy import AnnoyIndex
from multiprocess import cpu_count
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from tqdm import tqdm


class savedTexts:
    def __init__(self, text_path):
        self.text_path = text_path

    def __iter__(self):
        files = []
        for text_collection in os.scandir(self.text_path):
            texts_dir = os.path.join(text_collection.path, "texts")
            for input_file in os.scandir(texts_dir):
                files.append((input_file.path, int(input_file.name)))
        files.sort(key=lambda x: x[1])
        for file, _ in files:
            with open(file, encoding="utf8") as input_file:
                yield input_file.read()

    def random_sample(self, proportion=0.8):
        for text_collection in os.scandir(self.text_path):
            texts_dir = os.path.join(text_collection.path, "texts")
            file_paths = [f.path for f in os.scandir(texts_dir)]
            sample_size = floor(len(file_paths) * proportion)
            for file in random.sample(file_paths, sample_size):
                with open(file, encoding="utf8") as input_file:
                    yield input_file.read()


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
    ):
        self.metadata = self.__get_metadata(source_files_path)
        self.ngram = ngram if len(ngram) == 2 else (ngram[0], ngram[0])
        self._max_relative_frequency = max_relative_frequency
        self._min_absolute_frequency = min_absolute_frequency
        self.max_features = max_features
        self.texts_to_vectorize = savedTexts(source_files_path)
        self._vectorization = vectorization

        if vectorizer is None:
            if vectorization == "tfidf":
                self.vectorizer = TfidfVectorizer(
                    ngram_range=self.ngram,
                    max_df=max_relative_frequency,
                    min_df=min_absolute_frequency,
                    max_features=max_features,
                    smooth_idf=True,
                    sublinear_tf=True,
                )
            elif vectorization == "tf":
                self.vectorizer = CountVectorizer(
                    ngram_range=self.ngram,
                    max_df=max_relative_frequency,
                    min_df=min_absolute_frequency,
                    max_features=max_features,
                )
            else:
                raise ValueError(f"Unknown vectorization type: {vectorization!r}")
            self.sklearn_vector_space = self.vectorizer.fit_transform(self.texts_to_vectorize)
        else:
            self.vectorizer = vectorizer
            self.sklearn_vector_space = self.vectorizer.transform(self.texts_to_vectorize)

        self.size = self.sklearn_vector_space.shape[0]
        self.feature_names = self.vectorizer.get_feature_names_out()
        self.annoy_index = None

    def __get_metadata(self, data_path):
        metadata = {}
        for text_collection in os.scandir(data_path):
            with open(os.path.join(text_collection.path, "metadata.pickle"), "rb") as f:
                metadata.update(pickle.load(f))
        return metadata

    def sample_corpus(self):
        self.sklearn_vector_space = self.vectorizer.transform(self.texts_to_vectorize.random_sample())

    def build_annoy_index(self):
        print("Building Annoy index of document vectors...", flush=True)
        self.annoy_index = AnnoyIndex(self.sklearn_vector_space.shape[1], "angular")
        for i, doc_vector in tqdm(
            enumerate(self.sklearn_vector_space),
            total=self.size,
            desc="Adding document vectors to Annoy index",
            leave=False,
        ):
            self.annoy_index.add_item(i, doc_vector.toarray()[0])
        self.annoy_index.build(1000, n_jobs=cpu_count() - 1)

    def similar_docs_by_vector(self, doc_id, num_docs):
        docs, scores = self.annoy_index.get_nns_by_item(doc_id, num_docs + 1, include_distances=True)
        return [(doc, score) for doc, score in zip(docs, scores) if doc != doc_id]

    def similar_docs_by_topic_distribution(self, doc_id, num_docs, topic_model):
        docs, scores = topic_model.annoy_index.get_nns_by_item(doc_id, num_docs + 1, include_distances=True)
        return [(doc, score) for doc, score in zip(docs, scores) if doc != doc_id]
