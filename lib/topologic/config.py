# /usr/bin/env python3

import configparser
import json
import os
import sys
from typing import Dict, Union


def read_config(config_path):
    """Read config file for building the topic model and associated app"""
    config = configparser.ConfigParser()
    config.read(config_path)
    training_dbs = [i.strip() for i in config["TRAINING_DATA"]["philologic_database_paths"].split(",")]
    training_db_urls = [i.strip().rstrip("/") for i in config["TRAINING_DATA"]["philologic_database_urls"].split(",")]
    training_text_object_levels = [i.strip() for i in config["TRAINING_DATA"]["text_object_level"].split(",")]
    training_data: Dict[str, Union[int, Dict[str, Dict[str, str]]]] = {}
    training_data["databases"] = {
        os.path.basename(os.path.normpath(db_path)): {
            "db_path": db_path,
            "db_url": db_url,
            "text_object_level": text_object_level,
        }
        for db_path, db_url, text_object_level in zip(training_dbs, training_db_urls, training_text_object_levels)
    }
    training_data["min_tokens_per_doc"] = int(config["TRAINING_DATA"]["min_tokens_per_doc"])

    inference_dbs = [i.strip() for i in config["INFERENCE_DATA"]["philologic_database_paths"].split(",")]
    inference_db_urls = [i.strip().rstrip("/") for i in config["INFERENCE_DATA"]["philologic_database_urls"].split(",")]
    inference_text_object_levels = [i.strip() for i in config["INFERENCE_DATA"]["text_object_level"].split(",")]
    inference_data: Dict[str, Union[int, Dict[str, Dict[str, str]]]] = {}
    inference_data["databases"] = {
        os.path.basename(os.path.normpath(db_path)): {
            "db_path": db_path,
            "db_url": db_url,
            "text_object_level": text_object_level,
        }
        for db_path, db_url, text_object_level in zip(inference_dbs, inference_db_urls, inference_text_object_levels)
    }
    inference_data["min_tokens_per_doc"] = int(config["INFERENCE_DATA"]["min_tokens_per_doc"])

    metadata_filters = {}
    for key, value in config["METADATA_FILTERS"].items():
        metadata_filters[key] = value
    preprocessing = {}
    for key, value in config["PREPROCESSING"].items():
        if key == "pos_to_keep" and value != "":
            preprocessing[key] = [i.strip() for i in value.split(",")]
        elif key == "minimum_word_length":
            preprocessing[key] = int(value)
        elif key in ("numbers", "lowercase", "stemmer", "modernize", "ascii"):
            if value.lower() == "yes" or value.lower() == "true":
                value = True
            else:
                value = False
            preprocessing[key] = value
        else:
            preprocessing[key] = value
    vectorization = {}
    for key, value in config["VECTORIZATION"].items():
        if key in ("min_freq", "max_freq"):
            vectorization[key] = float(value.strip())
        elif key == "ngram":
            vectorization[key] = tuple([int(v.strip()) for v in value.split(",")])
        elif key == "max_features":
            if value:
                vectorization[key] = int(value.strip())
            else:
                vectorization[key] = None
        else:
            vectorization[key] = value
    topic_modeling = {}
    for key, value in config["TOPIC_MODELING"].items():
        if key in ("number_of_topics", "max_iter"):
            topic_modeling[key] = int(value.strip())
        else:
            topic_modeling[key] = value
    topics_over_time = {}
    for key, value in config["TOPICS_OVER_TIME"].items():
        if key == "topics_over_time_interval":
            if value not in ("1", "10", "25", "50", "100"):
                print("topics_over_time_interval value invalid: you need to set it to 1, 10, 25, 50, or 100")
                sys.exit(1)
            topics_over_time[key] = int(value)
        else:
            try:
                topics_over_time[key] = int(value)
            except ValueError:
                topics_over_time[key] = None
    return (
        training_data,
        inference_data,
        metadata_filters,
        config["DATABASE"]["database_name"],
        preprocessing,
        vectorization,
        topic_modeling,
        topics_over_time,
    )


def write_app_config(db_path, database_name, server_name, philologic_links, start_date, end_date, interval):
    """Write app config used to build topic modeling browser web app"""
    with open(os.path.join(db_path, "appConfig.json"), "w") as app_config:
        json.dump(
            {
                "webServer": "Apache",
                "apiServer": os.path.join(server_name, "topologic-api"),
                "philoLogicUrls": philologic_links,
                "databaseName": database_name,
                "appPath": os.path.join("topologic", database_name),
                "metadataFields": [
                    {"field": "author", "style": {}, "link": False},
                    {"field": "title", "style": {"font-style": "italic"}, "link": True},
                    {"field": "year", "style": {}, "link": False},
                ],
                "citations": {
                    db_name: [
                        {"field": "author", "style": {"font-variant": "small-caps"}, "link": False},
                        {"field": "title", "style": {"font-style": "italic"}, "link": True},
                        {"field": "year", "style": {}, "link": False},
                    ]
                    for db_name in philologic_links.keys()
                },
                "timeSeriesConfig": {"interval": interval, "startDate": start_date, "endDate": end_date},
                "metadataDistributions": [{"label": "author", "field": "author", "filterFrequency": 1}],
            },
            app_config,
            indent=4,
        )
