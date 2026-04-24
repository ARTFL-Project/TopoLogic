"""Parse raw TEI/plaintext files into a philologic-shaped directory.

Produces `data/words_and_philo_ids/*.lz4` + a toms (metadata) table that the
existing `PreProcessor(is_philo_db=True)` pipeline consumes. Bibliography
(tsv/csv, auto-detected) is optional — without it, metadata is pulled from
TEI headers.
"""

import os
from typing import Set

from philologic.loadtime import LoadFilters
from philologic.loadtime import Parser as XMLParser
from philologic.loadtime import PlainTextParser
from philologic.loadtime.Loader import Loader, setup_db_dir

PHILO_TEXT_OBJECT_LEVELS = {
    "doc": 1,
    "div1": 2,
    "div2": 3,
    "div3": 4,
    "para": 5,
    "sent": 6,
    "word": 7,
}


def is_philo_db(path: str) -> bool:
    """True if `path` is the root of a pre-built philologic database."""
    return os.path.isdir(os.path.join(path, "data", "words_and_philo_ids"))


def _detect_file_type(input_file_path: str) -> str:
    """Return 'tei' if any file in the dir looks like XML, else 'plaintext'."""
    for entry in os.scandir(input_file_path):
        if entry.is_file() and entry.name.lower().endswith((".xml", ".tei", ".tei.xml")):
            return "tei"
    return "plaintext"


def _find_bibliography(input_file_path: str) -> str:
    """Look for a sibling bibliography file next to the input dir."""
    parent = os.path.dirname(os.path.abspath(input_file_path))
    for name in ("bibliography.tsv", "bibliography.tab", "bibliography.csv"):
        candidate = os.path.join(parent, name)
        if os.path.isfile(candidate):
            return candidate
        candidate = os.path.join(input_file_path, name)
        if os.path.isfile(candidate):
            return candidate
    return ""


def parse_files(
    input_file_path: str,
    output_path: str,
    object_level: str,
    lowercase: bool = True,
    workers: int = 4,
    file_type: str = "",
    bibliography: str = "",
    words_to_index: str = "all",
    debug: bool = False,
) -> str:
    """Parse a directory of TEI/plaintext files into a philo-db dir.

    Returns the absolute output path (which is also a valid philo-db root).
    """
    input_file_path = os.path.abspath(input_file_path)
    output_path = os.path.abspath(output_path)
    # philologic's Loader chdir's into its own WORK dir while running, so we
    # capture cwd here and restore it before returning — otherwise downstream
    # code that uses relative paths resolves them against WORK/.
    original_cwd = os.getcwd()
    # Nest the philologic output under `<output_path>/data/` so the resulting
    # tree matches a standard philologic db layout (`data/words_and_philo_ids`,
    # `data/TEXT`, `data/WORK`). TopoLogic's downstream pipeline — and the
    # `is_philo_db()` detector — both assume that layout.
    data_destination = os.path.join(output_path, "data")
    os.makedirs(data_destination, exist_ok=True)
    setup_db_dir(data_destination, force_delete=True)

    if not file_type:
        file_type = _detect_file_type(input_file_path)
    if not bibliography:
        bibliography = _find_bibliography(input_file_path)

    word_list: Set[str] = set()
    if words_to_index != "all" and words_to_index:
        with open(words_to_index, encoding="utf8") as fh:
            for line in fh:
                word_list.add(line.strip())

    navigable_objects = [
        text_object
        for text_object, depth in PHILO_TEXT_OBJECT_LEVELS.items()
        if PHILO_TEXT_OBJECT_LEVELS[object_level] >= depth
    ]

    if file_type == "tei":
        parser_factory = XMLParser.XMLParser
        token_regex = XMLParser.TOKEN_REGEX
    else:
        parser_factory = PlainTextParser.PlainTextParser
        token_regex = PlainTextParser.TOKEN_REGEX

    loader = Loader.set_class_attributes(
        {
            "post_filters": [],
            "debug": debug,
            "words_to_index": word_list,
            "data_destination": data_destination,
            "db_destination": "",
            "default_object_level": object_level,
            "token_regex": token_regex,
            "url_root": "",
            "cores": workers,
            "ascii_conversion": True,
            "doc_xpaths": XMLParser.DEFAULT_DOC_XPATHS,
            "metadata_sql_types": {},
            "metadata_to_parse": XMLParser.DEFAULT_METADATA_TO_PARSE,
            "tag_to_obj_map": XMLParser.DEFAULT_TAG_TO_OBJ_MAP,
            "parser_factory": parser_factory,
            "load_filters": LoadFilters.set_load_filters(navigable_objects=navigable_objects),
            "file_type": file_type,
            "bibliography": bibliography,
            "lowercase_index": lowercase,
            "load_config": "",
            "lemma_file": None,
            "spacy_model": "",
            "suppress_word_attributes": [],
        }
    )
    loader.tables = ["toms"]
    try:
        loader.add_files([f.path for f in os.scandir(input_file_path) if f.is_file()])
        if bibliography:
            doc_metadata = loader.parse_bibliography_file(
                bibliography, ["year", "author", "title", "filename"]
            )
        else:
            doc_metadata = loader.parse_metadata(
                ["year", "author", "title", "filename"], header="tei", verbose=False
            )
        loader.set_file_data(doc_metadata, loader.textdir, loader.workdir)
        loader.parse_files(workers, verbose=False)
        loader.merge_files("toms", verbose=False)
        loader.setup_sql_load(verbose=False)
        # Inline a minimal post_processing: the standard Loader.post_processing
        # unconditionally builds a collocation database (numpy/LMDB artefacts
        # used by PhiloLogic's search UI, ~30s on a mid-size corpus) which
        # TopoLogic never queries. Run only the SQL-table post_filters that
        # setup_sql_load registered.
        for f in loader.post_filters:
            if f.__name__ == "metadata_frequencies":
                loader.metadata_fields_not_found = f(loader)
            else:
                f(loader)
        loader.write_db_config()
    finally:
        os.chdir(original_cwd)
    return output_path
