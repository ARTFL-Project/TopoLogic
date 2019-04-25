#! /usr/bin/env python3

import sys

import dill as pickle

from tom_lib.visualization.visualization import Visualization
from tom_lib.structure.corpus import Corpus
from tom_lib.nlp.topic_model import NonNegativeMatrixFactorization, LatentDirichletAllocation, save_model


def main():

    if sys.argv[1] == "nmf":
        vectorization = "tfidf"
    else:
        vectorization = "tf"

    # Load and prepare a corpus
    print("Load documents from CSV")
    corpus = Corpus(
        source_file_path="input/texts_partial.csv",
        # language="french",  # language for stop words
        vectorization=vectorization,  # 'tf' (term-frequency) or 'tfidf' (term-frequency inverse-document-frequency)
        max_relative_frequency=0.95,  # ignore words which relative frequency is > than max_relative_frequency
        min_absolute_frequency=0.01,
        n_gram=2,
    )  # ignore words which absolute frequency is < than min_absolute_frequency
    print("corpus size:", corpus.size)
    print("vocabulary size:", len(corpus.vocabulary))

    # Instantiate a topic model
    if sys.argv[1] == "nmf":
        topic_model = NonNegativeMatrixFactorization(corpus)
    else:
        topic_model = LatentDirichletAllocation(corpus)

    # Estimate the optimal number of topics
    print("Estimating the number of topics...")
    viz = Visualization(topic_model)
    viz.plot_greene_metric(min_num_topics=10, max_num_topics=20, tao=10, step=1, top_n_words=10)
    viz.plot_arun_metric(min_num_topics=10, max_num_topics=20, iterations=10)
    # viz.plot_brunet_metric(min_num_topics=10, max_num_topics=30, iterations=10)


if __name__ == "__main__":
    main()

