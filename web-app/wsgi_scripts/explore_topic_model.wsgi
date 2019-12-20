#!/usr/bin/env python3
import argparse
import configparser
import json
import os
import pickle
import random
import re
import shutil
from collections import defaultdict
from html import unescape as unescape_html
from xml.sax.saxutils import unescape as unescape_xml

from flask_cors import CORS
import numpy as np
from flask import Flask, jsonify, request, redirect
from numpy import NaN, any, array
from topic_modeling_browser.DB import DBSearch
from sklearn.metrics.pairwise import cosine_similarity


global_config = configparser.ConfigParser()
global_config.read("/etc/topic-modeling-browser/global_settings.ini")
DATABASE = global_config["DATABASE"]
APP_PATH = global_config["WEB_APP"]["web_app_path"]

TAGS = re.compile(r"<[^>]+>")
START_TAG = re.compile(r"^[^<]*?>")

# Flask Web server
application = Flask(__name__)
CORS(application)


def read_config(table_name):
    local_config = configparser.ConfigParser()
    local_config.read(os.path.join(APP_PATH, table_name, "model_config.ini"))
    return {
        "object_level": local_config["PARAMETERS"]["object_level"],
        "topics": int(local_config["PARAMETERS"]["number_of_topics"]),
        "method": local_config["PARAMETERS"]["algorithm"],
        "corpus_size": int(local_config["DATA"]["num_docs"]),
        "vocabularySize": local_config["DATA"]["num_tokens"],
        "maxTf": float(local_config["PARAMETERS"]["max_freq"]),
        "minTf": float(local_config["PARAMETERS"]["min_freq"]),
        "vectorization": local_config["PARAMETERS"]["vectorization"].upper(),
        "metadata_fields": local_config["DATA"]["metadata"].split(","),
        "file_path": local_config["DATA"]["file_path"],
    }


def clean_text(text: str) -> str:
    """Cleaning text function which removes tags and converts entities"""
    text = TAGS.sub(" ", text)
    text = START_TAG.sub("", text)
    text = unescape_xml(text)
    text = unescape_html(text)
    text = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    text = " ".join(text.split())
    text = text.strip()
    return text


def build_label_map(min_year, max_year, interval):
    label_map = {}
    current_min = min_year
    current_max = min_year + interval
    for year in range(min_year, max_year + 1):
        if year >= current_max:
            current_min = current_max
            current_max += interval
        label_map[year] = f"{current_min}"
    return label_map


def group_distributions_over_time(distribution_over_time, label_map):
    grouped_evolution = defaultdict(float)
    for year, weight in zip(distribution_over_time["labels"], distribution_over_time["data"]):
        grouped_evolution[label_map[year]] += weight
    labels, data = zip(*grouped_evolution.items())
    return {"labels": labels, "data": data}


def response(data):
    response = jsonify(data)
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response


@application.route("/get_config/<table>")
def get_config(table):
    return response(read_config(table))


@application.route("/get_topic_ids")
def get_topic_ids():
    config = read_config(request.args["table"])
    return response(list(range(config["topics"])))


@application.route("/get_topic_data/<table>/<topic_id>")
def get_topic_data(table, topic_id):
    config = read_config(table)
    db = DBSearch(DATABASE, table, config["object_level"])
    topic_data = db.get_topic_data(int(topic_id))
    documents = []
    for document_id, weight in topic_data["docs"][:50]:
        metadata = db.get_metadata(document_id, config["metadata_fields"])
        documents.append({"doc_id": document_id, "metadata": metadata, "score": weight})
    current_topic_evolution = topic_data["topic_evolution"]
    current_topic_evolution_array = array([current_topic_evolution["data"]])
    similar_topics = []
    for topic, topic_evolution in db.get_topic_evolutions(int(topic_id)):
        similarity = float(cosine_similarity(current_topic_evolution_array, array([topic_evolution["data"]]))[0, 0])
        similar_topics.append({"topic": topic, "topic_evolution": topic_evolution, "score": similarity})
    similar_topics.sort(key=lambda x: x["score"], reverse=True)

    return response(
        {
            "word_distribution": topic_data["word_distribution"],
            "topic_evolution": current_topic_evolution,
            "documents": documents,
            "frequency": topic_data["frequency"],
            "similar_topics": similar_topics,
        }
    )


@application.route("/get_docs_in_topic_by_year/<table>/<topic_id>/<year>")
def get_docs_in_topic_by_year(table, topic_id, year):
    config = read_config(table)
    db = DBSearch(DATABASE, table, config["object_level"])
    doc_ids = db.get_doc_ids_by_metadata("year", year)
    topic_data = db.get_topic_data(int(topic_id))
    documents = []
    for doc_id, weight in topic_data["docs"]:
        if doc_id in doc_ids:
            metadata = db.get_metadata(doc_id, config["metadata_fields"])
            documents.append({"doc_id": doc_id, "metadata": metadata, "score": weight})
    return response(documents[:50])


@application.route("/get_doc_data/<table>/<philo_id>")
def get_doc_data(table, philo_id):
    config = read_config(table)
    db = DBSearch(DATABASE, table, config["object_level"])
    doc_data = db.get_doc_data(philo_id)
    word_list = [(w[0], w[1] * 10, w[2]) for w in doc_data["word_list"][:50] if w[1] > 0]
    highest_value = word_list[0][1]
    if len(word_list) > 1:
        lowest_value = word_list[-1][1]
    else:
        lowest_value = 0
    coeff = (highest_value - lowest_value) / 10
    if coeff == 0.0:
        coeff = 1.0

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

    topic_similarity = []
    for doc_id, score in doc_data["topic_similarity"]:
        doc_metadata = db.get_metadata(doc_id, config["metadata_fields"])
        topic_similarity.append({"doc_id": doc_id, "metadata": doc_metadata, "score": score})
    vector_similarity = []
    for doc_id, score in doc_data["vector_similarity"]:
        doc_metadata = db.get_metadata(doc_id, config["metadata_fields"])
        vector_similarity.append({"doc_id": doc_id, "metadata": doc_metadata, "score": score})

    metadata = {field: doc_data[field] for field in config["metadata_fields"]}
    philo_db = True  # currently hardcoded to using only PhiloLogic for getting source texts
    if philo_db is True:
        with open(os.path.join(config["file_path"], metadata["filename"]), "rb") as text_file:
            length = int(metadata["end_byte"]) - int(metadata["start_byte"])
            text_file.seek(int(metadata["start_byte"]))
            text = text_file.read(length).decode("utf8", "ignore")
            text = clean_text(text)
            if len(text) > 5000:
                text = text[:5000] + " [...]"
    else:
        text = ""

    return response(
        {
            "topic_distribution": doc_data["topic_distribution"],
            "metadata": metadata,
            "vector_sim_docs": vector_similarity[:100],
            "topic_sim_docs": topic_similarity[:100],
            "text": text,
            "words": weighted_word_list,
        }
    )


@application.route("/get_word_data/<table>/<word>")
def get_word_data(table, word):
    config = read_config(table)
    db = DBSearch(DATABASE, table, config["object_level"])
    word_data = db.get_word_data(word)
    sorted_docs = word_data["docs"]
    documents = []
    for document_id, score in sorted_docs[:50]:
        metadata = db.get_metadata(document_id, config["metadata_fields"])
        documents.append({"metadata": metadata, "doc_id": document_id, "score": score})
    return response(
        {
            "word": word,
            "word_id": word_data["word_id"],
            "topic_ids": list(range(config["topics"])),
            "topic_distribution": word_data["distribution_across_topics"],
            "documents": documents[:100],
            "similar_words_by_topic": word_data["similar_words_by_topic"][1:21],
            "similar_words_by_cooc": word_data["similar_words_by_cooc"][1:21],
        }
    )


@application.route("/get_all_field_values/<table>")
def get_all_field_values(table):
    config = read_config(table)
    db = DBSearch(DATABASE, table, config["object_level"])
    field = request.args["field"]
    if field == "word":
        field_values = db.get_vocabulary()
    else:
        frequency_filter = request.args["filter"]
        field_values = db.get_all_metadata_values(field, frequency_filter=int(frequency_filter))
    return response({"field_values": field_values, "size": len(field_values)})


@application.route("/get_field_distribution/<table>/<field>")
def get_field_distribution(table, field):
    config = read_config(table)
    db = DBSearch(DATABASE, table, config["object_level"])
    field_value = request.args["value"]
    topic_distribution = db.get_topic_distribution_by_metadata(field, field_value)
    return response({"topic_distribution": topic_distribution})


@application.route("/get_time_distributions/<table>/")
def get_time_distributions(table):
    config = read_config(table)
    db = DBSearch(DATABASE, table, config["object_level"])
    distributions_over_time = db.get_topic_distributions_over_time()
    return response({"distributions_over_time": distributions_over_time})

