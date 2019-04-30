# coding: utf-8
import argparse
import os
import pickle
import random
import shutil

from flask import Flask, render_template
from numpy import NaN, any
import numpy as np

import tom_lib.utils as utils
from tom_lib.nlp.topic_model import load_model
from tom_lib.structure.corpus import load_corpus

__author__ = "Clovis Gladstone"
__email__ = "clovisgladstone@uchicago.edu"


parser = argparse.ArgumentParser(description="Define files to process")
parser.add_argument("--path", dest="path", type=str, default="")

args = parser.parse_args()

corpus = load_corpus(os.path.join(args.path, "corpus"))
vectorization = corpus._vectorization
max_tf = corpus._max_relative_frequency
min_tf = corpus._min_absolute_frequency

topic_model = load_model(os.path.join(args.path, "model"))
num_topics = topic_model.nb_topics
# Associate documents with topics
topic_associations = topic_model.documents_per_topic()
data_path = args.path.replace("browser/static/", "")
print(data_path)


# Flask Web server
app = Flask(__name__, static_folder="browser/static", template_folder="browser/templates")


@app.route("/")
def index():
    return render_template(
        "index.html",
        topic_ids=range(topic_model.nb_topics),
        doc_ids=range(corpus.size),
        method=type(topic_model).__name__,
        corpus_size=corpus.size,
        vocabulary_size=len(corpus.vectorizer.vocabulary_),
        max_tf=max_tf,
        min_tf=min_tf,
        vectorization=vectorization,
        num_topics=num_topics,
    )


@app.route("/topic_cloud.html")
def topic_cloud():
    return render_template(
        "topic_cloud.html",
        title="Topic Cloud",
        topic_ids=range(topic_model.nb_topics),
        doc_ids=range(corpus.size),
        data_path=data_path,
        num_topics=topic_model.nb_topics,
    )


@app.route("/vocabulary.html")
def vocabulary():
    word_list = []
    for i in range(len(corpus.vectorizer.vocabulary_)):
        word_list.append((i, corpus.word_for_id(i)))
    splitted_vocabulary = []
    words_per_column = int(len(corpus.vectorizer.vocabulary_) / 5)
    for j in range(5):
        sub_vocabulary = []
        for l in range(j * words_per_column, (j + 1) * words_per_column):
            sub_vocabulary.append(word_list[l])
        splitted_vocabulary.append(sub_vocabulary)
    return render_template(
        "vocabulary.html",
        title="Vocabulary",
        topic_ids=range(topic_model.nb_topics),
        doc_ids=range(corpus.size),
        splitted_vocabulary=splitted_vocabulary,
        vocabulary_size=len(word_list),
    )


@app.route("/topic/<tid>.html")
def topic_details(tid):
    ids = topic_model.top_documents(int(tid))
    documents = []
    for document_id, weight in ids:
        document_array = corpus.sklearn_vector_space[document_id]
        positive_values = any(document_array.todense() > 0)
        if positive_values:
            documents.append(
                (
                    corpus.title(document_id).capitalize(),
                    ", ".join(corpus.author(document_id)),
                    corpus.date(document_id),
                    document_id,
                    weight,
                )
            )
    return render_template(
        "topic.html",
        title="Topic Details",
        topic_id=tid,
        frequency=round(topic_model.topic_frequency(int(tid)) * 100, 2),
        documents=documents,
        topic_ids=range(topic_model.nb_topics),
        num_topics=topic_model.nb_topics,
        doc_ids=range(corpus.size),
        data_path=data_path,
    )


@app.route("/document/<did>.html")
def document_details(did):
    vector = corpus.sklearn_vector_space[int(did)].toarray()[0]
    word_list = []
    for word_id, weight in enumerate(vector):
        if weight > 0:
            word_list.append((corpus.word_for_id(word_id), weight * 10, word_id))
    word_list.sort(key=lambda x: x[1])
    word_list.reverse()
    word_list = [w for w in word_list[:21] if w[1] > 0]
    highest_value = word_list[0][1]
    if len(word_list) > 1:
        lowest_value = word_list[-1][1]
    else:
        lowest_value = 0
    coeff = (highest_value - lowest_value) / 10

    def adjust_weight(weight):
        adjusted_weight = round((weight - lowest_value) / coeff, 0)
        try:
            adjusted_weight = int(adjusted_weight)
        except ValueError:
            adjusted_weight = 0
        return adjusted_weight

    adjusted_word_list = [(w[0], adjust_weight(w[1]), w[2]) for w in word_list]
    color_codes = {
        10: "rgb(26, 114, 159)",
        9: "rgba(26,114,159, .95)",
        8: "rgba(26,114,159, .9)",
        7: "rgba(26,114,159, .85)",
        6: "rgba(26,114,159, .8)",
        5: "rgba(26,114,159, .75)",
        4: "rgba(26,114,159, .7)",
        3: "rgba(26,114,159, .65)",
        2: "rgba(26,114,159, .6)",
        1: "rgba(26,114,159, .55)",
        0: "rgba(26,114,159, .5)",
    }

    weighted_word_list = [(w[0], w[1] / 10, w[2], color_codes[w[1]]) for w in adjusted_word_list]
    weighted_word_list.sort(key=lambda x: x[0])
    documents = []
    for another_doc, score in corpus.similar_documents(int(did), 5):
        documents.append(
            (
                corpus.title(another_doc).capitalize(),
                ", ".join(corpus.author(another_doc)),
                corpus.date(another_doc),
                another_doc,
                round(score, 3),
            )
        )
    sim_docs_by_word = []
    doc_id = int(did)
    for another_doc, score in [
        (d, 1.0 - corpus.similarity_matrix[doc_id][d])
        for d in np.argsort(corpus.similarity_matrix[doc_id])
        if d != doc_id
    ][:5]:
        sim_docs_by_word.append(
            (
                corpus.title(another_doc).capitalize(),
                ", ".join(corpus.author(another_doc)),
                corpus.date(another_doc),
                another_doc,
                round(score, 3),
            )
        )
    with open(f"browser/static/text/{did}.txt") as input_text:
        text = input_text.read()
    return render_template(
        "document.html",
        doc_id=did,
        words=weighted_word_list,
        topic_ids=range(topic_model.nb_topics),
        doc_ids=range(corpus.size),
        documents=documents,
        authors=", ".join(corpus.author(int(did))),
        year=corpus.date(int(did)),
        short_content=corpus.title(int(did)),
        text=text,
        title="Document Composition",
        data_path=data_path,
        sim_docs_by_word=sim_docs_by_word,
    )


@app.route("/word/<wid>.html")
def word_details(wid):
    documents = []
    try:
        wid = int(wid)
    except ValueError:
        wid = corpus.vectorizer.vocabulary_[wid]
    for document_id in corpus.docs_for_word(wid):
        documents.append(
            (
                corpus.title(document_id).capitalize(),
                ", ".join(corpus.author(document_id)),
                corpus.date(document_id),
                document_id,
            )
        )
    return render_template(
        "word.html",
        word_id=str(wid),
        word=topic_model.corpus.word_for_id(wid),
        topic_ids=range(topic_model.nb_topics),
        doc_ids=range(corpus.size),
        documents=documents,
        title="Word Distribution",
        data_path=data_path,
    )


if __name__ == "__main__":
    # Access the browser at http://localhost:2016/
    app.run(debug=True, host="anomander.uchicago.edu", port=8080)
