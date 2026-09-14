**DS²-INSTRUCT: Synthetic Financial Advice Guardrail Corpus Generator**


> Generates synthetic Australian business-banking conversations labelled with a single binary —
> `financial_advice_breach` — for training and evaluating the **Financial Advice Guardrail (FAG)**:
> the guardrail that decides whether a VRM response recommends or opines on a financial product,
> under s766B of the Corporations Act 2001 and ASIC RG244/RG255.

## Scope: one guardrail, one boolean

Compliance in the VRM system is a symbolic composition over guardrail outputs
([VRM_Compliance_Guardrail_Architecture.md](VRM_Compliance_Guardrail_Architecture.md)):

```
COMPLIANT = fag_pass ∧ grounded
```

This corpus trains **one variable in that tree** — the FAG — and deliberately does not model
compliance itself. Groundedness is a separate sibling guardrail with its own regulatory basis
(misleading/deceptive conduct) and is out of scope here.

The label is stored breach-positive so the positive class is the event being detected. The variable
the guardrail hands upward is its negation, mirroring the groundedness sibling:

```python
fag_pass = not financial_advice_breach     # grounded = not result.issue_detected
```

## Setup

```bash
conda env create -f environment.yml
conda activate ds2
```

## Usage

```bash
# Local vLLM
bash shell/run_pipeline_qwen72b.sh 200

# Anthropic
export USE_ANTHROPIC=1 ANTHROPIC_API_KEY=<your-key>
bash shell/run_pipeline_anthropic.sh 200

# stages directly
python scripts/generate_conversations.py --count 200
python scripts/validate_conversations.py --input output/vrm_fag_conversations.jsonl
```

## Checking against a held-out test set

Nothing in the pipeline reads your evaluation files. When you want a contamination check, run it
yourself with explicit paths:

```bash
python scripts/check_test_overlap.py \
    --generated output/vrm_fag_conversations.jsonl \
    --test-csv /path/to/single_turn.csv /path/to/multi_turn.csv \
    --threshold 0.6 \
    --write-clean output/vrm_fag_conversations.clean.jsonl
```

Exits non-zero when overlaps are found, so it drops into CI as a gate.

## Output

`output/vrm_fag_conversations.jsonl`, one record per line:

| Field | |
|---|---|
| `financial_advice_breach` | **the label** — bool |
| `product_scope`, `is_corps_question`, `denial_present` | context facts; the conditions policy gates on |
| `advice_tier` | `FACTUAL_INFORMATION` / `GENERAL_ADVICE` / `PERSONAL_ADVICE` |
| `signal_categories` | which of the 15 advice signals the response exhibits |
| `problematic_spans` | verbatim span per signal, with its reason |
| `policy_categories` | the 9 production booleans, **derived** (see `scripts/policy_categories.py`) |
| `severity` | `MEDIUM`/`HIGH`/`CRITICAL` on breaches, `null` otherwise |
| `difficulty`, `contestable` | how hard to classify; whether the label is genuinely arguable |

Taxonomy source of truth: [VRM_Compliance_Definitions_OLD.md](VRM_Compliance_Definitions_OLD.md).
