# /usr/bin/env python3

import configparser
import json
import os
import sys
from typing import Dict, Union


# bertopic-only. Absent or empty means "use BERTopicModel's default", so
# defaults live in exactly one place.
BERTOPIC_OPTIONS = (
    "embedding_model",
    "min_cluster_size",
    "cluster_selection_method",
    "reduce_outliers",
    "assignment_temperature",
    "mmr_diversity",
    "embedding_batch_size",
)


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
    # Ceiling on a chunk, in RAW words. Empty means "one chunk per text
    # object" -- the pre-chunking behaviour -- so existing configs are
    # unaffected. Raw words, not preprocessed tokens: raw words are what bound
    # the embedder's context window, and the two differ by ~5x.
    _chunk = config["TRAINING_DATA"].get("max_chunk_size", "").strip()
    training_data["max_chunk_size"] = int(_chunk) if _chunk else None

    inference_paths = [i.strip() for i in config["INFERENCE_DATA"]["text_paths"].split(",") if i.strip()]
    inference_text_object_levels = [i.strip() for i in config["INFERENCE_DATA"]["text_object_level"].split(",")]
    inference_data: Dict[str, Union[int, Dict[str, Dict[str, str]]]] = {}
    inference_data["databases"] = {
        os.path.basename(os.path.normpath(path)): {
            "db_path": path,
            "text_object_level": text_object_level,
        }
        for path, text_object_level in zip(inference_paths, inference_text_object_levels)
    }
    inference_data["min_tokens_per_doc"] = int(config["INFERENCE_DATA"]["min_tokens_per_doc"])
    # Ceiling on a chunk, in RAW words. Empty means "one chunk per text
    # object" -- the pre-chunking behaviour -- so existing configs are
    # unaffected. Raw words, not preprocessed tokens: raw words are what bound
    # the embedder's context window, and the two differ by ~5x.
    _chunk = config["INFERENCE_DATA"].get("max_chunk_size", "").strip()
    inference_data["max_chunk_size"] = int(_chunk) if _chunk else None

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
            # sklearn reads an int as an absolute document count and a float
            # as a proportion, so anything above 1 must be a count. Without
            # this an absolute floor is unreachable (min_freq = 5 raises),
            # which matters most for c-TF-IDF.
            number = float(value.strip())
            vectorization[key] = int(number) if number > 1 else number
        elif key == "ngram":
            vectorization[key] = tuple([int(v.strip()) for v in value.split(",")])
        elif key == "max_features":
            if value:
                vectorization[key] = int(value.strip())
            else:
                vectorization[key] = None
        else:
            vectorization[key] = value
    # Only keys present in the file land here; build_model forwards just those.
    topic_modeling = {}
    for key, value in config["TOPIC_MODELING"].items():
        value = value.strip()
        if key == "number_of_topics":
            # ""/"none" -> None (the clustering decides), "auto" -> merge
            # similar topics, N -> exactly N. nmf/lda require an int.
            lowered = value.lower()
            if lowered in ("", "none"):
                topic_modeling[key] = None
            elif lowered == "auto":
                topic_modeling[key] = "auto"
            else:
                topic_modeling[key] = int(value)
        elif key == "max_iter":
            # Empty is allowed for bertopic; build_model requires it otherwise.
            topic_modeling[key] = int(value) if value else None
        elif key in BERTOPIC_OPTIONS and not value:
            # Leave the key out so build_model forwards nothing; storing "" or
            # False here would override the model default.
            continue
        elif key in ("min_cluster_size", "embedding_batch_size"):
            topic_modeling[key] = int(value)
        elif key in ("assignment_temperature", "mmr_diversity"):
            topic_modeling[key] = float(value)
        elif key == "reduce_outliers":
            topic_modeling[key] = value.lower() in ("1", "true", "yes", "on")
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
    inference_db_names,
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
                    for db_name in inference_db_names
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
