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

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

# from flask_cors import CORS
# from flask import Flask, jsonify, request, redirect
from topologic.DB import DBSearch
from topologic import read_config


global_config = configparser.ConfigParser()
global_config.read("/etc/topologic/global_settings.ini")
DATABASE = global_config["DATABASE"]
APP_PATH = global_config["WEB_APP"]["web_app_path"]

TAGS = re.compile(r"<[^>]+>")
START_TAG = re.compile(r"^[^<]*?>")

# FastAPI application server
app = FastAPI()
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)


def read_model_config(table_name):
    local_config = configparser.ConfigParser()
    local_config.read(os.path.join(APP_PATH, table_name, "model_config.ini"))
    return {
        "object_level": local_config["PREPROCESSING"]["text_object_level"],
        "maxTf": float(local_config["VECTORIZATION"]["max_freq"]),
        "minTf": float(local_config["VECTORIZATION"]["min_freq"]),
        "vectorization": local_config["VECTORIZATION"]["vectorization"].upper(),
        "topics": int(local_config["TOPIC_MODELING"]["number_of_topics"]),
        "method": local_config["TOPIC_MODELING"]["algorithm"],
        "topic_over_time_interval": int(local_config["TOPICS_OVER_TIME"]["topics_over_time_interval"]),
        "metadata_fields": local_config["DATA"]["metadata"].split(","),
        "file_path": local_config["DATA"]["file_path"],
        "corpus_size": int(local_config["DATA"]["num_docs"]),
        "vocabularySize": local_config["DATA"]["num_tokens"],
    }


def group_distributions_over_time(distribution_over_time, label_map):
    grouped_evolution = defaultdict(float)
    for year, weight in zip(distribution_over_time["labels"], distribution_over_time["data"]):
        grouped_evolution[label_map[year]] += weight
    labels, data = zip(*grouped_evolution.items())
    return {"labels": labels, "data": data}


@app.get("/")
def root():
    return "HEllo"


@app.get("/get_config/{table}")
def get_config(table):
    return read_model_config(table)


@app.get("/get_topic_ids")
def get_topic_ids(table: str):
    config = read_model_config(table)
    return list(range(config["topics"]))


@app.get("/get_topic_data/{table}/{topic_id}")
def get_topic_data(table, topic_id):
    config = read_model_config(table)
    db = DBSearch(DATABASE, table, config["object_level"])
    topic_data = db.get_topic_data(int(topic_id), config["metadata_fields"])
    return topic_data


@app.get("/get_docs_in_topic_by_year/{table}/{topic_id}/{year}")
def get_docs_in_topic_by_year(table, topic_id, year):
    config = read_model_config(table)
    db = DBSearch(DATABASE, table, config["object_level"])
    documents = db.get_topic_data_by_year(
        int(topic_id), year, config["topic_over_time_interval"], config["metadata_fields"], 50
    )
    return documents


@app.get("/get_doc_data/{table}/{philo_id}")
def get_doc_data(table, philo_id):
    config = read_model_config(table)
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

    return {
        "topic_distribution": doc_data["topic_distribution"],
        "metadata": metadata,
        "vector_sim_docs": vector_similarity[:100],
        "topic_sim_docs": topic_similarity[:100],
        "words": weighted_word_list,
    }


@app.get("/get_word_data/{table}/{word}")
def get_word_data(table, word):
    config = read_model_config(table)
    db = DBSearch(DATABASE, table, config["object_level"])
    word_data = db.get_word_data(word)
    if word_data is None:
        return {
            "word": word,
            "word_id": None,
            "topic_ids": [],
            "topic_distribution": None,
            "documents": [],
            "similar_words_by_topic": None,
            "similar_words_by_cooc": None,
        }
    sorted_docs = word_data["docs"]
    documents = []
    for document_id, score in sorted_docs[:50]:
        metadata = db.get_metadata(document_id, config["metadata_fields"])
        documents.append({"metadata": metadata, "doc_id": document_id, "score": score})
    return {
        "word": word,
        "word_id": word_data["word_id"],
        "topic_ids": list(range(config["topics"])),
        "topic_distribution": word_data["distribution_across_topics"],
        "documents": documents[:100],
        "similar_words_by_topic": word_data["similar_words_by_topic"][1:21],
        "similar_words_by_cooc": word_data["similar_words_by_cooc"][1:21],
    }


@app.get("/get_all_field_values/{table}")
def get_all_field_values(table, field: str, filter: int):
    config = read_model_config(table)
    db = DBSearch(DATABASE, table, config["object_level"])
    if field == "word":
        field_values = db.get_vocabulary()
    else:
        field_values = db.get_all_metadata_values(field, frequency_filter=filter)
    return {"field_values": field_values, "size": len(field_values)}


@app.get("/get_field_distribution/{table}/{field}")
def get_field_distribution(table, field, value: str):
    config = read_model_config(table)
    db = DBSearch(DATABASE, table, config["object_level"])
    topic_distribution = db.get_topic_distribution_by_metadata(field, value)
    return {"topic_distribution": topic_distribution}


@app.get("/get_time_distributions/{table}/")
def get_time_distributions(table):
    config = read_model_config(table)
    db = DBSearch(DATABASE, table, config["object_level"])
    distributions_over_time = db.get_topic_distributions_over_time()
    return {"distributions_over_time": distributions_over_time}

