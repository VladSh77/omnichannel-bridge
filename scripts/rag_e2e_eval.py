#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lightweight E2E evaluator for RAG answer quality.

Input: JSONL where each row has:
{
  "faithful": true/false,
  "relevant": true/false,
  "context_precision": 0..1,
  "context_recall": 0..1,
  "not_found": true/false
}
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/rag_e2e_eval.py <dataset.jsonl>")
        return 2
    path = Path(sys.argv[1]).resolve()
    if not path.is_file():
        print(f"File not found: {path}")
        return 2

    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    if not rows:
        print("Dataset is empty.")
        return 2

    n = len(rows)
    faith = sum(1 for r in rows if bool(r.get("faithful")))
    rel = sum(1 for r in rows if bool(r.get("relevant")))
    nf = sum(1 for r in rows if bool(r.get("not_found")))
    cp = sum(float(r.get("context_precision", 0.0)) for r in rows) / n
    cr = sum(float(r.get("context_recall", 0.0)) for r in rows) / n

    print("RAG_E2E_REPORT")
    print(f"- samples: {n}")
    print(f"- faithfulness: {faith / n:.4f}")
    print(f"- answer_relevancy: {rel / n:.4f}")
    print(f"- context_precision: {cp:.4f}")
    print(f"- context_recall: {cr:.4f}")
    print(f"- not_found_rate: {nf / n:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
