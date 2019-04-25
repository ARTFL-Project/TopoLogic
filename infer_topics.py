#!/usr/bin/env python3

import os
import re
import shutil
import sys
from html import unescape as unescape_html
from xml.sax.saxutils import unescape as unescape_xml

import dill as pickle

import tom_lib.utils as utils
from tom_lib.nlp.topic_model import LatentDirichletAllocation, NonNegativeMatrixFactorization, save_model
from tom_lib.structure.corpus import Corpus, save_corpus

TAGS = re.compile(r"<[^>]+>")
START_TAG = re.compile(r"^[^<]*?>")


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


def get_text(start_byte: int, end_byte: int, filename: str) -> str:
    """Grab all texts"""
    if start_byte < 0:
        start_byte = 0
    length: int = end_byte - start_byte
    with open(filename, "rb") as text_file:
        text_file.seek(start_byte)
        text: str = text_file.read(length).decode("utf8", "ignore")
    text = clean_text(text)
    return text


def main():
    with open("/shared/philomine/texts_NOUN.pickle", "rb") as pickled_texts:
        texts = pickle.load(pickled_texts)

    with open("input/texts.csv", "w") as csv_output:
        with open("input/texts_partial.csv", "w") as csv_partial_output:
            print("id\ttitle\ttext\tauthor\tdate\taffiliation\tfull_text", file=csv_output)
            print("id\ttitle\ttext\tauthor\tdate\taffiliation", file=csv_partial_output)
            partial_id = 0
            full_id = 0
            for text in texts:
                if len(text) > 50:
                    print(
                        "\t".join(
                            [
                                str(partial_id),
                                text.metadata["title"] + f""" ({text.metadata["pub_date"]})""",
                                " ".join(text),
                                text.metadata["author"],
                                text.metadata["year"],
                                text.metadata["author"],
                            ]
                        ),
                        file=csv_partial_output,
                    )
                    partial_id += 1
                if len(text) >= 10:
                    print(
                        "\t".join(
                            [
                                str(full_id),
                                text.metadata["title"] + f""" ({text.metadata["pub_date"]})""",
                                " ".join(text),
                                text.metadata["author"],
                                text.metadata["year"],
                                text.metadata["author"],
                            ]
                        ),
                        file=csv_output,
                    )
                    full_text = get_text(
                        text.metadata["start_byte"], text.metadata["end_byte"], text.metadata["filename"]
                    )

                    with open(f"browser/static/text/{full_id}.txt", "w") as text_output:
                        text_output.write(full_text)
                    full_id += 1

    if sys.argv[2] == "nmf":
        vectorization = "tfidf"
    else:
        vectorization = "tf"

    # Load and prepare a corpus
    print("Load documents from CSV")
    partial_corpus = Corpus(
        source_file_path="input/texts_partial.csv",
        vectorization=vectorization,  # 'tf' (term-frequency) or 'tfidf' (term-frequency inverse-document-frequency)
        max_relative_frequency=0.5,  # ignore words which relative frequency is > than max_relative_frequency
        min_absolute_frequency=0.01,
        n_gram=2,
    )  # ignore words which absolute frequency is < than min_absolute_frequency
    print("corpus size:", partial_corpus.size)
    print("vocabulary size:", len(partial_corpus.vocabulary))

    full_corpus = Corpus(source_file_path="input/texts.csv", vectorizer=partial_corpus.vectorizer)

    # Instantiate a topic model
    if sys.argv[2] == "nmf":
        topic_model = NonNegativeMatrixFactorization(partial_corpus)
    else:
        topic_model = LatentDirichletAllocation(partial_corpus)

    # Infer topics
    print("Inferring topics...")
    topic_model.infer_topics(num_topics=int(sys.argv[1]))
    topic_model.infer_and_replace(full_corpus)

    # Save corpus
    full_corpus.similar_documents_by_topic_distribution(topic_model)
    save_corpus(full_corpus)

    save_model(topic_model)

    #  Clean the data directory
    if os.path.exists("browser/static/data"):
        shutil.rmtree("browser/static/data")
    os.makedirs("browser/static/data")

    # Export topic cloud
    utils.save_topic_cloud(topic_model, "browser/static/data/topic_cloud.json")

    # Export details about topics
    print("Saving word distributions...")
    for topic_id in range(topic_model.nb_topics):
        utils.save_word_distribution(
            topic_model.top_words(topic_id, 20), "browser/static/data/word_distribution" + str(topic_id) + ".json"
        )
        utils.save_affiliation_repartition(
            topic_model.affiliation_repartition(topic_id),
            "browser/static/data/affiliation_repartition" + str(topic_id) + ".tsv",
        )
        evolution = []
        for i in range(1711, 1778):
            evolution.append((i, topic_model.topic_frequency(topic_id, date=i)))
        utils.save_topic_evolution(evolution, "browser/static/data/frequency" + str(topic_id) + ".json")

    # Export details about documents
    print("Saving topic distributions...")
    for doc_id in range(topic_model.corpus.size):
        utils.save_topic_distribution(
            topic_model.topic_distribution_for_document(doc_id),
            "browser/static/data/topic_distribution_d" + str(doc_id) + ".json",
        )

    # Export details about words
    print("Saving word distributions across topics...")
    for word_id in range(len(topic_model.corpus.vocabulary)):
        utils.save_topic_distribution(
            topic_model.topic_distribution_for_word(word_id),
            "browser/static/data/topic_distribution_w" + str(word_id) + ".json",
        )

    # Associate documents with topics
    topic_associations = topic_model.documents_per_topic()

    # Export per-topic author network
    for topic_id in range(topic_model.nb_topics):
        utils.save_json_object(
            full_corpus.collaboration_network(topic_associations[topic_id]),
            "browser/static/data/author_network" + str(topic_id) + ".json",
        )


if __name__ == "__main__":
    main()
