# Learning Policy (No Fine-Tuning)

The bot is improved through Odoo data and rules, not automatic model weight training.

## Enabled mechanisms

- Partner memory fields (`omni_chat_memory`, addressing preferences).
- Rule-based extraction from chat text.
- Editable knowledge UI (`omni.knowledge.article`) for business updates.
- Prompt/version controls in settings (`llm_prompt_version`, `llm_experiment_tag`).

## Explicitly disabled by default

- Automatic fine-tuning on customer conversations.
- Autonomous model retraining without legal/product review.

## Operational intent

- Keep responses grounded in ORM facts.
- Reduce hallucination risk by controlled context and human-reviewable rules.
