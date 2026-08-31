#!/usr/bin/env python3

import argparse
import configparser
import gc
import os
import pickle
import shutil
import subprocess
import time

from joblib import dump
from philologic.runtime.DB import DB
from text_preprocessing import PreProcessor, Token

from topologic import (
    BERTopicModel,
    Corpus,
    LatentDirichletAllocation,
    NonNegativeMatrixFactorization,
    max_year_normalizer,
    read_config,
    topic_num_evaluator,
    write_app_config,
    year_normalizer,
)
from topologic.chunking import write_raw_paragraphs_for_metadata
from topologic.DB import DBHandler
from topologic.text_parser import is_philo_db, parse_files


def _create_lz4_tarball(out_path, source_dir):
    """Stream `source_dir` into an lz4-compressed tarball at `out_path`.

    lz4 trades somewhat larger output for 3-5x faster (de)compression, which
    suits a tarball rewritten on every fresh preprocess.
    """
    import tarfile

    import lz4.frame

    with lz4.frame.open(out_path, "wb") as compressed_fp:
        with tarfile.open(fileobj=compressed_fp, mode="w") as tar:
            tar.add(source_dir, arcname=os.path.basename(source_dir.rstrip(os.sep)))


def _extract_preprocessed_tarball(tarball_path, out_dir):
    """Extract a preprocessed-data tarball into `out_dir`.

    Auto-detects compression from extension: `.tar.lz4`/`.lz4` for lz4
    (current format), `.tar.gz`/`.tgz`/`.gz` for gzip (older tarballs).
    """
    import tarfile
    name = tarball_path.lower()
    # filter="data" blocks extraction outside the destination and setuid bits.
    if name.endswith(".lz4"):
        import lz4.frame
        with lz4.frame.open(tarball_path, "rb") as compressed_fp:
            with tarfile.open(fileobj=compressed_fp, mode="r|") as tar:
                tar.extractall(path=out_dir, filter="data")
    elif name.endswith((".gz", ".tgz")):
        with tarfile.open(tarball_path, "r:gz") as tar:
            tar.extractall(path=out_dir, filter="data")
    else:
        raise ValueError(
            f"Unrecognized tarball extension on {tarball_path!r}; "
            "expected .tar.lz4 (current format) or .tar.gz (legacy)."
        )

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
        topic_labeling,
    ) = read_config(args.config)
    training_texts_path = os.path.join(args.data_output, "training/")
    inference_texts_path = os.path.join(args.data_output, "inference/")
    if args.preprocessed_data_path is None:
        if os.path.exists(args.data_output):
            shutil.rmtree(args.data_output)
        os.makedirs(inference_texts_path, exist_ok=True)
        os.makedirs(training_texts_path, exist_ok=True)

    if args.preprocessed_data_path is None:
        parsed_root = os.path.join(args.data_output, "parsed")
        ensure_parsed_dbs(training_config, parsed_root, args.workers, args.debug)
        ensure_parsed_dbs(inference_config, parsed_root, args.workers, args.debug)
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
        # Decompress preprocessed data (lz4 for current tarballs, gzip for legacy).
        _extract_preprocessed_tarball(args.preprocessed_data_path, os.path.dirname(os.path.abspath(args.data_output)) or ".")
        training_texts_path = os.path.join(args.data_output, "training/")
        inference_texts_path = os.path.join(args.data_output, "inference/")

    topic_model, full_corpus, training_corpus = build_model(
        training_texts_path,
        inference_texts_path,
        training_config,
        inference_config,
        algorithm=model_config["algorithm"],
        number_of_topics=model_config["number_of_topics"],
        max_iter=model_config.get("max_iter"),
        vectorization=vector_config["vectorization"],
        max_freq=vector_config["max_freq"],
        min_freq=vector_config["min_freq"],
        max_features=vector_config["max_features"] or None,
        ngram=vector_config["ngram"],
        evaluate=args.evaluate,
        model_options=model_config,
    )

    if args.evaluate is False:
        build_web_app(
            args.config,
            inference_config,
            database_name,
            topic_model,
            full_corpus,
            topics_over_time,
            topic_labeling,
        )
    else:
        if model_config["algorithm"] == "bertopic":
            # Greene stability refits at a fixed k; bertopic has no k to sweep.
            raise ValueError(
                "--evaluate estimates the number of topics for nmf/lda, which take k as "
                "an input. bertopic determines its topic count from the clustering; tune "
                "min_cluster_size instead."
            )
        print("Estimating the number of topics...")
        corpus_path = os.path.join(args.data_output, "corpus")
        dump(training_corpus, corpus_path)
        os.makedirs("./evaluation_output", exist_ok=True)
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

    # Re-tar at end-of-run so the embedding cache is preserved for future
    # --preprocessed_data_path runs; the tarball from prepare_data has only the
    # preprocessed text, so re-running with this one skips embedding.
    if args.evaluate is False:
        post_tarball = f"{args.data_output}_with_embeddings_{time.strftime('%Y-%m-%d_%H-%M')}.tar.lz4"
        try:
            _create_lz4_tarball(post_tarball, args.data_output)
            print(f"Saved post-build tarball (with embedding cache): {post_tarball}", flush=True)
        except Exception as exc:
            print(f"Warning: failed to write post-build tarball: {exc}", flush=True)

    if args.debug is False:
        shutil.rmtree(args.data_output, ignore_errors=True)


def ensure_parsed_dbs(data_config, parsed_root, workers, debug):
    """For any `text_paths` entry that isn't an existing philo-db, parse it
    in-place and rewrite `db_path` to the generated philo-db directory.
    """
    for db_name, db_config in data_config["databases"].items():
        src_path = db_config["db_path"]
        if is_philo_db(src_path):
            continue
        if not os.path.isdir(src_path):
            print(f"Error: text_paths entry is not a directory: {src_path}")
            exit(1)
        parsed_dir = os.path.join(parsed_root, db_name)
        # If this db is already parsed (e.g., shared training/inference entry),
        # just point at the existing output.
        if not is_philo_db(parsed_dir):
            print(f"## PARSING RAW FILES: {db_name} ##", flush=True)
            parse_files(
                input_file_path=src_path,
                output_path=parsed_dir,
                object_level=db_config["text_object_level"],
                workers=workers,
                debug=debug,
            )
        db_config["db_path"] = parsed_dir


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
        paragraph_metadata = {}
        if file_count == 0:
            print(f"Skipping collection {count}... No files matched based on metadata filter.")
            continue

        os.makedirs(os.path.join(training_texts_path, db_name, "texts"), exist_ok=True)
        # Also persist the full preprocessor Tokens object per doc. Each
        # PreprocessorToken carries `ext["start_byte"]` / `ext["end_byte"]`
        # inherited from the source, so `save_doc_chunks` can later assign
        # each preproc token to its paragraph (byte range from lz4) and feed
        # true vectorizer-vocabulary tokens to fold-in.
        os.makedirs(os.path.join(training_texts_path, db_name, "tokens"), exist_ok=True)
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
            text.save(os.path.join(training_texts_path, db_name, "tokens", f"{pos}.pkl"))
            text.metadata["philo_db"] = db_name
            # Separate from `metadata`, which is deliberately empty when the
            # training and inference object levels differ. Paragraph extraction
            # needs every training doc regardless, and keying it off `metadata`
            # silently wrote nothing for those runs.
            paragraph_metadata[pos] = text.metadata
            if (
                db_name in inference_config["databases"]
                and db_config["text_object_level"] == inference_config["databases"][db_name]["text_object_level"]
            ):  # if training collection and inference collection are the same, we won't process it again
                metadata[pos] = text.metadata
            pos += 1
        with open(os.path.join(training_texts_path, db_name, "metadata.pickle"), "wb") as output_metadata:
            pickle.dump(metadata, output_metadata)
        # Atomic raw-text paragraphs. Runs unconditionally so the tarball
        # stays portable — chunks are formed later, at whatever size is asked.
        written = write_raw_paragraphs_for_metadata(
            metadata=paragraph_metadata,
            db_name=db_name,
            philo_db_path=db_config["db_path"],
            level=db_config["text_object_level"],
            object_levels=OBJECT_LEVELS,
            out_dir=os.path.join(training_texts_path, db_name, "raw_paragraphs"),
            progress_desc=f"Extracting raw paragraphs for {db_name} (training)",
        )
        if written < len(paragraph_metadata):
            print(
                f"Warning: wrote raw paragraphs for {written}/{len(paragraph_metadata)} training docs "
                f"in {db_name}. The rest cannot be chunked, or embedded from raw text.",
                flush=True,
            )
        preproc = None
        gc.collect()

    pos = 0
    count = 0
    print("Processing inference data...", flush=True)
    for db_name, db_config in inference_config["databases"].items():
        count += 1
        if db_name in training_config["databases"]:
            if db_config["text_object_level"] == training_config["databases"][db_name]["text_object_level"]:
                os.symlink(
                    os.path.join(os.path.abspath(training_texts_path), db_name),
                    os.path.join(inference_texts_path, db_name),
                )
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
        os.makedirs(os.path.join(inference_texts_path, db_name, "texts"), exist_ok=True)
        os.makedirs(os.path.join(inference_texts_path, db_name, "tokens"), exist_ok=True)
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
            text.save(os.path.join(inference_texts_path, db_name, "tokens", f"{pos}.pkl"))
            text.metadata["philo_db"] = db_name
            metadata[pos] = text.metadata
            pos += 1
        with open(os.path.join(inference_texts_path, db_name, "metadata.pickle"), "wb") as output_metadata:
            pickle.dump(metadata, output_metadata)
        write_raw_paragraphs_for_metadata(
            metadata=metadata,
            db_name=db_name,
            philo_db_path=db_config["db_path"],
            level=db_config["text_object_level"],
            object_levels=OBJECT_LEVELS,
            out_dir=os.path.join(inference_texts_path, db_name, "raw_paragraphs"),
            progress_desc=f"Extracting raw paragraphs for {db_name} (inference)",
        )
        preproc = None
        gc.collect()

    # Compress data output for if a new model is to be built from the same preprocessed data
    # Add timestamp to tarball YYYY-MM-DD_HH-MM
    tarball_name = f"{args.data_output}_{time.strftime('%Y-%m-%d_%H-%M')}.tar.lz4"
    _create_lz4_tarball(tarball_name, args.data_output)


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
    model_options=None,
):
    model_options = model_options or {}
    # nmf/lda need an explicit k. bertopic also accepts None ("keep the
    # clustering's own topic count") and "auto" -- its topic count is a
    # property of the clustering, not an input. See config.py.
    if algorithm != "bertopic":
        if not isinstance(number_of_topics, int):
            raise ValueError(
                f"algorithm={algorithm!r} requires number_of_topics to be a positive "
                f"integer, got {number_of_topics!r}."
            )
        if not isinstance(max_iter, int):
            raise ValueError(
                f"algorithm={algorithm!r} requires max_iter to be a positive integer, "
                f"got {max_iter!r}. Only bertopic may leave it empty."
            )

    # bertopic chunks at embed time, so chunking its corpus too would
    # double-chunk; nmf/lda have no such step, making the training corpus where
    # their chunking happens. The inference corpus always stays
    # document-level — documents are what the web app cites.
    training_chunk_size = None if algorithm == "bertopic" else training_config.get("max_chunk_size")
    print("Vectorize documents...", flush=True)
    training_corpus = Corpus(
        training_texts_path,
        vectorization=vectorization,
        max_relative_frequency=max_freq,
        min_absolute_frequency=min_freq,
        ngram=ngram,
        max_features=max_features,
        max_chunk_size=training_chunk_size,
    )
    if training_chunk_size:
        print(
            f"Training on chunks of at most {training_chunk_size} raw words.",
            flush=True,
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
        # Chunked training forces a separate inference corpus, or every
        # "document" downstream would be a chunk.
        if training_chunk_size is None and (
            training_config["min_tokens_per_doc"] == inference_config["min_tokens_per_doc"] or evaluate is True
        ):
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

    # An unrecognized algorithm must raise: the previous `else -> LDA` fallback
    # meant a bertopic run completed having quietly built an LDA model.
    if algorithm == "nmf":
        topic_model = NonNegativeMatrixFactorization(training_corpus, max_iter=max_iter)
    elif algorithm == "lda":
        topic_model = LatentDirichletAllocation(training_corpus, max_iter=max_iter)
    elif algorithm == "bertopic":
        # Only keys the config actually set, so BERTopicModel.__init__ stays
        # the one place defaults live.
        bertopic_options = {
            key: model_options[key]
            for key in (
                "embedding_model",
                "reduce_outliers",
                "min_cluster_size",
                "cluster_selection_method",
                "assignment_temperature",
                "mmr_diversity",
            )
            if key in model_options
        }
        if "embedding_batch_size" in model_options:
            bertopic_options["batch_size"] = model_options["embedding_batch_size"]
        # From the data sections, not TOPIC_MODELING: training and inference
        # may legitimately differ. infer_topics uses the training value;
        # infer_and_replace swaps in the inference one below.
        if training_config.get("max_chunk_size") is not None:
            bertopic_options["max_chunk_size"] = training_config["max_chunk_size"]
        topic_model = BERTopicModel(training_corpus, max_iter=max_iter, **bertopic_options)
    else:
        raise ValueError(f"Unknown algorithm {algorithm!r}. Expected one of: nmf, lda, bertopic.")

    if evaluate is False:
        # Infer topics
        full_corpus.build_annoy_index()
        print("Inferring topics...", flush=True)
        topic_model.infer_topics(num_topics=number_of_topics)
        # Cut the inference corpus the way INFERENCE_DATA asks.
        if algorithm == "bertopic":
            topic_model.max_chunk_size = inference_config.get("max_chunk_size")
        topic_model.infer_and_replace(full_corpus)

    return topic_model, full_corpus, training_corpus


def build_web_app(
    config_path,
    inference_config,
    database_name,
    topic_model,
    full_corpus,
    topics_over_time,
    topic_labeling,
):
    db_path = os.path.join(GLOBAL_CONFIG["WEB_APP"]["web_app_path"], database_name)
    if os.path.exists(db_path):
        shutil.rmtree(db_path)
    shutil.copytree("/var/lib/topologic/web-app/browser-app", db_path)
    shutil.copy2("/var/lib/topologic/web-app/apache_htaccess.conf", os.path.join(db_path, ".htaccess"))
    config = configparser.ConfigParser()
    config.read(config_path, encoding="utf-8")

    years = set()
    metadata_field_names = set()
    for fields in full_corpus.metadata.values():
        for field in fields.keys():
            metadata_field_names.add(field)
        try:
            years.add(int(fields["year"]))
        except (KeyError, ValueError, TypeError):
            pass

    configured_start = topics_over_time["start_date"]
    configured_end = topics_over_time["end_date"]
    time_series_enabled = bool(years) or configured_start is not None or configured_end is not None

    if time_series_enabled:
        min_year = configured_start if configured_start is not None else min(years)
        max_year = configured_end if configured_end is not None else max(years)
        # Storage is always per-year. The display bucket size is chosen at query
        # time from the UI; no need to normalize the bounds to it.
    else:
        print(
            "No parseable 'year' metadata found in corpus; disabling time-series features.",
            flush=True,
        )
        min_year = None
        max_year = None

    config["DATA"] = {
        "num_docs": full_corpus.size,
        "num_tokens": len(full_corpus.vectorizer.vocabulary_),
        # What the model actually produced. [TOPIC_MODELING]/number_of_topics
        # is only the input and may be empty, "auto", or simply not hit.
        "num_topics": topic_model.nb_topics,
        "metadata": ",".join(metadata_field_names),
    }

    with open(os.path.join(db_path, "model_config.ini"), "w", encoding="utf8") as configfile:
        config.write(configfile)

    # Storage is always 1-year buckets; re-bucketing to any display interval
    # happens at query time so the UI can toggle it live.
    storage_interval = 1
    # DuckDB file lives inside each model's webapp dir — one file per model,
    # fully portable with the rest of the deployment.
    db_file = os.path.join(db_path, "model.duckdb")
    if os.path.exists(db_file):
        os.remove(db_file)
    with DBHandler.set_class_attributes(
        db_file,
        topic_model,
        full_corpus,
        min_year,
        max_year,
        storage_interval,
        time_series_enabled,
    ) as db:
        print("Saving words...", flush=True)
        db.save_words()

        print("Saving docs...", flush=True)
        db.save_docs()

        print("Building structural chunks + HTML for topical reading...", flush=True)
        db.save_doc_chunks(
            inference_config["databases"],
            max_chunk_size=inference_config.get("max_chunk_size"),
        )

        print("Building per-metadata-value profiles...", flush=True)
        db.save_metadata_profiles()

        print("Saving topics...", flush=True)
        db.save_topics(
            f"{db_path}/topic_words.json",
            min_year,
            max_year,
            storage_interval,
            topic_labeling=topic_labeling,
        )

    write_app_config(
        db_path,
        database_name,
        GLOBAL_CONFIG["WEB_APP"]["server_name"],
        GLOBAL_CONFIG["WEB_APP"]["proxy_path"],
        list(inference_config["databases"].keys()),
        min_year,
        max_year,
        topics_over_time["topics_over_time_interval"],
        time_series_enabled,
    )
    subprocess.run(["npm", "run", "build"], cwd=db_path, check=True)

    print(
        f"""TopoLogic web application is viewable at: {os.path.join(GLOBAL_CONFIG['WEB_APP']['server_name'], GLOBAL_CONFIG["WEB_APP"]["proxy_path"], 'topologic', os.path.basename(db_path))}"""
    )


if __name__ == "__main__":
    args = parse_args()
    main(args)
