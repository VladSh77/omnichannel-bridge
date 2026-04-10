#!/usr/bin/env python3
"""Split 00_offer2026_brochure.md into part files (no OCR)."""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
KB = REPO_ROOT.parent / "camp" / "knowledge-base"
SRC = KB / "00_offer2026_brochure.md"
SLIDES_PER_PART = 6
MAX_PART_CHARS = 9000

HEADER = """---
tags: [campscout, offer, marketing, 2026, ocr]
status: reference
source: Offer2026_unpacked PNG slides (macOS Vision OCR)
---

> OCR (PL/EN/UA). Для цін, дат і юридичних фактів — **звіряти з Odoo і** [00_company.md](00_company.md); це маркетингова брошура.

"""


def main() -> None:
    raw = SRC.read_text(encoding="utf-8")
    if raw.startswith("---"):
        i = raw.find("\n---\n", 3)
        if i != -1:
            raw = raw[i + 5 :]
    sections = re.split(r"(?=^## Слайд \d+\s*$)", raw, flags=re.M)
    slide_blocks: list[tuple[int, str]] = []
    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue
        m = re.match(r"^## Слайд (\d+)\s*\n", sec, re.M)
        if m:
            slide_blocks.append((int(m.group(1)), sec))
    slide_blocks.sort(key=lambda x: x[0])

    for old in KB.glob("00_offer2026_brochure_part*.md"):
        old.unlink()

    part_idx = 0
    buf: list[str] = []
    start_slide: int | None = None

    def flush() -> None:
        nonlocal part_idx, buf, start_slide
        if not buf or start_slide is None:
            return
        part_idx += 1
        last_m = re.search(r"^## Слайд (\d+)", buf[-1], re.M)
        last_i = int(last_m.group(1)) if last_m else start_slide
        path = KB / f"00_offer2026_brochure_part{part_idx:02d}.md"
        body = HEADER + f"# Оферта Camp Scout 2026 — слайди {start_slide}–{last_i}\n\n" + "\n\n".join(buf)
        path.write_text(body, encoding="utf-8")
        buf = []
        start_slide = None

    for si, block in slide_blocks:
        if not buf:
            start_slide = si
        buf.append(block)
        joined = "\n\n".join(buf)
        if len(joined) >= MAX_PART_CHARS:
            flush()
        elif len(buf) >= SLIDES_PER_PART:
            flush()
    if buf:
        flush()
    print(f"Split into {part_idx} parts")


if __name__ == "__main__":
    if not SRC.is_file():
        raise SystemExit(f"Missing {SRC}")
    main()
