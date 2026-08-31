#!/usr/bin/env python3

import os
import pickle
import random
import re
from math import floor
from typing import NamedTuple

import numpy as np
from annoy import AnnoyIndex
from multiprocess import cpu_count
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from tqdm import tqdm


class ChunkedCorpus(NamedTuple):
    """One row per chunk, plus the mapping back to documents.

    `doc_index[i]` is the sklearn_vector_space ROW of the document chunk i
    belongs to; `tokens[i]` is its raw word count, used to weight the
    aggregation back to document level. Chunks never span documents.
    """

    texts: list
    embeddings: np.ndarray
    doc_index: np.ndarray
    tokens: np.ndarray

    @property
    def n_docs(self):
        return int(self.doc_index.max()) + 1 if len(self.doc_index) else 0


def iter_text_collections(text_path):
    """Yield the DirEntry of each text-collection subdirectory under `text_path`.

    Filtering to real directories is load-bearing, not defensive:
    `Corpus.compute_or_load_embeddings` caches `embeddings_*.npy` in
    `text_path` itself, i.e. as a sibling of the collections. Any scan here
    that descends unconditionally raises NotADirectoryError on that file the
    moment a run reuses a post-build tarball -- which is exactly what the
    tarball exists for.
    """
    for entry in os.scandir(text_path):
        if entry.is_dir() and os.path.isdir(os.path.join(entry.path, "texts")):
            yield entry


class savedTexts:
    def __init__(self, text_path, max_chunk_size=None):
        self.text_path = text_path
        # When set, iteration yields CHUNKS rather than documents, so each row
        # of the corpus matrix is a chunk. Only ever set on a training corpus:
        # inference rows must stay documents, since that is what the web app
        # cites and links.
        self.max_chunk_size = max_chunk_size

    def iter_doc_entries(self):
        """(doc_id, text_file_path, collection_path), globally sorted by doc_id.

        The single definition of corpus row order: row i of
        `Corpus.sklearn_vector_space` is entry i of this list. Any parallel
        walk over the corpus -- embeddings, per-doc side files -- must go
        through this rather than re-deriving an order, or it risks pairing
        row i with a different document: doc ids are assigned by a global
        counter in contiguous per-database blocks, while `os.scandir` returns
        inode order, and the two disagree as soon as there is more than one
        database.
        """
        entries = []
        for collection in iter_text_collections(self.text_path):
            texts_dir = os.path.join(collection.path, "texts")
            for input_file in os.scandir(texts_dir):
                if input_file.name.isdigit():
                    entries.append((int(input_file.name), input_file.path, collection.path))
        entries.sort(key=lambda entry: entry[0])
        return entries

    def iter_chunk_texts(self, max_chunk_size):
        """Yield preprocessed text split into chunks of at most `max_chunk_size` raw words.

        Used to make the TRAINING corpus chunk-level. A long document's word
        co-occurrence is nearly uniform, so document-level statistics cannot
        separate themes that reliably appear together inside it; chunks break
        that correlation. Measured on a synthetic corpus where three pairs of
        themes always co-occur, document-level NMF recovered 5/6 themes at 53%
        top-word purity while chunk-level recovered 6/6 at 100%.

        Chunk boundaries come from `raw_paragraphs` (raw words, so the size
        means the same thing as it does for embedding) but the text emitted is
        the PREPROCESSED token stream, mapped onto paragraphs by byte range —
        that is what the vectorizer must see.

        Falls back to yielding whole documents, with a warning, when the
        per-paragraph inputs are missing (a tarball preprocessed before byte
        spans were recorded).
        """
        import json as _json

        from topologic.chunking import assign_preproc_tokens, group_by_counts, group_paragraphs_into_chunks

        try:
            from text_preprocessing.spacy_helpers import Tokens
        except ImportError:
            Tokens = None

        degraded = 0
        total_docs = 0
        for doc_id, text_file_path, collection_path in self.iter_doc_entries():
            total_docs += 1
            paragraphs = None
            p_path = os.path.join(collection_path, "raw_paragraphs", f"{doc_id}.json")
            if os.path.exists(p_path):
                with open(p_path, encoding="utf-8") as fh:
                    paragraphs = _json.load(fh)

            tokens_obj = None
            if Tokens is not None:
                pkl = os.path.join(collection_path, "tokens", f"{doc_id}.pkl")
                if os.path.exists(pkl):
                    try:
                        tokens_obj = Tokens.load(pkl)
                    except Exception:
                        tokens_obj = None

            usable = (
                paragraphs
                and tokens_obj is not None
                and all("start_byte" in p for p in paragraphs)
            )
            if not usable:
                degraded += 1
                with open(text_file_path, encoding="utf8") as fh:
                    yield fh.read()
                continue

            # Group on raw words so the cap means the same thing everywhere,
            # then emit the preprocessed tokens that fall in each group.
            raw_groups = group_by_counts(
                [len(p["text"].split()) for p in paragraphs], max_chunk_size
            )
            per_paragraph = assign_preproc_tokens(paragraphs, tokens_obj)
            emitted = False
            for group in raw_groups:
                text = " ".join(tok for i in group for tok in per_paragraph[i])
                if text.strip():
                    emitted = True
                    yield text
            if not emitted:
                # Every paragraph was stopworded away; keep the row so the
                # corpus size still matches what the caller counted.
                yield ""

        if degraded == total_docs:
            # Not a degradation but a misconfiguration: max_chunk_size was
            # asked for and nothing was chunked, so the run would silently
            # produce exactly the unchunked model. That is how a chunked
            # Condorcet build came out byte-identical to the unchunked one.
            raise RuntimeError(
                f"max_chunk_size={max_chunk_size} was set but none of {total_docs} docs could be "
                "chunked: raw_paragraphs, tokens/*.pkl, or paragraph byte spans are missing from "
                "the preprocessed data. Re-run preprocessing (do not pass --preprocessed_data_path "
                "with a tarball built before paragraph byte spans were recorded)."
            )
        if degraded:
            print(
                f"Warning: {degraded}/{total_docs} docs could not be chunked (missing raw_paragraphs, "
                "tokens, or byte spans) and were used whole. Re-run preprocessing to chunk them.",
                flush=True,
            )

    def __iter__(self):
        if self.max_chunk_size:
            yield from self.iter_chunk_texts(self.max_chunk_size)
            return
        for _, file_path, _ in self.iter_doc_entries():
            with open(file_path, encoding="utf8") as input_file:
                yield input_file.read()

    def random_sample(self, proportion=0.8):
        for collection in iter_text_collections(self.text_path):
            texts_dir = os.path.join(collection.path, "texts")
            file_paths = [f.path for f in os.scandir(texts_dir) if f.name.isdigit()]
            sample_size = floor(len(file_paths) * proportion)
            for file in random.sample(file_paths, sample_size):
                with open(file, encoding="utf8") as input_file:
                    yield input_file.read()


class Corpus:
    def __init__(
        self,
        source_files_path,
        language=None,
        ngram=(1, 1),
        vectorization="tfidf",
        max_relative_frequency=1.0,
        min_absolute_frequency=0,
        max_features=None,
        vectorizer=None,
        max_chunk_size=None,
    ):
        self.metadata = self.__get_metadata(source_files_path)
        self.ngram = ngram if len(ngram) == 2 else (ngram[0], ngram[0])
        self._max_relative_frequency = max_relative_frequency
        self._min_absolute_frequency = min_absolute_frequency
        self.max_features = max_features
        self.max_chunk_size = max_chunk_size
        self.texts_to_vectorize = savedTexts(source_files_path, max_chunk_size=max_chunk_size)
        self._vectorization = vectorization

        if vectorizer is None:
            if vectorization == "tfidf":
                self.vectorizer = TfidfVectorizer(
                    ngram_range=self.ngram,
                    max_df=max_relative_frequency,
                    min_df=min_absolute_frequency,
                    max_features=max_features,
                    smooth_idf=True,
                    sublinear_tf=True,
                )
            elif vectorization == "tf":
                self.vectorizer = CountVectorizer(
                    ngram_range=self.ngram,
                    max_df=max_relative_frequency,
                    min_df=min_absolute_frequency,
                    max_features=max_features,
                )
            else:
                raise ValueError(f"Unknown vectorization type: {vectorization!r}")
            self.sklearn_vector_space = self.vectorizer.fit_transform(self.texts_to_vectorize)
        else:
            self.vectorizer = vectorizer
            self.sklearn_vector_space = self.vectorizer.transform(self.texts_to_vectorize)

        self.size = self.sklearn_vector_space.shape[0]
        self.feature_names = self.vectorizer.get_feature_names_out()
        self.annoy_index = None

    def __get_metadata(self, data_path):
        metadata = {}
        for text_collection in iter_text_collections(data_path):
            with open(os.path.join(text_collection.path, "metadata.pickle"), "rb") as f:
                metadata.update(pickle.load(f))
        return metadata

    def docs(self):
        """Iterate the raw doc strings in the same order as sklearn_vector_space rows.

        Used by embedding-based topic models (BERTopic) which operate on raw
        text rather than the bag-of-words matrix.
        """
        return iter(self.texts_to_vectorize)

    def build_chunks(self, max_chunk_size):
        """Split every document into chunks of at most `max_chunk_size` raw words.

        Returns (texts, doc_index, tokens): parallel arrays where doc_index[i]
        is the sklearn_vector_space ROW of the document chunk i belongs to.
        Chunks never span documents, so this mapping is what lets a
        chunk-level model report a document-level result.

        Cheap (reads JSON, no model), so it is recomputed rather than cached
        even when the embeddings themselves are cached.
        """
        import json as _json

        from topologic.chunking import group_paragraphs_into_chunks

        texts: list = []
        doc_index: list = []
        tokens: list = []
        oversized = 0
        for row, (doc_id, text_file_path, collection_path) in enumerate(
            self.texts_to_vectorize.iter_doc_entries()
        ):
            chunks: list = []
            p_path = os.path.join(collection_path, "raw_paragraphs", f"{doc_id}.json")
            if os.path.exists(p_path):
                with open(p_path, encoding="utf-8") as f:
                    paragraphs = _json.load(f)
                chunks = group_paragraphs_into_chunks(paragraphs, max_chunk_size)
            if not chunks:
                # Fallback: preprocessed text as a single chunk. Worse quality
                # (spacy-tokenized) but keeps the pipeline going if
                # raw_paragraphs is missing for some doc.
                with open(text_file_path, encoding="utf-8") as f:
                    body = f.read()
                chunks = [{"philo_ids": [], "text": body, "tokens": len(body.split())}]
            kept = [c for c in chunks if c["text"].strip()]
            if not kept:
                kept = [{"philo_ids": [], "text": "", "tokens": 0}]
            for c in kept:
                texts.append(c["text"])
                doc_index.append(row)
                tokens.append(c["tokens"])
                if c["tokens"] > max_chunk_size:
                    oversized += 1

        if len(set(doc_index)) != self.size:
            raise RuntimeError(
                f"Chunked {len(set(doc_index))} docs but corpus size is {self.size}"
            )
        if oversized:
            # A paragraph longer than the cap cannot be split without breaking
            # the one guarantee callers rely on, so it becomes an over-cap
            # chunk. Say so: for embedding backends it means the tokenizer
            # silently drops the tail.
            print(
                f"Warning: {oversized} chunks exceed max_chunk_size={max_chunk_size} because a "
                f"single paragraph does. Embedding backends will truncate these.",
                flush=True,
            )
        return texts, np.asarray(doc_index, dtype=np.int64), np.asarray(tokens, dtype=np.int64)

    def compute_or_load_embeddings(self, model_name, batch_size=32, max_chunk_size=None):
        """Embed every chunk of every document. No pooling.

        Returns (ChunkedCorpus, embedder) with one row per CHUNK, not per
        document.

        Mean-pooling chunk embeddings into a document vector used to happen
        here and was wrong: the mean of points on a sphere is not on the
        sphere, so a document spanning several topics landed in empty space
        between the clusters rather than in any of them. On Condorcet that hit
        40% of documents, the largest averaging 67 chunks into one vector.
        Callers aggregate in TOPIC space instead, which is additive and valid.

        `max_chunk_size` is in raw words and is clamped to what the embedder
        can actually encode. Left as None it defaults to the model's own
        limit.

        Cache lives next to the texts dir so it survives the
        `--preprocessed_data_path` tar/decompress flow, keyed on the sanitized
        model name and the chunk size (which changes the chunking).
        """
        if self.max_chunk_size:
            raise RuntimeError(
                "compute_or_load_embeddings chunks from raw_paragraphs itself, so it cannot "
                "run on a Corpus that is already chunk-level — the rows would no longer line "
                "up with raw_paragraphs. Build the corpus with max_chunk_size=None for "
                "embedding backends (build_model does this)."
            )
        # Load the embedder regardless of cache state: the caller passes it to
        # BERTopic as embedding_model (for topic embeddings / outlier
        # strategies), so it is needed even on a pure cache hit. Caller frees
        # it via `del` when done.
        embedder = self._load_embedder(model_name)

        # Convert subword max_seq_length to a raw-word budget. Multilingual
        # subword tokenizers (XLM-R, BPE) average ~1.6 subwords per word for
        # European languages; the 0.9 factor leaves headroom against
        # punctuation and rare tokens. Now that grouping honours this as a
        # ceiling rather than a floor, the headroom is real.
        model_limit = max(int(embedder.max_seq_length / 1.6 * 0.9), 32)
        if max_chunk_size is None:
            cap = model_limit
        elif max_chunk_size > model_limit:
            print(
                f"Warning: max_chunk_size={max_chunk_size} exceeds what {model_name} can encode "
                f"({model_limit} raw words); clamping to {model_limit}.",
                flush=True,
            )
            cap = model_limit
        else:
            cap = int(max_chunk_size)
        print(
            f"Embedder {model_name}: max_seq_length={embedder.max_seq_length} subwords; "
            f"chunk cap {cap} raw words.",
            flush=True,
        )

        texts, doc_index, tokens = self.build_chunks(cap)

        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", model_name)
        # v3: one row per chunk rather than per document, so the cache carries
        # the doc mapping alongside. Keyed on the cap too, since changing it
        # changes the chunking.
        cache_path = os.path.join(
            self.texts_to_vectorize.text_path, f"embeddings_v3_{safe_name}_c{cap}.npz"
        )
        if os.path.exists(cache_path):
            cached = np.load(cache_path)
            if cached["embeddings"].shape[0] == len(texts):
                print(f"Loaded cached embeddings from {cache_path}", flush=True)
                return ChunkedCorpus(texts, cached["embeddings"], cached["doc_index"], cached["tokens"]), embedder
            print(
                f"Cached embeddings at {cache_path} have stale shape "
                f"{cached['embeddings'].shape}; recomputing.",
                flush=True,
            )

        print(f"Embedding {len(texts)} chunks across {self.size} docs...", flush=True)
        embeddings = embedder.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=True,
            convert_to_numpy=True,
        )
        np.savez(cache_path, embeddings=embeddings, doc_index=doc_index, tokens=tokens)

        self._empty_cuda_cache()
        return ChunkedCorpus(texts, embeddings, doc_index, tokens), embedder

    @staticmethod
    def _empty_cuda_cache():
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

    @staticmethod
    def _load_embedder(model_name):
        """Construct a SentenceTransformer with bf16/fp16 on GPU when possible.

        Embedding inference doesn't need fp32 precision; bf16 doubles
        throughput on modern GPUs without measurable quality loss. bf16 has
        fp32's exponent range so it dodges fp16 overflow issues in attention;
        we fall back to fp16 on pre-Ampere cards.
        """
        from sentence_transformers import SentenceTransformer

        embedder = SentenceTransformer(model_name, trust_remote_code=True)
        try:
            import torch
            if torch.cuda.is_available():
                if torch.cuda.get_device_capability()[0] >= 8:
                    embedder = embedder.to(dtype=torch.bfloat16)
                    print("Embedder: cast to bfloat16 for inference.", flush=True)
                else:
                    embedder = embedder.half()
                    print("Embedder: cast to float16 for inference.", flush=True)
        except ImportError:
            pass
        return embedder

    def sample_corpus(self):
        self.sklearn_vector_space = self.vectorizer.transform(self.texts_to_vectorize.random_sample())

    def build_annoy_index(self):
        print("Building Annoy index of document vectors...", flush=True)
        self.annoy_index = AnnoyIndex(self.sklearn_vector_space.shape[1], "angular")
        for i, doc_vector in tqdm(
            enumerate(self.sklearn_vector_space),
            total=self.size,
            desc="Adding document vectors to Annoy index",
            leave=False,
        ):
            self.annoy_index.add_item(i, doc_vector.toarray()[0])
        self.annoy_index.build(1000, n_jobs=cpu_count() - 1)

    def similar_docs_by_vector(self, doc_id, num_docs):
        docs, scores = self.annoy_index.get_nns_by_item(doc_id, num_docs + 1, include_distances=True)
        return [(doc, score) for doc, score in zip(docs, scores) if doc != doc_id]

    def similar_docs_by_topic_distribution(self, doc_id, num_docs, topic_model):
        docs, scores = topic_model.annoy_index.get_nns_by_item(doc_id, num_docs + 1, include_distances=True)
        return [(doc, score) for doc, score in zip(docs, scores) if doc != doc_id]
