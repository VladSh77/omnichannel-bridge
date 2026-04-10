#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI-only launch gate evaluator (20.9).

Input JSONL row:
{
  "camp": "Pozhumimo",
  "channel": "telegram",
  "correct": true,
  "relevant": true,
  "critical_hallucination": false,
  "automation_resolved": true,
  "fallback_only": false,
  "blocking_identity_bug": false
}
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path


THRESHOLDS = {
    "relevancy": 0.97,
    "critical_hallucination_max": 0.01,
    "automation_resolution": 0.95,
    "fallback_only_max": 0.03,
    "blocking_identity_bugs_max": 0.0,
}


def _safe_rate(hit: int, total: int) -> float:
    return (hit / total) if total else 0.0


def _eval_group(rows: list[dict]) -> dict:
    total = len(rows)
    relevant = sum(1 for r in rows if bool(r.get("relevant")))
    halluc = sum(1 for r in rows if bool(r.get("critical_hallucination")))
    auto = sum(1 for r in rows if bool(r.get("automation_resolved")))
    fallback = sum(1 for r in rows if bool(r.get("fallback_only")))
    blocking = sum(1 for r in rows if bool(r.get("blocking_identity_bug")))
    return {
        "n": total,
        "relevancy": _safe_rate(relevant, total),
        "critical_hallucination_rate": _safe_rate(halluc, total),
        "automation_resolution_rate": _safe_rate(auto, total),
        "fallback_only_rate": _safe_rate(fallback, total),
        "blocking_identity_bugs": blocking,
    }


def _pass_gate(m: dict) -> tuple[bool, list[str]]:
    fails = []
    if m["relevancy"] < THRESHOLDS["relevancy"]:
        fails.append("relevancy")
    if m["critical_hallucination_rate"] > THRESHOLDS["critical_hallucination_max"]:
        fails.append("critical_hallucination_rate")
    if m["automation_resolution_rate"] < THRESHOLDS["automation_resolution"]:
        fails.append("automation_resolution_rate")
    if m["fallback_only_rate"] > THRESHOLDS["fallback_only_max"]:
        fails.append("fallback_only_rate")
    if m["blocking_identity_bugs"] > THRESHOLDS["blocking_identity_bugs_max"]:
        fails.append("blocking_identity_bugs")
    return (len(fails) == 0, fails)


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/ai_launch_gate_eval.py <dataset.jsonl>")
        return 2
    path = Path(sys.argv[1]).resolve()
    if not path.is_file():
        print(f"File not found: {path}")
        return 2
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    if not rows:
        print("Dataset is empty.")
        return 2

    per_channel: dict[str, list[dict]] = defaultdict(list)
    per_camp: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        per_channel[str(row.get("channel") or "unknown")].append(row)
        per_camp[str(row.get("camp") or "unknown")].append(row)

    global_metrics = _eval_group(rows)
    global_pass, global_fails = _pass_gate(global_metrics)
    print("AI_ONLY_GATE_REPORT")
    print(f"- samples: {global_metrics['n']}")
    print(f"- relevancy: {global_metrics['relevancy']:.4f}")
    print(f"- critical_hallucination_rate: {global_metrics['critical_hallucination_rate']:.4f}")
    print(f"- automation_resolution_rate: {global_metrics['automation_resolution_rate']:.4f}")
    print(f"- fallback_only_rate: {global_metrics['fallback_only_rate']:.4f}")
    print(f"- blocking_identity_bugs: {global_metrics['blocking_identity_bugs']}")
    print(f"- global_gate: {'PASS' if global_pass else 'FAIL'}")
    if global_fails:
        print(f"- global_fail_reasons: {', '.join(global_fails)}")

    print("- channel_gate:")
    channel_fail = False
    for channel in sorted(per_channel.keys()):
        m = _eval_group(per_channel[channel])
        ok, fails = _pass_gate(m)
        if not ok:
            channel_fail = True
        print(
            "  - %s: %s (n=%s, rel=%.3f, hall=%.3f, auto=%.3f, fb=%.3f, bugs=%s%s)"
            % (
                channel,
                "PASS" if ok else "FAIL",
                m["n"],
                m["relevancy"],
                m["critical_hallucination_rate"],
                m["automation_resolution_rate"],
                m["fallback_only_rate"],
                m["blocking_identity_bugs"],
                "" if ok else "; fail=" + ",".join(fails),
            )
        )

    print("- camp_coverage:")
    for camp in sorted(per_camp.keys()):
        m = _eval_group(per_camp[camp])
        correct = sum(1 for r in per_camp[camp] if bool(r.get("correct")))
        print(
            "  - %s: n=%s, correct_rate=%.3f"
            % (camp, m["n"], _safe_rate(correct, m["n"]))
        )

    return 0 if (global_pass and not channel_fail) else 1


if __name__ == "__main__":
    raise SystemExit(main())
