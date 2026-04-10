#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OCR PNG slides from Offer2026_unpacked (macOS Vision framework).
Writes camp/knowledge-base/00_offer2026_brochure_partNN.md (chunked) for generate_camp_knowledge_data.py.

Usage:
  python3 scripts/ocr_offer2026_to_markdown.py
  OFFER2026_DIR=/path/to/Offer2026_unpacked python3 scripts/ocr_offer2026_to_markdown.py
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OFFER_DIR = Path.home() / "Developer" / "Offer2026_unpacked"
KB = REPO_ROOT.parent / "camp" / "knowledge-base"
SLIDES_PER_PART = 6
MAX_PART_CHARS = 9000


def _ocr_image_vision(path: Path) -> str:
    from Cocoa import NSURL
    from Quartz import CIImage
    from Vision import VNImageRequestHandler, VNRecognizeTextRequest

    url = NSURL.fileURLWithPath_(str(path.resolve()))
    image = CIImage.imageWithContentsOfURL_(url)
    if image is None:
        return ""

    handler = VNImageRequestHandler.alloc().initWithCIImage_options_(image, {})
    request = VNRecognizeTextRequest.alloc().init()
    # Polish + English + Ukrainian for mixed marketing slides
    try:
        request.setRecognitionLanguages_(["pl-PL", "en-US", "uk-UA"])
    except Exception:
        pass
    try:
        request.setUsesLanguageCorrection_(True)
    except Exception:
        pass

    ok, err = handler.performRequests_error_([request], None)
    if not ok:
        return ""

    lines: list[str] = []
    for observation in request.results() or []:
        for i in range(observation.topCandidates_(1).count()):
            cand = observation.topCandidates_(1).objectAtIndex_(i)
            lines.append(str(cand.string()))
    return "\n".join(lines).strip()


def main() -> int:
    offer_dir = Path(os.environ.get("OFFER2026_DIR", str(DEFAULT_OFFER_DIR))).resolve()
    if not offer_dir.is_dir():
        print(f"Offer directory not found: {offer_dir}", file=sys.stderr)
        return 1

    pngs = sorted(
        offer_dir.glob("*.png"),
        key=lambda p: int(re.sub(r"\D", "", p.stem) or "0"),
    )
    if not pngs:
        print(f"No PNG files in {offer_dir}", file=sys.stderr)
        return 1

    slide_blocks: list[tuple[int, str]] = []
    for i, png in enumerate(pngs, start=1):
        text = _ocr_image_vision(png)
        block = f"## Слайд {i}\n\n{text if text else '_(порожньо або не розпізнано)_'}\n"
        slide_blocks.append((i, block))

    KB.mkdir(parents=True, exist_ok=True)
    # Remove previous parts (keep repo clean on re-run)
    for old in KB.glob("00_offer2026_brochure_part*.md"):
        old.unlink()
    legacy = KB / "00_offer2026_brochure.md"
    if legacy.is_file():
        legacy.unlink()

    header_common = (
        "---\n"
        "tags: [campscout, offer, marketing, 2026, ocr]\n"
        "status: reference\n"
        "source: Offer2026_unpacked PNG slides (macOS Vision OCR)\n"
        "---\n\n"
        "> OCR (PL/EN/UA). Для цін, дат і юридичних фактів — **звіряти з Odoo і** "
        "[00_company.md](00_company.md); це маркетингова брошура.\n\n"
    )

    part_idx = 0
    buf: list[str] = []
    buf_start_slide: int | None = None
    written = 0

    def flush_part() -> None:
        nonlocal part_idx, buf, buf_start_slide, written
        if not buf or buf_start_slide is None:
            return
        part_idx += 1
        m = re.search(r"## Слайд (\d+)", buf[-1])
        last_i = int(m.group(1)) if m else buf_start_slide
        first_i = buf_start_slide
        name = f"00_offer2026_brochure_part{part_idx:02d}.md"
        title_line = f"# Оферта Camp Scout 2026 — слайди {first_i}–{last_i}\n\n"
        path = KB / name
        path.write_text(header_common + title_line + "\n".join(buf), encoding="utf-8")
        written += 1
        buf = []
        buf_start_slide = None

    for si, block in slide_blocks:
        if not buf:
            buf_start_slide = si
        buf.append(block)
        joined = "\n".join(buf)
        if len(joined) >= MAX_PART_CHARS:
            flush_part()
            continue
        if len(buf) >= SLIDES_PER_PART:
            flush_part()

    if buf:
        flush_part()

    print(f"Wrote {written} part file(s) under {KB} ({len(pngs)} slides OCR)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
