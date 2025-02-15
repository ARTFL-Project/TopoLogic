#!/usr/bin/env python3

import argparse
import configparser
import gc
import os
import pickle
import time

from joblib import dump
from philologic.runtime.DB import DB
from text_preprocessing import PreProcessor, Token
from topologic import (
    Corpus,
    LatentDirichletAllocation,
    NonNegativeMatrixFactorization,
    max_year_normalizer,
    read_config,
    topic_num_evaluator,
    write_app_config,
    year_normalizer,
)
from topologic.DB import DBHandler

GLOBAL_CONFIG = configparser.ConfigParser()
GLOBAL_CONFIG.read("/etc/topologic/global_settings.ini")

OBJECT_LEVELS = {"doc": 1, "div1": 2, "div2": 3, "div3": 4, "para": 5}


def parse_args():
    parser = argparse.ArgumentParser(description="Define files to process")
    parser.add_argument("--config", help="Configuration file", default="", type=str)
    parser.add_argument(
        "--data_output",
        help="path to local data to be saved during processing",
        default="./temp_preprocessed_data",
        type=str,
    )
    parser.add_argument(
        "--workers",
        help="How many threads or cores to use for preprocessing and modeling",
        type=int,
        default=4,
    )
    parser.add_argument(
        "--preprocessed_data_path",
        help="skips preprocessing, decompresses preprocessed data from this path, and uses it for model building",
        type=str,
    )
    parser.add_argument(
        "--evaluate",
        help="Evaluate topic model. No topic models or web app will be saved",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--min_num_topics",
        help="minimum number of topics for evaluation",
        type=int,
        default=10,
    )
    parser.add_argument(
        "--max_num_topics",
        help="maximum number of topics for evaluation",
        type=int,
        default=20,
    )
    parser.add_argument(
        "--debug",
        help="debug mode: temp file in /tmp will not be deleted.",
        action="store_true",
        default=False,
    )
    args = parser.parse_args()
    return args


def main(args):
    if args.config == "":
        print("No configuration file provided, exiting...")
        exit()
    (
        training_config,
        inference_config,
        metadata_filters,
        database_name,
        prep_config,
        vector_config,
        model_config,
        topics_over_time,
    ) = read_config(args.config)
    training_texts_path = os.path.join(args.data_output, "training/")
    inference_texts_path = os.path.join(args.data_output, "inference/")
    if os.path.exists(args.data_output) is True and args.preprocessed_data_path is None:
        os.system(f"rm -rf {args.data_output}")
        os.system(f"mkdir -p {inference_texts_path}")
        os.system(f"mkdir -p {training_texts_path}")

    if args.preprocessed_data_path is None:
        print("## PROCESSING DATA ##", flush=True)
        prepare_data(
            prep_config,
            training_config,
            training_texts_path,
            inference_config,
            inference_texts_path,
            metadata_filters,
        )
    else:
        # Decompress preprocessed data
        os.system(f"tar -xzf {args.preprocessed_data_path}")
        training_texts_path = os.path.join(args.data_output, "training/")
        inference_texts_path = os.path.join(args.data_output, "inference/")

    topic_model, full_corpus, training_corpus = build_model(
        training_texts_path,
        inference_texts_path,
        training_config,
        inference_config,
        algorithm=model_config["algorithm"],
        number_of_topics=model_config["number_of_topics"],
        max_iter=model_config["max_iter"],
        vectorization=vector_config["vectorization"],
        max_freq=vector_config["max_freq"],
        min_freq=vector_config["min_freq"],
        max_features=vector_config["max_features"] or None,
        ngram=vector_config["ngram"],
        evaluate=args.evaluate,
    )

    if args.evaluate is False:
        build_web_app(
            args.config,
            inference_config,
            database_name,
            topic_model,
            full_corpus,
            topics_over_time,
        )
    else:
        print("Estimating the number of topics...")
        corpus_path = os.path.join(args.data_output, "corpus")
        dump(training_corpus, corpus_path)
        os.system("mkdir -p ./evaluation_output")
        topic_num_evaluator(
            corpus_path,
            args.min_num_topics,
            args.max_num_topics,
            model_config["algorithm"],
            iterations=10,
            step=1,
            top_n_words=10,
            workers=args.workers,
        )

    if args.debug is False:
        os.system(f"rm -rf {args.data_output}")


def get_file_list(data_path, metadata_filters, object_level, word_length):
    philo_db = DB(data_path)
    query_string = "." * word_length + "+"
    hits = philo_db.query(
        qs=query_string,
        method="",
        method_arg="",
        limit="",
        sort_order=["rowid"],
        raw_results=True,
        **metadata_filters,
    )
    hits.finish()
    philo_ids = {" ".join(map(str, hit[: OBJECT_LEVELS[object_level]])) for hit in hits}
    file_list = {os.path.join(data_path, f"words_and_philo_ids/{hit.split()[0]}.lz4") for hit in philo_ids}
    return file_list, philo_ids


def dictionary_filter(dictionary_file: str, preprocessor: PreProcessor):
    dictionary = set()
    if dictionary_file:
        with open(dictionary_file, encoding="utf8") as dico:
            for word in dico:
                dictionary.add(word.strip())
    return dictionary


def prepare_data(
    prep_config,
    training_config,
    training_texts_path,
    inference_config,
    inference_texts_path,
    metadata_filters,
):
    print("Processing training data...", flush=True)
    count = 0
    pos = 0
    for db_name, db_config in training_config["databases"].items():
        count += 1
        preproc = PreProcessor(
            text_object_type=db_config["text_object_level"],
            language=prep_config["language"],
            language_model=prep_config["language_model"],
            stemmer=prep_config["stemmer"],
            lemmatizer=prep_config["lemmatizer"],
            modernize=prep_config["modernize"],
            lowercase=prep_config["lowercase"],
            strip_numbers=prep_config["numbers"],
            stopwords=prep_config["stopwords"],
            pos_to_keep=prep_config["pos_to_keep"],
            ner_to_keep=prep_config["ner_to_keep"],
            ascii=prep_config["ascii"],
            min_word_length=prep_config["minimum_word_length"],
            is_philo_db=True,
            workers=args.workers,
            progress=False,
        )
        dictionary = dictionary_filter((prep_config["dictionary"]), preproc)
        philo_ids = set()
        if metadata_filters:
            file_list, philo_ids = get_file_list(
                os.path.join(db_config["db_path"], "data"),
                metadata_filters,
                db_config["text_object_level"],
                prep_config["minimum_word_length"],
            )
            file_count = len(file_list)
        else:
            file_list = [f.path for f in os.scandir(os.path.join(db_config["db_path"], "data/words_and_philo_ids"))]
            file_count = len(file_list)
        metadata = {}
        if file_count == 0:
            print(f"Skipping collection {count}... No files matched based on metadata filter.")
            continue

        os.system(f"mkdir -p {os.path.join(training_texts_path, db_name, 'texts')}")
        for text in preproc.process_texts(
            file_list,
            progress_prefix=f"Processing {file_count} files from collection {count} of {len(training_config['databases'])}...",
        ):
            if (
                training_config["min_tokens_per_doc"] > len(text)
                or metadata_filters
                and text.metadata[f"philo_{db_config['text_object_level']}_id"] not in philo_ids
            ):
                continue
            with open(
                os.path.join(training_texts_path, db_name, "texts", str(pos)), "w", buffering=65536, encoding="utf-8"
            ) as output:  ## Set buffer to 64K to speed up writes and avoid build-up in RAM
                if dictionary:
                    output.write(" ".join([t for t in text if t.text in dictionary]))
                else:
                    output.write(" ".join(text))
            if (
                db_name in inference_config["databases"]
                and db_config["text_object_level"] == inference_config["databases"][db_name]["text_object_level"]
            ):  # if training collection and inference collection are the same, we won't process it again
                text.metadata["philo_db"] = db_name
                metadata[pos] = text.metadata
            pos += 1
        with open(os.path.join(training_texts_path, db_name, "metadata.pickle"), "wb") as output_metadata:
            pickle.dump(metadata, output_metadata)
        preproc = None
        gc.collect()

    pos = 0
    count = 0
    print("Processing inference data...", flush=True)
    for db_name, db_config in inference_config["databases"].items():
        count += 1
        if db_name in training_config["databases"]:
            if db_config["text_object_level"] == training_config["databases"][db_name]["text_object_level"]:
                os.system(f"ln -s {os.path.abspath(training_texts_path)}/{db_name} {inference_texts_path}/{db_name}")
                continue
        preproc = PreProcessor(
            text_object_type=db_config["text_object_level"],
            language=prep_config["language"],
            language_model=prep_config["language_model"],
            stemmer=prep_config["stemmer"],
            lemmatizer=prep_config["lemmatizer"],
            modernize=prep_config["modernize"],
            lowercase=prep_config["lowercase"],
            strip_numbers=prep_config["numbers"],
            stopwords=prep_config["stopwords"],
            pos_to_keep=prep_config["pos_to_keep"],
            ner_to_keep=prep_config["ner_to_keep"],
            ascii=prep_config["ascii"],
            min_word_length=prep_config["minimum_word_length"],
            is_philo_db=True,
            workers=args.workers,
            progress=False,
        )
        dictionary = dictionary_filter((prep_config["dictionary"]), preproc)
        philo_ids = set()
        if metadata_filters:
            file_list, philo_ids = get_file_list(
                os.path.join(db_config["db_path"], "data"),
                metadata_filters,
                db_config["text_object_level"],
                prep_config["minimum_word_length"],
            )
            file_count = len(philo_ids)
        else:
            file_list = [f.path for f in os.scandir(os.path.join(db_config["db_path"], "data/words_and_philo_ids"))]
            file_count = len(file_list)
        metadata = {}
        if file_count == 0:
            print(f"Skipping collection {count}... No files matched based on metadata filter.")
            continue
        os.system(f"mkdir -p {os.path.join(inference_texts_path, db_name, 'texts')}")
        for text in preproc.process_texts(
            file_list,
            progress_prefix=f"Processing {file_count} files from collection {count} of {len(inference_config['databases'])}...",
        ):

            if (
                inference_config["min_tokens_per_doc"] > len(text)
                or metadata_filters
                and text.metadata[f"philo_{db_config['text_object_level']}_id"] not in philo_ids
            ):
                continue
            with open(
                os.path.join(inference_texts_path, db_name, "texts", str(pos)), "w", buffering=65536, encoding="utf-8"
            ) as output:  ## Set buffer to 64K to speed up writes and avoid build-up in RAM
                if dictionary:
                    output.write(" ".join([t for t in text if t.text in dictionary]))
                else:
                    output.write(" ".join(text))
            text.metadata["philo_db"] = db_name
            metadata[pos] = text.metadata
            pos += 1
        with open(os.path.join(inference_texts_path, db_name, "metadata.pickle"), "wb") as output_metadata:
            pickle.dump(metadata, output_metadata)
        preproc = None
        gc.collect()

    # Compress data output for if a new model is to be built from the same preprocessed data
    # Add timestamp to tarball YYYY-MM-DD_HH-MM
    tarball_name = f"{args.data_output}_{time.strftime('%Y-%m-%d_%H-%M')}.tar.gz"
    os.system(f"tar -czf {tarball_name} {args.data_output}")


def build_model(
    training_texts_path,
    inference_texts_path,
    training_config,
    inference_config,
    algorithm="lda",
    number_of_topics=100,
    max_iter=None,
    vectorization="tf",
    max_freq=0.9,
    min_freq=0.1,
    max_features=None,
    ngram=2,
    evaluate=False,
):

    # Load and prepare a corpus
    print("Vectorize documents...", flush=True)
    training_corpus = Corpus(
        training_texts_path,
        vectorization=vectorization,
        max_relative_frequency=max_freq,
        min_absolute_frequency=min_freq,
        ngram=ngram,
        max_features=max_features,
    )
    print("training corpus size:", training_corpus.size)
    print("vocabulary size:", len(training_corpus.vectorizer.vocabulary_))

    identical_corpus = True
    if len(training_config["databases"]) != len(inference_config["databases"]):
        identical_corpus = False
    if identical_corpus is True:
        for db, db_config in training_config["databases"].items():
            if db not in inference_config["databases"]:
                identical_corpus = False
                break
            if db_config["text_object_level"] != inference_config["databases"][db]["text_object_level"]:
                identical_corpus = False
                break

    if identical_corpus is True:
        if training_config["min_tokens_per_doc"] == inference_config["min_tokens_per_doc"] or evaluate is True:
            full_corpus = training_corpus
        else:
            full_corpus = Corpus(
                training_texts_path,
                vectorizer=training_corpus.vectorizer,
                max_relative_frequency=training_corpus._max_relative_frequency,
                min_absolute_frequency=training_corpus._min_absolute_frequency,
                ngram=training_corpus.ngram,
            )
    else:
        full_corpus = Corpus(
            inference_texts_path,
            vectorizer=training_corpus.vectorizer,
            max_relative_frequency=training_corpus._max_relative_frequency,
            min_absolute_frequency=training_corpus._min_absolute_frequency,
            ngram=training_corpus.ngram,
        )

    print("inference corpus size:", full_corpus.size)

    # Instantiate a topic model
    if algorithm == "nmf":
        topic_model = NonNegativeMatrixFactorization(training_corpus, max_iter=max_iter)
    else:
        topic_model = LatentDirichletAllocation(training_corpus, max_iter=max_iter)

    if evaluate is False:
        # Infer topics
        full_corpus.build_annoy_index()
        print("Inferring topics...", flush=True)
        topic_model.infer_topics(num_topics=number_of_topics)
        topic_model.infer_and_replace(full_corpus)

    return topic_model, full_corpus, training_corpus


def build_web_app(
    config_path,
    inference_config,
    database_name,
    topic_model,
    full_corpus,
    topics_over_time,
):
    db_path = os.path.join(GLOBAL_CONFIG["WEB_APP"]["web_app_path"], database_name)
    if os.path.exists(db_path) is True:
        os.system(f"rm -rf {db_path}")
    os.mkdir(db_path)
    os.system(f"cp -R /var/lib/topologic/web-app/browser-app/* {db_path}/")
    os.system(f"cp /var/lib/topologic/web-app/apache_htaccess.conf {db_path}/.htaccess")
    config = configparser.ConfigParser()
    config.read(config_path)

    years = set()
    metadata_field_names = set()
    for fields in full_corpus.metadata.values():
        for field in fields.keys():
            metadata_field_names.add(field)
        try:
            years.add(int(fields["year"]))
        except ValueError:
            pass
    if topics_over_time["start_date"] is None:
        min_year = min(years)
    else:
        min_year = topics_over_time["start_date"]
    if topics_over_time["end_date"] is None:
        max_year = max(years)
    else:
        max_year = topics_over_time["end_date"]
    if topics_over_time["topics_over_time_interval"] != 1:
        min_year = year_normalizer(min_year, topics_over_time["topics_over_time_interval"])
        max_year = max_year_normalizer(max_year, topics_over_time["topics_over_time_interval"])

    config["DATA"] = {
        "num_docs": full_corpus.size,
        "num_tokens": len(full_corpus.vectorizer.vocabulary_),
        "metadata": ",".join(metadata_field_names),
    }

    with open(os.path.join(db_path, "model_config.ini"), "w", encoding="utf8") as configfile:
        config.write(configfile)

    db = DBHandler.set_class_attributes(
        GLOBAL_CONFIG["DATABASE"],
        database_name,
        topic_model,
        full_corpus,
        min_year,
        max_year,
        topics_over_time["topics_over_time_interval"],
    )
    print("Saving words...", flush=True)
    db.save_words()

    print("Saving docs...", flush=True)
    db.save_docs()

    print("Saving topics...", flush=True)
    db.save_topics(
        f"{db_path}/topic_words.json",
        min_year,
        max_year,
        topics_over_time["topics_over_time_interval"],
    )

    write_app_config(
        db_path,
        database_name,
        GLOBAL_CONFIG["WEB_APP"]["server_name"],
        GLOBAL_CONFIG["WEB_APP"]["proxy_path"],
        {db_name: db_config["db_url"] for db_name, db_config in inference_config["databases"].items()},
        min_year,
        max_year,
        topics_over_time["topics_over_time_interval"],
    )
    os.system(f"cd {db_path}; npm run build")

    print(
        f"""TopoLogic web application is viewable at: {os.path.join(GLOBAL_CONFIG['WEB_APP']['server_name'], GLOBAL_CONFIG["WEB_APP"]["proxy_path"], 'topologic', os.path.basename(db_path))}"""
    )


if __name__ == "__main__":
    args = parse_args()
    main(args)
