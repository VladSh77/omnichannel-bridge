# AI-only Acceptance Report (20.9)

Date: 2026-04-10

KPI summary (7-day gate window):
- Relevancy: `0.978`
- Critical hallucination rate: `0.006`
- Automation resolution: `0.958`
- Fallback-only: `0.022`
- Blocking identity/author bugs in Discuss: `0`

Channel gate:
- `telegram`: PASS
- `site_livechat`: PASS
- `meta`: PASS
- `whatsapp`: PASS
- `viber`: PASS

Operational mode:
- Standard sales/FAQ flows run in AI-first mode.
- Manager role remains escalation-only for edge/sensitive/technical cases.

Evidence bundle:
- `docs/CHANNEL_PARITY_E2E_CHECKLIST.md`
- `docs/CAMP_CHANNEL_SMOKE_REPORT_2026-04-10.md`
- `docs/CAMP_QA_ACCEPTANCE_DATASET_2026-04.md`
- `scripts/ai_launch_gate_eval.py`
