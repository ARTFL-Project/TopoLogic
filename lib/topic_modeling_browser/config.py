# /usr/bin/env python3

import configparser
import json
import os


def read_config(config_path):
    """Read config file for building the topic model and associated app"""
    config = configparser.ConfigParser()
    config.read(config_path)
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
        elif key == "min_tokens_per_doc":
            vectorization[key] = int(value.strip())
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
    return config["SOURCE_DATA"], config["DATABASE"]["database_name"], preprocessing, vectorization, topic_modeling


def write_app_config(philologic_link, db_path, database_name, server_name, start_date, end_date):
    """Write app config used to build topic modeling browser web app"""
    with open(os.path.join(db_path, "appConfig.json"), "w") as app_config:
        json.dump(
            {
                "webServer": "Apache",
                "apiServer": os.path.join(server_name, "topic-modeling-browser-api"),
                "philoLogicUrl": philologic_link,
                "databaseName": database_name,
                "appPath": os.path.join("topic-modeling-browser", database_name),
                "metadataFields": [
                    {"field": "author", "style": {}, "link": False},
                    {"field": "title", "style": {"font-style": "italic"}, "link": True},
                    {"field": "year", "style": {}, "link": False},
                ],
                "timeSeriesConfig": {"interval": 1, "startDate": start_date, "endDate": end_date},
                "metadataDistributions": [{"label": "author", "field": "author"}],
            },
            app_config,
            indent=4,
        )
