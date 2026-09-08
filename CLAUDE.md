# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

DS²-INSTRUCT generates a synthetic dataset of business-banking customer/AI-assistant conversations, labeled `COMPLIANT` / `NON_COMPLIANT` / `BORDERLINE`, for training and evaluating a financial compliance detection system. The full generation spec (topics, risk categories, realism/safety requirements, output schema, target distributions, QC checklist) lives in [Task description.md](Task%20description.md) — read it before changing prompt or sampling logic, since the code encodes its rules directly. [synthetic_conversations.jsonl](synthetic_conversations.jsonl) is a hand-authored reference sample showing the target output shape and quality bar.

There is no test suite or build step — this is a small collection of pipeline scripts run via the shell wrappers in `shell/`.

## Setup

```bash
conda env create -f environment.yml
conda activate ds2
```

## Running the pipeline

Two entry points in `shell/`, one per backend, each generating `<count>` conversations then validating them:

```bash
# Local vLLM (Qwen 72B), starts/reuses a vLLM server on localhost:8001
bash shell/run_pipeline_qwen72b.sh <count> [--server-only] [--no-server]

# Anthropic (requires ANTHROPIC_API_KEY; optional ANTHROPIC_MODEL, defaults to claude-sonnet-5)
export USE_ANTHROPIC=1
bash shell/run_pipeline_anthropic.sh <count> [--max_retries N] [--temperature T] [--start_index N]
```

Stages can also be run directly:

```bash
python scripts/generate_conversations.py --count 200 [--output PATH] [--start_index N] [--max_retries 2] [--temperature 0.8] [--seed N]
python scripts/validate_conversations.py --input output/banking_compliance_conversations.jsonl [--output cleaned.jsonl]
```

Output: `output/banking_compliance_conversations.jsonl` — one JSON conversation record per line, appended across runs. `generate_conversations.py` auto-continues `conversation_id` numbering from however many lines already exist in the output file unless `--start_index` is given.

## Pipeline architecture

Unlike a keyword-expansion/retrieval pipeline, each conversation here is produced by a single LLM call: the *scenario metadata* (topic, jurisdiction, compliance status, severity, difficulty, risk categories, conversation length) is sampled by code first, and the LLM's only job is to write a conversation that matches that fixed recipe. This split exists because the task spec gives explicit target distributions (e.g. 40/45/15% compliant/non-compliant/borderline, risk categories "distributed broadly rather than concentrating on AML") that are far more reliable to enforce via weighted sampling than by asking the model to self-balance across many calls.

1. **[scripts/scenario_sampler.py](scripts/scenario_sampler.py)** — `sample_scenario()` draws one scenario recipe: `conversation_type`/`turn_count` (from `CONVERSATION_LENGTH_BUCKETS`/`_WEIGHTS` — single_turn=2 messages, short=2-4, medium=6-8, long=10-14; always even since real conversations end on an assistant turn), `compliance_status` (weighted per `COMPLIANCE_STATUS_WEIGHTS`), then `severity`/`difficulty`/`risk_categories` conditioned on that status (e.g. BORDERLINE always pairs with `difficulty="BORDERLINE"`), plus `industry`/`business_type`/`jurisdiction`/`primary_topic`/`secondary_topics` and a `customer_stance` hint (legitimate/suspicious/confused/frustrated/ambiguous/prohibited_request/personalized_request) used only to flavor the prompt, not written to the final record.

2. **[scripts/prompts.py](scripts/prompts.py)** — `build_conversation_prompt(scenario)` renders the fixed recipe plus risk-category definitions (`config.CATEGORY_DESCRIPTIONS`) into a generation prompt instructing the model to return one JSON object with exactly: `customer_intent`, `messages`, `problematic_turns`, `problematic_spans`, `reasoning_summary`, `expected_ai_behavior`. Everything else in the final record (topic, jurisdiction, compliance_status, etc.) comes from the scenario, not the model.

3. **[scripts/generate_conversations.py](scripts/generate_conversations.py)** — for each sampled scenario: calls the model, extracts JSON from the response (`utils.extract_json`, tolerates markdown fences), merges it with the scenario into a full record (`assemble_record`), and validates it (`utils.validate_conversation`). On failure it retries the same scenario up to `--max_retries` times, then drops it and logs why — it does not fall back to a lower-quality record. Appends valid records to the output JSONL as it goes (not batched), so a killed run keeps whatever it already wrote.

4. **[scripts/validate_conversations.py](scripts/validate_conversations.py)** — standalone auditor over an existing JSONL file; reuses the same `utils.validate_conversation` check, reports per-record failures and the compliance-status distribution among valid records, and optionally writes a filtered `--output` containing only records that passed.

### Conversation validation rules

`utils.validate_conversation` (used by both generation-time retries and the standalone auditor) enforces the schema mechanically wherever the spec's QC checklist is checkable without human judgment:
- `messages` turns are numbered sequentially from 1 and alternate `customer`/`assistant` starting with `customer`.
- `compliance_status`/`severity`/`difficulty` are valid enum values; `risk_categories` are from `config.RISK_CATEGORIES`.
- `COMPLIANT` records must have empty `problematic_turns`/`problematic_spans`; `NON_COMPLIANT`/`BORDERLINE` records must have at least one.
- Every `problematic_spans[].text` must appear as an **exact verbatim substring** of the assistant content in the turn it cites (not a paraphrase) — this is the check most likely to reject otherwise-plausible model output, since models often lightly reword the span instead of copying it.

### Backend abstraction

[scripts/model_backends.py](scripts/model_backends.py) is domain-agnostic: a single `call_model(prompt, max_tokens, temperature)` used by generation, backed by one of three implementations selected via `config.BACKEND` (driven by the `USE_ANTHROPIC` env var):
- `APIBackend` — OpenAI-compatible HTTP API (local vLLM server mode, `VLLM_API_BASE`).
- `VLLMDirectBackend` — in-process vLLM (`from vllm import LLM`), only if the `vllm` package is importable.
- `AnthropicBackend` — Anthropic Messages API via the `anthropic` SDK; reads `ANTHROPIC_API_KEY`/`ANTHROPIC_MODEL` from the environment (`config.ANTHROPIC_CONFIG`), only if the `anthropic` package is importable.

`setup_model_backend()` must be called once before any `call_model()` calls; it also validates/resolves the served model name against the live API.

### Domain data lives in config.py

[scripts/config.py](scripts/config.py) is the single source of truth for everything the sampler and prompts draw from: `TOPICS`, `INDUSTRIES`, `BUSINESS_TYPES`, `JURISDICTIONS`, `RISK_CATEGORIES`/`CATEGORY_DESCRIPTIONS`, and all the `*_WEIGHTS`/`*_BUCKETS` distribution knobs. Adding a topic, jurisdiction, or risk category means adding it here — `scenario_sampler.py` and `prompts.py` pick it up automatically with no other code changes. Changing target distributions (e.g. more BORDERLINE examples) means editing the weight dicts here, not the prompt text.
