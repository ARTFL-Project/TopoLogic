"""Paragraph extraction and embed-time chunk grouping for SBERT embedding.

Each "doc" in the topologic sense is one PhiloLogic object at the configured
level (div3, doc, …). This module:

  - extracts that object's paragraphs (atomic units, never crossing the
    object boundary) during preprocessing — saved as
    `raw_paragraphs/{doc_id}.json`,
  - regroups those paragraphs into model-adaptive chunks at embed time
    (chunk size derived from the SBERT model's `max_seq_length`).

Splitting it this way means the preprocessed tarball is portable across
embedding models — switching from a 128-token MiniLM to an 8192-token
bge-m3 just changes how paragraphs are grouped, no re-preprocessing.
"""

import json
import os
from bisect import bisect_right
from math import ceil
from typing import List, Tuple

import lz4.frame


def _load_lz4(path: str) -> List[Tuple[int, int, str, List[str], str]]:
    """Yield-style loader for a PhiloLogic words_and_philo_ids/*.lz4 file.

    Returns a list of (start_byte, end_byte, token, position_parts, philo_type)
    tuples, sorted by file order. Returns [] if the file is missing.
    """
    tokens: List[Tuple[int, int, str, List[str], str]] = []
    if not os.path.exists(path):
        return tokens
    with lz4.frame.open(path, "rb") as fh:
        for line in fh:
            line = line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            sb = rec.get("start_byte", 0)
            eb = rec.get("end_byte", 0)
            if eb <= sb:
                continue
            pos = (rec.get("position") or "").split()
            tokens.append((sb, eb, rec.get("token", ""), pos, rec.get("philo_type", "word")))
    return tokens


def iter_doc_paragraphs(
    philo_db_path: str,
    philo_id_parts: List[str],
    level_depth: int,
    lz4_cache: dict = None,
) -> List[dict]:
    """Extract paragraphs (atomic units) for one topologic doc.

    `philo_id_parts` is the configured-level philo id split (e.g.
    `["1", "2", "3"]` for a div3 with depth 3). Tokens outside this object
    are filtered out, so paragraphs strictly stay within the object boundary.

    Returns `{"philo_id", "text", "start_byte", "end_byte"}` in document order;
    the byte span is what `assign_preproc_tokens` maps against.
    """
    lz4_path = os.path.join(philo_db_path, "data", "words_and_philo_ids", f"{philo_id_parts[0]}.lz4")
    if lz4_cache is not None and lz4_path in lz4_cache:
        all_tokens = lz4_cache[lz4_path]
    else:
        all_tokens = _load_lz4(lz4_path)
        if lz4_cache is not None:
            lz4_cache[lz4_path] = all_tokens
    if not all_tokens:
        return []

    level_tokens = [t for t in all_tokens if t[3][:level_depth] == philo_id_parts]
    if not level_tokens:
        return []
    level_tokens.sort(key=lambda t: t[0])

    paragraphs = []
    cur_key = None
    cur_words: list = []
    cur_start = 0
    cur_end = 0
    for sb, eb, tok, pos, ptype in level_tokens:
        key = tuple(pos[:5]) if len(pos) >= 5 else tuple(pos)
        if key != cur_key:
            if cur_words and cur_key is not None:
                paragraphs.append({
                    "philo_id": " ".join(str(v) for v in cur_key),
                    "text": " ".join(cur_words),
                    "start_byte": cur_start,
                    "end_byte": cur_end,
                })
            cur_key = key
            cur_words = []
            cur_start, cur_end = sb, eb
        if tok:
            cur_words.append(tok)
            cur_end = max(cur_end, eb)
    if cur_words and cur_key is not None:
        paragraphs.append({
            "philo_id": " ".join(str(v) for v in cur_key),
            "text": " ".join(cur_words),
            "start_byte": cur_start,
            "end_byte": cur_end,
        })
    return paragraphs


def group_by_counts(counts: List[int], cap: int) -> List[List[int]]:
    """Group consecutive items into buckets of at most `cap`, by their counts.

    A ceiling, not a floor. Bucket count is fixed up front (ceil(total / cap))
    and each bucket targets the even split, so there is no runt at the end.
    Items are never split: one larger than `cap` becomes an oversized bucket of
    its own, which callers detect from the bucket total.

    Returns lists of indices into `counts`.
    """
    if not counts:
        return []
    total = sum(counts)
    cap = max(int(cap), 1)
    remaining = total
    buckets_left = max(1, ceil(total / cap))

    groups: List[List[int]] = []
    bucket: List[int] = []
    bucket_count = 0
    for idx, count in enumerate(counts):
        # Recomputed each step so rounding spreads across the remaining
        # buckets rather than landing in the last one.
        target = remaining / buckets_left if buckets_left > 0 else cap
        # Zero-count buckets are never committed, so items contributing nothing
        # (stopworded captions) fold forward; nor are empty ones, since a lone
        # over-cap item has nowhere else to go.
        if bucket and bucket_count > 0 and (bucket_count + count > cap or bucket_count >= target):
            groups.append(bucket)
            remaining -= bucket_count
            buckets_left = max(1, buckets_left - 1)
            bucket, bucket_count = [], 0
        bucket.append(idx)
        bucket_count += count
    if bucket:
        groups.append(bucket)
    return groups


def assign_preproc_tokens(paragraphs: List[dict], tokens_obj) -> List[List[str]]:
    """Map preprocessed tokens onto their source paragraphs by byte range.

    Preprocessing drops tokens but never moves them, so a survivor's
    `ext["start_byte"]` still falls inside its paragraph's raw span. Returns a
    list parallel to `paragraphs`; fully-stopworded paragraphs come back empty.
    """
    per_paragraph: List[List[str]] = [[] for _ in paragraphs]
    if tokens_obj is None or not paragraphs:
        return per_paragraph
    starts = [p.get("start_byte", 0) for p in paragraphs]
    ends = [p.get("end_byte", 0) for p in paragraphs]
    for token in tokens_obj:
        text = getattr(token, "text", None)
        if not text or not text.strip() or text == "#DEL#":
            continue
        ext = getattr(token, "ext", None) or {}
        start = ext.get("start_byte")
        if start is None:
            continue
        idx = bisect_right(starts, start) - 1
        if idx < 0 or idx >= len(paragraphs) or start > ends[idx]:
            continue
        per_paragraph[idx].append(text)
    return per_paragraph


def group_paragraphs_into_chunks(paragraphs: List[dict], max_raw_tokens: int) -> List[dict]:
    """Group paragraphs into chunks of at most `max_raw_tokens` words.

    Paragraphs are never split, so one longer than the cap becomes an oversized
    chunk; callers check `tokens` and report it, since for embedding backends
    it means tokenizer truncation.

    Returns `{"philo_ids": [...], "text": "...", "tokens": N}` per chunk.
    """
    if not paragraphs:
        return []

    counts = [len(p["text"].split()) for p in paragraphs]
    groups = group_by_counts(counts, max_raw_tokens)

    chunks = []
    for idx_group in groups:
        chunks.append({
            "philo_ids": [paragraphs[i]["philo_id"] for i in idx_group],
            "text": " ".join(paragraphs[i]["text"] for i in idx_group if paragraphs[i]["text"]),
            "tokens": sum(counts[i] for i in idx_group),
        })
    return chunks


def write_raw_paragraphs_for_metadata(
    metadata: dict,
    db_name: str,
    philo_db_path: str,
    level: str,
    object_levels: dict,
    out_dir: str,
    progress_desc: str = None,
) -> int:
    """Write `{out_dir}/{doc_id}.json` paragraph files for every doc in metadata.

    Atomic-paragraph format — embed-time chunking is handled separately so
    the same preprocessed tarball can drive any SBERT model regardless of
    its context window.

    `metadata` is the dict written by prepare_data —
    `{doc_id: {philo_db, philo_<level>_id, ...}}`. Returns the number of
    docs successfully written.
    """
    from tqdm import tqdm

    level_depth = object_levels.get(level)
    if level_depth is None:
        return 0
    os.makedirs(out_dir, exist_ok=True)
    lz4_cache: dict = {}
    written = 0
    iterator = metadata.items()
    if progress_desc is not None:
        iterator = tqdm(iterator, total=len(metadata), desc=progress_desc, leave=False)
    philo_id_field = f"philo_{level}_id"
    for doc_id, meta in iterator:
        if meta.get("philo_db") != db_name:
            continue
        raw_pid = str(meta.get(philo_id_field, "")).strip()
        if not raw_pid:
            continue
        pid_parts = raw_pid.split()[:level_depth]
        if len(pid_parts) < level_depth:
            continue
        paragraphs = iter_doc_paragraphs(
            philo_db_path,
            pid_parts,
            level_depth,
            lz4_cache=lz4_cache,
        )
        if not paragraphs:
            continue
        with open(os.path.join(out_dir, f"{int(doc_id)}.json"), "w", encoding="utf-8") as f:
            json.dump(paragraphs, f, ensure_ascii=False)
        written += 1
    return written
