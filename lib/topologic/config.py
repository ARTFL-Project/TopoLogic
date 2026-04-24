# /usr/bin/env python3

import configparser
import json
import os
import sys
from typing import Dict, Union


def read_config(config_path):
    """Read config file for building the topic model and associated app"""
    config = configparser.ConfigParser()
    config.read(config_path, encoding="utf-8")
    training_paths = [i.strip() for i in config["TRAINING_DATA"]["text_paths"].split(",") if i.strip()]
    training_text_object_levels = [i.strip() for i in config["TRAINING_DATA"]["text_object_level"].split(",")]
    training_data: Dict[str, Union[int, Dict[str, Dict[str, str]]]] = {}
    training_data["databases"] = {
        os.path.basename(os.path.normpath(path)): {
            "db_path": path,
            "text_object_level": text_object_level,
        }
        for path, text_object_level in zip(training_paths, training_text_object_levels)
    }
    training_data["min_tokens_per_doc"] = int(config["TRAINING_DATA"]["min_tokens_per_doc"])

    inference_paths = [i.strip() for i in config["INFERENCE_DATA"]["text_paths"].split(",") if i.strip()]
    inference_raw_urls = [
        i.strip().rstrip("/")
        for i in config["INFERENCE_DATA"].get("philologic_database_urls", "").split(",")
    ]
    # Pad URL list so a shorter list (or empty) still aligns by position.
    inference_urls = inference_raw_urls + [""] * max(0, len(inference_paths) - len(inference_raw_urls))
    inference_text_object_levels = [i.strip() for i in config["INFERENCE_DATA"]["text_object_level"].split(",")]
    inference_data: Dict[str, Union[int, Dict[str, Dict[str, str]]]] = {}
    inference_data["databases"] = {
        os.path.basename(os.path.normpath(path)): {
            "db_path": path,
            "db_url": db_url,
            "text_object_level": text_object_level,
        }
        for path, db_url, text_object_level in zip(inference_paths, inference_urls, inference_text_object_levels)
    }
    inference_data["min_tokens_per_doc"] = int(config["INFERENCE_DATA"]["min_tokens_per_doc"])

    metadata_filters = {}
    for key, value in config["METADATA_FILTERS"].items():
        metadata_filters[key] = value
    preprocessing = {}
    for key, value in config["PREPROCESSING"].items():
        if key == "pos_to_keep" and value != "":
            preprocessing[key] = [i.strip() for i in value.split(",")]
        elif key == "ner_to_keep" and value != "":
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
    if "ner_to_keep" not in preprocessing:
        preprocessing["ner_to_keep"] = ""
        print(
            "You are using on older version of the config file. You can now filter on NER. See the ner_to_keep variable in updated config file found in /var/lib/topologic/config/topologic_config.ini."
        )
    if not preprocessing.get("language_model") and preprocessing["pos_to_keep"] or preprocessing.get("ner_to_keep"):
        if "language_model" not in preprocessing:
            print(
                "You are using on older version of the config file. Please add the language_model variable and a corresponding value under the PREPROCESSING section.\n"
            )
            sys.exit(1)
        elif preprocessing["language_model"] == "":
            print(
                "You need to specify a a SpaCy language model in the config file if you want to keep specific POS or NER tags."
            )
        print(
            """For a list of SpaCy Models to use, see https://spacy.io/models/. Make sure to use the full name of the model, including the language code. For example, en_core_web_sm for English.\nYou will also need to ensure the model is installed within the topologic environment."""
        )
        sys.exit(1)
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
    topic_labeling = {
        "enabled": False,
        "model": "google/gemma-4-E2B-it",
        "language": "English",
    }
    if config.has_section("TOPIC_LABELING"):
        section = config["TOPIC_LABELING"]
        raw_enabled = section.get("enabled", "false").strip().lower()
        topic_labeling["enabled"] = raw_enabled in ("1", "true", "yes", "on")
        if section.get("model", "").strip():
            topic_labeling["model"] = section["model"].strip()
        if section.get("language", "").strip():
            topic_labeling["language"] = section["language"].strip()

    return (
        training_data,
        inference_data,
        metadata_filters,
        config["DATABASE"]["database_name"],
        preprocessing,
        vectorization,
        topic_modeling,
        topics_over_time,
        topic_labeling,
    )


def write_app_config(
    db_path,
    database_name,
    server_name,
    proxy_path,
    philologic_links,
    start_date,
    end_date,
    interval,
    time_series_enabled=True,
):
    """Write app config used to build topic modeling browser web app.

    Splits into two files:
    - appConfig.build.json: values vite bakes into the bundle (just appPath).
    - appConfig.json: everything else, fetched at runtime so edits take effect
      on page reload without rebuilding.
    """
    app_path = os.path.join(proxy_path, "topologic", database_name)
    with open(os.path.join(db_path, "appConfig.build.json"), "w") as build_config:
        json.dump({"appPath": app_path, "devServerConfig": {}}, build_config, indent=4)
    with open(os.path.join(db_path, "appConfig.json"), "w") as app_config:
        json.dump(
            {
                "apiServer": os.path.join(server_name, proxy_path, "topologic-api"),
                "philoLogicUrls": philologic_links,
                "displayName": database_name,
                "metadataFields": [
                    {"field": "author", "style": {}, "link": False},
                    {"field": "title", "style": {"font-style": "italic"}, "link": True},
                    {"field": "year", "style": {}, "link": False},
                ],
                "citations": {
                    db_name: [
                        {
                            "field": "author",
                            "style": {"font-variant": "small-caps"},
                            "link": False,
                        },
                        {
                            "field": "title",
                            "style": {"font-style": "italic"},
                            "link": True,
                        },
                        {"field": "year", "style": {}, "link": False},
                    ]
                    for db_name in philologic_links.keys()
                },
                "timeSeriesConfig": {
                    "enabled": time_series_enabled,
                    "interval": interval,
                    "startDate": start_date,
                    "endDate": end_date,
                },
                "metadataDistributions": [{"label": "author", "field": "author", "filterFrequency": 1}],
            },
            app_config,
            indent=4,
        )
