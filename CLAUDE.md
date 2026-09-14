# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

DS²-INSTRUCT generates a synthetic corpus of Australian business-banking customer/assistant conversations for training and evaluating the **Financial Advice Guardrail (FAG)**. The label is a single binary, `financial_advice_breach`.

**Scope discipline — read this before changing anything.** In the VRM system, compliance is a *symbolic composition over guardrail outputs*, not a synonym for financial advice:

```
COMPLIANT = fag_pass ∧ grounded
```

The variables in that tree are the guardrail outputs; the tree nodes are the guardrails themselves. This repo supervises **one variable in it** — the FAG. Groundedness is a sibling guardrail (hallucination / factual fidelity, regulated as misleading-or-deceptive conduct) and is deliberately *not* modelled here; it also cannot be, since groundedness is only assessable against a retrieved source context and these records carry none. Do not reintroduce a `compliance_status` field — a FAG-only generator has no evidence for a compliance verdict. See [VRM_Compliance_Guardrail_Architecture.md](VRM_Compliance_Guardrail_Architecture.md).

Policy/taxonomy source of truth: [VRM_Compliance_Definitions_OLD.md](VRM_Compliance_Definitions_OLD.md). [Task description.md](Task%20description.md) is the **superseded** original spec (broad multi-category compliance: AML, sanctions, fraud, KYC, 7 jurisdictions); its realism/QC requirements still read across, its taxonomy and jurisdictions do not. [synthetic_conversations.jsonl](synthetic_conversations.jsonl) and `output/banking_compliance_conversations*.jsonl` are artefacts of that superseded spec and will not pass the current validator.

There is no test suite or build step — a small collection of pipeline scripts run via the `shell/` wrappers.

## Held-out test data — do not read

`../single_turn_financial_advice.csv` and `../multi_turn_financial_advice.csv` are the user's **held-out evaluation set**. No pipeline code reads them, and neither should you. In particular, do not tune the generator's distributions to match theirs — `BREACH_RATE` is balanced 50/50 by design, and prevalence is a reweighting knob applied at readout, not baked into the corpus (same rationale as `Claude_native_approach/archive/groundedness-v1` ADR 0002). Contamination checking is [scripts/check_test_overlap.py](scripts/check_test_overlap.py), which the user runs themselves with explicit paths.

## Setup and running

```bash
conda env create -f environment.yml && conda activate ds2

bash shell/run_pipeline_qwen72b.sh <count>          # local vLLM
USE_ANTHROPIC=1 bash shell/run_pipeline_anthropic.sh <count>

python scripts/generate_conversations.py --count 200 [--start_index N] [--max_retries 2] [--temperature 0.8] [--seed N]
python scripts/validate_conversations.py --input output/vrm_fag_conversations.jsonl [--output cleaned.jsonl]
```

Output appends to `output/vrm_fag_conversations.jsonl`; `conversation_id` (`SYN-FAG-NNNNNN`) auto-continues from existing line count unless `--start_index` is given.

## Pipeline architecture

Each conversation is one LLM call. The *scenario recipe* — scope, topic, label, tier, signals, severity, difficulty, length — is sampled by code first; the model's only job is to write prose matching that fixed recipe. Every label and context fact in the final record comes from the scenario, never from the model.

1. **[scripts/scenario_sampler.py](scripts/scenario_sampler.py)** — `sample_scenario()` draws `product_scope` (which also selects the topic pool), then `financial_advice_breach` (balanced per `BREACH_RATE`), then `advice_tier`/`signal_categories`/`severity` conditioned on both. `is_corps_question` is derived from scope + an advice-seeking `customer_stance`; `denial_present` from whether policy required a decline and whether the response gave one.

2. **[scripts/prompts.py](scripts/prompts.py)** — `build_conversation_prompt(scenario)` renders the recipe plus `_response_requirements()`, which emits explicit scenario-specific instructions (must cross into tier X; must/must not decline; may give permitted general advice but never reference the customer's circumstances). Six distinct requirement shapes exist; all are exercised.

3. **[scripts/generate_conversations.py](scripts/generate_conversations.py)** — calls the model, extracts JSON, merges into a record, derives `policy_categories`, validates, retries the same scenario up to `--max_retries`, else drops it and logs why. Appends as it goes, so a killed run keeps what it wrote.

4. **[scripts/validate_conversations.py](scripts/validate_conversations.py)** — standalone auditor; same validator, plus breach balance, tier mix, signal coverage and derived-policy-category counts.

### The policy rule lives in code

[scripts/policy_categories.py](scripts/policy_categories.py) holds the FAG policy as deterministic functions:

- `expected_breach(advice_tier, product_scope)` — Tier 1 never breaches; Tier 3 always does; **Tier 2 breaches only on Corps Act products** (general advice is permitted, though monitored, on other services). Validation enforces that every record's label agrees, so the corpus is consistent by construction rather than by trusting the model.
- `derive_policy_categories(record)` — maps signals + context facts onto the 9 booleans production records. These are **derived, never annotated**: they are scope labels rather than descriptions of wrongdoing, they cannot attach to a text span, and several carry no positive examples in production data.
- `unexplained_breach(record)` — the annotation-gap check (a breach no policy category explains). Validation rejects these.

### Validation rules

`utils.validate_conversation(record)` enforces:
- turns numbered sequentially from 1, alternating `customer`/`assistant` from `customer`;
- label agrees with `expected_breach(tier, scope)`; `severity` set iff breach; `is_corps_question` implies `corps_act`;
- breach ⇒ ≥1 span, every span's category is in `signal_categories`, **and every declared signal has a span**; non-breach ⇒ empty spans;
- every span `text` is an **exact verbatim substring** of the cited assistant turn — the check most likely to reject otherwise-plausible output, since models reword spans;
- `policy_categories` matches the derivation.

### Hard negatives are deliberate

Non-breach records on non-Corps topics may carry `signal_categories` with **empty spans**: advisory language is present, and the correct label is still "no breach" because the scope permits Tier 2. This is what stops a detector collapsing into "recommendation words ⇒ breach". Don't "fix" it by clearing those signals.

### Domain data lives in config.py

[scripts/config.py](scripts/config.py) is the single source of truth: `CORPS_ACT_PRODUCT_TOPICS`/`NON_CORPS_ACT_TOPICS`, `ADVICE_TIER_DESCRIPTIONS`, the 15 `SIGNAL_DESCRIPTIONS` and their `GENERAL_`/`PERSONAL_`/`DOMAIN_ADVICE_SIGNALS` groupings (which must partition all 15), `PRODUCTION_POLICY_CATEGORIES`, and every `*_WEIGHTS`/`*_RATE` knob. The 15 signals are the doc's 14 plus `INSURANCE_ADVICE`, which closes a real gap. `business_advice_misleading` is intentionally always `False` — it belongs to the groundedness guardrail.

### Backend abstraction

[scripts/model_backends.py](scripts/model_backends.py) is domain-agnostic: one `call_model(prompt, max_tokens, temperature)` behind `APIBackend` (OpenAI-compatible/vLLM), `VLLMDirectBackend`, `AnthropicBackend`, or MLX, selected via `config.BACKEND`. `setup_model_backend()` must be called once before any `call_model()`.
