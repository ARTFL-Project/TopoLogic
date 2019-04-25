# coding: utf-8
import os
import pickle
import random
import shutil
from numpy import NaN

from flask import Flask, render_template

import tom_lib.utils as utils
from tom_lib.nlp.topic_model import load_model
from tom_lib.structure.corpus import load_corpus

__author__ = "Adrien Guille"
__email__ = "adrien.guille@univ-lyon2.fr"

# Flask Web server
app = Flask(__name__, static_folder="browser/static", template_folder="browser/templates")

corpus = load_corpus("input/corpus")
vectorization = corpus._vectorization
max_tf = corpus._max_relative_frequency
min_tf = corpus._min_absolute_frequency

topic_model = load_model("input/model")
num_topics = topic_model.nb_topics
# Associate documents with topics
topic_associations = topic_model.documents_per_topic()


@app.route("/")
def index():
    return render_template(
        "index.html",
        topic_ids=range(topic_model.nb_topics),
        doc_ids=range(corpus.size),
        method=type(topic_model).__name__,
        corpus_size=corpus.size,
        vocabulary_size=len(corpus.vocabulary),
        max_tf=max_tf,
        min_tf=min_tf,
        vectorization=vectorization,
        num_topics=num_topics,
    )


@app.route("/topic_cloud.html")
def topic_cloud():
    return render_template(
        "topic_cloud.html", title="Topic Cloud", topic_ids=range(topic_model.nb_topics), doc_ids=range(corpus.size)
    )


@app.route("/vocabulary.html")
def vocabulary():
    word_list = []
    for i in range(len(corpus.vocabulary)):
        word_list.append((i, corpus.word_for_id(i)))
    splitted_vocabulary = []
    words_per_column = int(len(corpus.vocabulary) / 5)
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
    ids = topic_associations[int(tid)]
    documents = []
    for document_id in ids:
        documents.append(
            (
                corpus.title(document_id).capitalize(),
                ", ".join(corpus.author(document_id)),
                corpus.date(document_id),
                document_id,
            )
        )
    return render_template(
        "topic.html",
        title="Topic Details",
        topic_id=tid,
        frequency=round(topic_model.topic_frequency(int(tid)) * 100, 2),
        documents=documents,
        topic_ids=range(topic_model.nb_topics),
        doc_ids=range(corpus.size),
    )


@app.route("/document/<did>.html")
def document_details(did):
    vector = topic_model.corpus.vector_for_document(int(did))
    word_list = []
    for a_word_id in range(len(vector)):
        if vector[a_word_id] > 0:
            word_list.append((corpus.word_for_id(a_word_id), vector[a_word_id] * 10, a_word_id))
            print(vector[a_word_id])
    word_list.sort(key=lambda x: x[1])
    word_list.reverse()
    word_list = [w for w in word_list[:21] if w[1] > 0]
    highest_value = word_list[0][1]
    lowest_value = word_list[-1][1]
    coeff = (highest_value - lowest_value) / 10

    def adjust_weight(weight):
        adjusted_weight = round((weight - lowest_value) / coeff, 0)
        try:
            adjusted_weight = int(adjusted_weight)
        except ValueError:
            adjusted_weight = 0
        return adjusted_weight

    adjusted_word_list = [(w[0], adjust_weight(w[1]), w[2]) for w in word_list]
    print(highest_value, lowest_value, coeff)
    color_codes = {
        10: "#2A90DC",
        9: "#2AA9DC",
        8: "#2ABCDC",
        7: "#2ACCDC",
        6: "#2ADCCC",
        5: "#2ADCB6",
        4: "#2ADC93",
        3: "#2ADC7E",
        2: "#2ADC70",
        1: "#2ADC50",
        0: "#2ACB40",
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
    )


@app.route("/word/<wid>.html")
def word_details(wid):
    documents = []
    try:
        wid = int(wid)
    except ValueError:
        wid = corpus.id_for_word(wid)
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
    )


if __name__ == "__main__":
    # Access the browser at http://localhost:2016/
    app.run(debug=True, host="anomander.uchicago.edu", port=8080)
