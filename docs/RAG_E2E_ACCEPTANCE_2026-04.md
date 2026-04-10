# RAG E2E Acceptance (20.7)

This document defines launch gates for hybrid retrieval quality.

## Pipeline baseline

- Retrieval: lexical + graph candidates
- Fusion: RRF
- Rerank: lightweight cross score
- Anti-drift: minimum anchor overlap
- Output: bounded top-k context (U-curve guard)

## Required metrics

- faithfulness
- context_precision
- context_recall
- answer_relevancy
- not_found_rate

## Acceptance rule

- Hybrid retrieval is accepted only if E2E quality is not lower than baseline RAG.
- Target uplift must be recorded per channel and language.

## Suggested KPI thresholds

- faithfulness >= 0.95
- answer_relevancy >= 0.90
- not_found_rate <= 0.10
- no increase in critical hallucination rate

## Test dataset

- Per camp: 10-15 prompts minimum
- Languages: UA + PL (+ EN fallback checks)
- Channels: Telegram, Web, Meta, WhatsApp

## Reporting format

- date/time
- git commit
- config values (`rag_top_k`, `rag_rrf_k`, anchor threshold)
- per-category metric table
- pass/fail decision
