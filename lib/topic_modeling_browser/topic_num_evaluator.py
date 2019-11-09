#!/usr/bin/env python3

import matplotlib as mpl

mpl.use("Agg")  # To be able to create figures on a headless server (no DISPLAY variable)
import matplotlib.pyplot as plt
import numpy as np
from tqdm import tqdm
from joblib import load
from multiprocess import Pool
from topic_modeling_browser.topic_model import NonNegativeMatrixFactorization, LatentDirichletAllocation


def myjaccard(r_i, r_j):
    return len(set.intersection(set(r_i), r_j)) / float(len(set.union(set(r_i), r_j)))


def average_jaccard(r_i, r_j):
    if not r_i or not r_j:
        raise Exception("Ranked lists should have at least one element.")
    if len(r_i) != len(r_j):
        raise Exception("Both ranked term list should have the same dimension.")
    jacc_sum = [myjaccard(r_i[: d + 1], r_j[: d + 1]) for d in range(len(r_i))]
    return sum(jacc_sum) / float(len(r_i))


def jaccard_similarity_matrix(s_x, s_y):
    k = len(s_x)
    m = np.zeros((k, k))
    for i in range(k):
        for j in range(k):
            m[i, j] = average_jaccard(s_x[i], s_y[j])
    return m


def agreement_score(s_x, s_y):
    if not s_x or not s_y:
        raise Exception("The sets of ranked lists should have at least one element.")
    if len(s_x) != len(s_y):
        raise Exception("Both ranked term list sets should have the same dimension.")
    k = len(s_x)
    m = jaccard_similarity_matrix(s_x, s_y)
    agree_sum = [m[i,].max() for i in range(k)]
    return sum(agree_sum) / k


def topic_num_evaluator(
    corpus_path, min_num_topics, max_num_topics, algorithm, step=1, top_n_words=10, iterations=10, workers=4
):
    """
        Implements Greene metric to compute the optimal number of topics. Taken from How Many Topics?
        Stability Analysis for Topic Models from Greene et al. 2014.
        :param step:
        :param min_num_topics: Minimum number of topics to test
        :param max_num_topics: Maximum number of topics to test
        :param top_n_words: Top n words for topic to use
        :param iterations: Number of sampled models to build
        :return: A list of len (max_num_topics - min_num_topics) with the stability of each tested k
        """

    def inner_evaluator(k):
        corpus = load(corpus_path)
        if algorithm == "nmf":
            model = NonNegativeMatrixFactorization
        else:
            model = LatentDirichletAllocation
        topic_model = model(corpus)
        topic_model.infer_topics(k)
        reference_rank = [list(zip(*topic_model.top_words(i, top_n_words)))[0] for i in range(k)]
        agreement_score_list = []
        for t in range(iterations):
            corpus.sample_corpus()
            current_model = model(corpus)
            current_model.infer_topics(k)
            tao_rank = [next(zip(*current_model.top_words(i, top_n_words))) for i in range(k)]
            agreement_score_list.append(agreement_score(reference_rank, tao_rank))
        return k, np.mean(agreement_score_list)

    steps = list(range(min_num_topics, max_num_topics + 1, step))
    stability = []
    with tqdm(total=len(steps), smoothing=0, leave=False, desc="Evaluating topic numbers") as pbar:
        with Pool(workers) as pool:
            for result in pool.imap_unordered(inner_evaluator, steps):
                stability.append(result)
                pbar.update()
    stability = [i for _, i in sorted(stability, key=lambda x: x[0])]
    plt.figure(figsize=(8, 6), dpi=100)
    plt.clf()
    plt.plot(np.arange(min_num_topics, max_num_topics + 1, step), stability)
    plt.title("Greene et al. metric")
    plt.xlabel("number of topics")
    plt.ylabel("stability")
    plt.savefig("evaluation_output/greene.png")
    with open("evaluation_output/greene.tsv", "w") as output_file:
        output_file.write("k\tgreene_value\n")
        for idx, range_i in enumerate(np.arange(min_num_topics, max_num_topics + 1, step)):
            output_file.write("{0}\t{1}\n".format(range_i, stability[idx]))
