"""LLM-based topic labeler CLI.

Runs in its own venv so it can pin `transformers>=4.56` without conflicting
with `spacy-transformers`'s upper bound in the main topologic environment.

Reads `topic_words.json`, produces a short human-readable `label` for each
topic, and writes the file back in place.

Input preference:
- Uses the per-topic `top_words` field (top 20 words + weights) when present.
- Falls back to parsing `description` (top 10, comma-separated, no weights)
  so older `topic_words.json` files from pre-labeler builds still work.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Tuple

from tqdm import tqdm


PROMPT_INSTRUCTION = (
    "You are labeling topics from a topic model. Given the characteristic terms "
    "of one topic (ordered by weight, most important first, with weights), "
    "return a single {language} label that names the underlying theme.\n\n"
    "Rules — read carefully:\n"
    "1. Produce a noun phrase of 1 to 5 words. Prefer a single well-chosen word "
    "when a precise hypernym captures the theme (e.g., \"Fiscalité\", \"Religion\", "
    "\"Grammaire\") — a short label is usually better than a padded one.\n"
    "2. Consider ALL the terms in the list — including the lower-weighted ones. "
    "They are essential clues for disambiguating what the high-weight terms mean.\n"
    "3. NEVER output the pattern \"<top_word_1> <and/et/y/und/&/etc.> <top_word_2>\" "
    "or any trivial concatenation of the top two words with a conjunction. That "
    "is always considered a FAILED label — synthesize at a higher level of "
    "abstraction instead.\n"
    "4. Do not repeat a word and its adjective form (e.g., \"Religion religieuse\" "
    "is a tautology — write \"Religion\" or something more specific).\n"
    "5. If a word has multiple meanings (e.g., \"corps\" = human body OR political "
    "body), use the surrounding terms in the list to pick the right sense.\n"
    "6. If the terms are so generic or heterogeneous that no clear theme emerges, "
    "label it as a residual/abstract category (e.g., \"Vocabulaire abstrait\", "
    "\"Abstract vocabulary\") rather than forcing a false specific theme.\n"
    "7. Return only the label — no quotes, no explanation, no trailing punctuation.\n"
    "8. The label MUST be written in {language}. Even if the terms look like "
    "English or another language, your response is in {language}.\n\n"
    "Examples (apply the pattern in {language}):\n"
    "- terms [tax, owner, revenue, rate, value]\n"
    "    GOOD: \"Property taxation\"    BAD: \"Tax and owner\"\n"
    "- terms [science, art, genius, glory, talent, discovery, progress]\n"
    "    GOOD: \"Intellectual achievement\"    BAD: \"Science and art\"\n"
    "- terms [life, death, honor, parliament, protestant, magistrate, eulogy, friendship]\n"
    "    GOOD: \"Civic memorials\"    BAD: \"Life and death\"\n"
    "- terms [body, member, council, committee, session, deliberation]\n"
    "    GOOD: \"Legislative bodies\"    BAD: \"Body and member\" (AND never read \"body\" as anatomical when \"council\" appears)\n"
    "- terms [law, system, movement, legislation, execution, legislator]\n"
    "    GOOD: \"Lawmaking process\"    BAD: \"Law and movement\"\n"
    "- terms [religion, priest, god, clergy, worship, ritual]\n"
    "    GOOD: \"Religious practice\"    BAD: \"Religion religious\"  or  \"Religion and priest\"\n"
    "- terms [armée, troupe, ennemi, bataille, combat]\n"
    "    GOOD: \"Art militaire\"    BAD: \"Armée et troupe\"\n"
    "- terms [time, place, moment, motive, sort, gathering, side]  (generic)\n"
    "    GOOD: \"Abstract vocabulary\"    BAD: \"Time management\"\n"
)


def _format_payload(top_words: List[Tuple[str, float]]) -> str:
    """Render the top-words list as a compact JSON array the model can parse."""
    payload = [{"word": w, "weight": round(float(weight), 4)} for w, weight in top_words]
    return json.dumps(payload, ensure_ascii=False)


def _extract_top_words(entry: Dict[str, Any]) -> List[Tuple[str, float]]:
    """Prefer the rich `top_words` field. Fall back to parsing `description`."""
    raw = entry.get("top_words")
    if raw:
        # Stored as [[word, weight], ...].
        return [(item[0], float(item[1])) for item in raw]
    # Legacy fallback: 10-word comma list, no weights — synthesize rank-based weights
    # so the prompt still conveys ordering.
    words = [w.strip() for w in entry.get("description", "").split(",") if w.strip()]
    n = len(words) or 1
    return [(w, round((n - i) / n, 3)) for i, w in enumerate(words)]


def label_topics(
    top_words_by_topic: Dict[int, List[Tuple[str, float]]],
    model_id: str,
    language: str = "English",
) -> Dict[int, str]:
    try:
        from transformers import pipeline
        from transformers import logging as transformers_logging
    except ImportError as e:
        print(f"topologic-labeler: transformers not available ({e})", file=sys.stderr)
        return {}

    # Silence the per-generation "both max_new_tokens and max_length set"
    # warning — it's benign (max_new_tokens correctly wins) but floods stderr.
    transformers_logging.set_verbosity_error()

    try:
        pipe = pipeline(
            "text-generation",
            model=model_id,
            torch_dtype="auto",
            device_map="auto",
        )
    except Exception as e:
        print(f"topologic-labeler: failed to load {model_id} ({e})", file=sys.stderr)
        return {}

    instruction = PROMPT_INSTRUCTION.format(language=language)

    labels: Dict[int, str] = {}
    for topic_id in tqdm(sorted(top_words_by_topic), desc="Labeling topics"):
        payload = _format_payload(top_words_by_topic[topic_id])
        # Merged user turn — Gemma's chat template rejects `system`.
        messages = [
            {"role": "user", "content": f"{instruction}\nterms: {payload}\n\nLabel:"},
        ]
        try:
            out = pipe(messages, max_new_tokens=24, max_length=None, do_sample=False)
        except Exception as e:
            print(f"topologic-labeler: topic {topic_id} failed: {e}", file=sys.stderr)
            continue

        gen = out[0]["generated_text"]
        raw = gen[-1]["content"] if isinstance(gen, list) else gen
        label = raw.strip().strip('"\'`.').splitlines()[0].strip()
        # Trim a leading "Label:" the model sometimes repeats.
        for prefix in ("Label:", "label:"):
            if label.startswith(prefix):
                label = label[len(prefix):].strip()
        label = label.strip('"\'`.')[:80]
        if label:
            labels[topic_id] = label

    return labels


def relabel_json(path: str, model_id: str, language: str) -> int:
    with open(path, "r", encoding="utf-8") as f:
        topics = json.load(f)

    top_words_by_topic = {int(entry["name"]): _extract_top_words(entry) for entry in topics}

    labels = label_topics(top_words_by_topic, model_id=model_id, language=language)
    if not labels:
        print("topologic-labeler: no labels produced; file not modified.", file=sys.stderr)
        return 0

    for entry in topics:
        label = labels.get(int(entry["name"]))
        if label:
            entry["label"] = label
        else:
            entry.pop("label", None)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(topics, f, indent=None)
    return len(labels)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="topologic-labeler",
        description="Relabel topics in an existing topic_words.json using an LLM.",
    )
    parser.add_argument("topic_words_path", help="Path to topic_words.json to update in place")
    parser.add_argument("--model", required=True, help="HuggingFace instruction-tuned model ID")
    parser.add_argument("--language", default="English", help="Language for generated labels")
    args = parser.parse_args()

    n = relabel_json(args.topic_words_path, args.model, args.language)
    print(f"topologic-labeler: wrote {n} labels to {args.topic_words_path}")


if __name__ == "__main__":
    main()
