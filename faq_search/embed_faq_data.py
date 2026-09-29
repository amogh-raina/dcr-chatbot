#!/usr/bin/env python3
"""
embed_faq_data.py -- build-time step that computes sentence embeddings for
every canonical_question and question_variant in faq_qa_records.json, and
writes them to a companion artifact (NOT back into the records file).

Why separate from faq_qa_records.json:
- The records file is meant to stay human-readable data + provenance
  metadata (status/gap_note/dcr_note), reviewable and diffable in git.
  Vectors are large, opaque, and tied to a specific embedding model;
  keeping them in their own artifact means re-embedding with a
  different/better model later never touches the reviewed data model file.

What gets embedded (and why):
- canonical_question and every question_variant, for every record
  regardless of status -- including gap_stub records that have no
  answer_text yet. A gap_stub's *question* is still real (a user will type
  it), so embedding it lets the search layer recognize "this is a known
  documented gap" and return a distinct message (e.g. "we don't have a
  vetted answer for this yet") instead of a generic low-confidence
  fallback. Pass --skip-unanswered to exclude gap_stub questions if you'd
  rather they just fall through to the normal fallback path.
- answer_text, gap_note, and dcr_note are never embedded -- they aren't
  things a user types, and mixing answer text into the same vector space
  as questions would blur question-to-question matching.

Output (two files, written into the same directory as the input JSON by
default):
- faq_embeddings.npy       float32 array, shape (N, dim), L2-normalized
                           rows, so cosine similarity == dot product at
                           query time.
- faq_embeddings_meta.json one entry per row: {row, id, kind
                           ("canonical"|"variant"), variant_index, text,
                           status}, plus a header with model name,
                           dimension, similarity convention, coverage
                           counts, and build time.

At query time: embed the user's message with the same model, L2-normalize
it, dot it against every row of faq_embeddings.npy, then take the max
score per record id (its best-matching variant) as that record's score --
that max-per-record score is what the existing 0.80 / 0.50 thresholds
should be compared against.

Usage:
    conda activate dcr
    pip install -r faq_search/requirements.txt   # first time only
    python faq_search/embed_faq_data.py

    # override the model:
    python faq_search/embed_faq_data.py --model sentence-transformers/all-MiniLM-L6-v2

Default model: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2.
Chosen over an English-only model (e.g. all-MiniLM-L6-v2 -- same 384 dims,
smaller and faster) because the source content is bilingual (Danish su.dk
originals, English content-model translations) and it isn't yet confirmed
whether live users will type Danish or English questions. If you know
queries will always be English, switch to all-MiniLM-L6-v2 for a faster,
smaller model with no quality loss on English text.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

DEFAULT_MODEL = "Qwen/Qwen3-Embedding-0.6B"
FALLBACK_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
HERE = Path(__file__).resolve().parent
DEFAULT_INPUT = HERE / "data" / "faq_qa_records.json"
DEFAULT_OUTPUT_DIR = HERE / "data"


def collect_texts(records: list[dict], skip_unanswered: bool) -> list[dict]:
    """Flatten records into one row per embeddable text.

    Returns a list of meta dicts (no vector yet, no 'row' index yet);
    embed_texts() is called on [r["text"] for r in rows] in this same
    order, and main() stamps 'row' on afterwards.
    """
    rows: list[dict] = []
    for rec in records:
        if skip_unanswered and rec.get("status") == "gap_stub":
            continue
        rid = rec["id"]
        status = rec.get("status")

        canonical = (rec.get("canonical_question") or "").strip()
        if canonical:
            rows.append(
                {
                    "id": rid,
                    "kind": "canonical",
                    "variant_index": None,
                    "text": canonical,
                    "status": status,
                }
            )

        for i, variant in enumerate(rec.get("question_variants") or []):
            variant = (variant or "").strip()
            if not variant:
                continue
            rows.append(
                {
                    "id": rid,
                    "kind": "variant",
                    "variant_index": i,
                    "text": variant,
                    "status": status,
                }
            )
    return rows


def embed_texts(texts: list[str], model_name: str, batch_size: int = 64):
    """Encode texts with a sentence-transformers model. Imports are local
    so this whole module can be imported (and collect_texts unit-tested)
    without sentence-transformers/numpy/torch installed.
    """
    from sentence_transformers import SentenceTransformer

    try:
        model = SentenceTransformer(model_name)
    except Exception as e:
        print(f"Warning: Failed to load {model_name} ({e}). Falling back to {FALLBACK_MODEL}...")
        model_name = FALLBACK_MODEL
        model = SentenceTransformer(model_name)

    vectors = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,  # L2-normalize so cosine sim == dot product
    )
    return vectors.astype("float32"), model_name


def build_meta(rows: list[dict], vectors, model_name: str, args, data: dict) -> dict:
    for i, r in enumerate(rows):
        r["row"] = i
    return {
        "model": model_name,
        "dim": int(vectors.shape[1]),
        "normalized": True,
        "similarity": "dot_product (== cosine, since rows are L2-normalized)",
        "num_rows": len(rows),
        "num_records_covered": len({r["id"] for r in rows}),
        "num_records_total": len(data["records"]),
        "skip_unanswered": args.skip_unanswered,
        "source_schema_version": data.get("schema_version"),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "rows": rows,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Compute sentence embeddings for faq_qa_records.json question text."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument(
        "--skip-unanswered",
        action="store_true",
        help="Exclude gap_stub records (no answer_text yet) from the index.",
    )
    args = parser.parse_args()

    data = json.loads(args.input.read_text(encoding="utf-8"))
    records = data["records"]

    rows = collect_texts(records, args.skip_unanswered)
    if not rows:
        print("No embeddable text found -- nothing to do.", file=sys.stderr)
        sys.exit(1)

    texts = [r["text"] for r in rows]
    print(f"Embedding {len(texts)} texts from {len(records)} records with {args.model} ...")
    vectors, actual_model = embed_texts(texts, args.model, args.batch_size)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    npy_path = args.output_dir / "faq_embeddings.npy"
    meta_path = args.output_dir / "faq_embeddings_meta.json"

    import numpy as np

    np.save(npy_path, vectors)

    meta = build_meta(rows, vectors, actual_model, args, data)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote {npy_path} ({vectors.shape[0]} x {vectors.shape[1]}, float32)")
    print(f"Wrote {meta_path}")
    print(
        f"Covered {meta['num_records_covered']}/{meta['num_records_total']} records "
        f"({'including' if not args.skip_unanswered else 'excluding'} gap_stub questions)."
    )


if __name__ == "__main__":
    main()
