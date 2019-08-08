# coding: utf-8
import argparse
import configparser
import os
import pickle
import random
import shutil
import json

import numpy as np
import tom_lib.utils as utils
from flask import Flask, render_template
from numpy import NaN, any
from tom_lib.utils import DBHandler
from tom_lib.nlp.topic_model import load_model
from tom_lib.structure.corpus import load_corpus

__author__ = "Clovis Gladstone"
__email__ = "clovisgladstone@uchicago.edu"


parser = argparse.ArgumentParser(description="Define files to process")
parser.add_argument("--path", dest="path", type=str, default="")

args = parser.parse_args()

config = configparser.ConfigParser()
config.read("config.ini")

NUM_TOPICS = int(config["PARAMETERS"]["number_of_topics"])
NUM_DOCS = int(config["DATA"]["num_docs"])
METATADA_FIELDS = config["DATA"]["metadata"].split(",")
data_path = args.path.replace("browser/static/", "")
print(data_path)


# Flask Web server
app = Flask(__name__, static_folder="browser/static", template_folder="browser/templates")


@app.route("/")
def index():
    return render_template(
        "index.html",
        topic_ids=range(NUM_TOPICS),
        doc_ids=range(NUM_DOCS),
        method=config["PARAMETERS"]["algorithm"],
        corpus_size=NUM_DOCS,
        vocabulary_size=config["DATA"]["num_tokens"],
        max_tf=float(config["PARAMETERS"]["max_freq"]),
        min_tf=float(config["PARAMETERS"]["min_freq"]),
        vectorization=config["PARAMETERS"]["vectorization"],
        num_topics=NUM_TOPICS,
    )


@app.route("/topic_cloud.html")
def topic_cloud():
    with open("topic_cloud.json") as input_file:
        topics = json.load(input_file)
    return render_template(
        "topic_cloud.html", title="Topic Cloud", topic_ids=range(NUM_TOPICS), topics=topics["nodes"], num_topics=NUM_TOPICS
    )


@app.route("/vocabulary.html")
def vocabulary():
    db = DBHandler("./")
    word_list = db.get_vocabulary()
    splitted_vocabulary = []
    words_per_column = int(len(word_list) / 5)
    for j in range(5):
        sub_vocabulary = []
        for l in range(j * words_per_column, (j + 1) * words_per_column):
            sub_vocabulary.append(word_list[l])
        splitted_vocabulary.append(sub_vocabulary)
    return render_template(
        "vocabulary.html",
        title="Vocabulary",
        topic_ids=range(NUM_TOPICS),
        doc_ids=range(NUM_DOCS),
        splitted_vocabulary=splitted_vocabulary,
        vocabulary_size=len(word_list),
    )


@app.route("/topic/<topic_id>.html")
def topic_details(topic_id):
    db = DBHandler("./")
    topic_data = db.get_topic_data(int(topic_id))
    doc_ids = json.loads(topic_data["docs"])
    documents = []
    for document_id, weight in doc_ids:
        metadata = db.get_metadata(document_id, METATADA_FIELDS)
        documents.append((metadata["title"].capitalize(), metadata["author"], metadata["year"], document_id, weight))

    return render_template(
        "topic.html",
        title="Topic Details",
        topic_id=topic_id,
        frequency=topic_data["frequency"],
        documents=documents,
        topic_ids=range(NUM_TOPICS),
        num_topics=NUM_TOPICS,
        doc_ids=range(NUM_DOCS),
        data_path=data_path,
        word_distribution=json.loads(topic_data["word_distribution"]),
        topic_evolution=json.loads(topic_data["topic_evolution"]),
    )


@app.route("/document/<did>.html")
def document_details(did):
    db = DBHandler("./")
    doc_data = db.get_doc_data(int(did))
    word_list = json.loads(doc_data["word_list"])
    word_list = [(w[0], w[1] * 10, w[2]) for w in word_list[:21] if w[1] > 0]
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

    topic_similarity = json.loads(doc_data["topic_similarity"])
    vector_similarity = json.loads(doc_data["vector_similarity"])
    # topic_similarity, vector_similarity = db.get_doc_similiarities(int(did))

    with open(f"browser/static/text/{did}.txt") as input_text:
        text = input_text.read()

    metadata = {field: doc_data[field] for field in METATADA_FIELDS}
    topic_distribution = json.loads(doc_data["topic_distribution"])

    return render_template(
        "document.html",
        doc_id=did,
        words=weighted_word_list,
        topic_ids=range(NUM_TOPICS),
        doc_ids=range(NUM_DOCS),
        documents=topic_similarity,
        authors=metadata["author"],
        year=metadata["year"],
        short_content=metadata["title"],
        text=text,
        title="Document Composition",
        data_path=data_path,
        sim_docs_by_word=vector_similarity,
        topic_distribution=topic_distribution,
    )


@app.route("/word/<word_id>.html")
def word_details(word_id):
    db = DBHandler("./")
    word_data = db.get_word_data(int(word_id))
    sorted_docs = json.loads(word_data["docs"])
    print(sorted_docs)
    documents = []
    for document_id, _ in sorted_docs:
        metadata = db.get_metadata(document_id, METATADA_FIELDS)
        documents.append((metadata, document_id))

    return render_template(
        "word.html",
        word_id=word_id,
        word=word_data["word"],
        topic_ids=range(NUM_TOPICS),
        doc_ids=range(NUM_DOCS),
        topic_distribution=json.loads(word_data["distribution_across_topics"]),
        documents=documents,
        title="Word Distribution",
        data_path=data_path,
    )


if __name__ == "__main__":
    # Access the browser at http://localhost:2016/
    app.run(debug=True, host="anomander.uchicago.edu", port=8080)
