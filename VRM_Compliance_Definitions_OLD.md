# VRM Compliance System — Definitions

## Compliance — Project Definition

Within the VRM project, **Compliance** means:

> The operational guarantee that every VRM-generated response contains only objective, factual information — never a recommendation, opinion, or statement that could influence a customer's decision about a financial product — as required by **RG244**, **RG255**, and **section 766B of the Corporations Act 2001**.

Operationally, a response is "compliant" when it clears the Financial Advice Guardrail's expression tree without triggering any of the 14 classified signal categories. It is not just a legal concept — it is a runtime binary: **pass or fail**, on every single response, before it reaches the customer.

### Three Enforcement Layers

| Layer | Mechanism | Nature |
|---|---|---|
| Structural | Expression tree applying legislative policy logic | Deterministic, auditable |
| Semantic | Boolean Variable Classifier extracts 40+ signals in parallel | LLM-based, parallel |
| Corrective | Non-compliant responses are rewritten, not blocked | Preserves utility |

### What "Being Compliant" Means Operationally

A response passes compliance when the expression tree evaluates to `FACTUAL_INFORMATION_COMPLIANT = True`. This requires:

- No mention of a financial product paired with a general or personal advice statement
- No core financial advice signals present (recommendation, suitability assessment, action directive, etc.)
- No personal advice signals present (reference to customer's specific circumstances)
- Positive presence of factual information requirements (objective, verifiable product information)

---

## Financial Advice — Project Definition

Within the VRM project, **Financial Advice** means:

> Any statement, recommendation, or opinion in a VRM response that — in the context of the conversation — could reasonably be interpreted as intended to influence a customer's decision to acquire, hold, or dispose of a **Corps Act financial product** (e.g. Business Transaction Account, Business Investment Account, Neo Business Card).

### Three-Tier Advice Hierarchy

The project operationalises Financial Advice across a strict three-tier hierarchy:

| Tier | Label | Definition | VRM Status |
|---|---|---|---|
| 1 | **Factual Information** | Objective product features, rates, availability — no opinion, no recommendation | **Allowed** |
| 2 | **General Advice** | Statements about product suitability without reference to personal circumstances | **Restricted** — only for non-Corps Act products |
| 3 | **Personal / Scaled Advice** | Takes the customer's specific circumstances into account to suggest a product decision | **Prohibited** |

The critical boundary the entire system is built around:

> **Factual information about a product is allowed. An opinion about whether a customer should choose that product is not.**

### 14 Signal Categories

The Boolean Variable Classifier detects these signals to determine whether a response constitutes Financial Advice:

| # | Signal Category | Example |
|---|---|---|
| 1 | Suitability assessment | "this product suits your needs" |
| 2 | Product recommendation | "I recommend / you should consider" |
| 3 | Action directives | "apply now", "switch to" |
| 4 | Subjective descriptors | "best", "great option", "ideal" |
| 5 | Tax advice cues | "this could reduce your tax" |
| 6 | Legal advice cues | "you are legally better off" |
| 7 | Investment advice cues | "this will grow your money" |
| 8 | Competitive comparisons | comparing one product's merits over another |
| 9 | Forward-looking performance statements | "you'll earn more with this account" |
| 10 | Personal language | implying knowledge of the customer's specific situation |
| 11 | Risk characterisation | labelling products as low/high risk for the customer |
| 12 | Implied endorsement | framing that suggests CBA prefers one product for the customer |
| 13 | Need-based framing | "given your business needs, this product..." |
| 14 | Outcome projection | predicting financial outcomes for the specific customer |

### Corps Act Products In Scope

Financial products regulated under the Corporations Act, where the strictest advice restrictions apply:

- Business Transaction Account
- Business Investment Account
- Neo Business Card

Non-Corps Act products (general banking services, information queries) are subject to lighter restrictions — General Advice (Tier 2) is permitted but still monitored.

---

## Regulatory Framework

| Regulation | Definition Provided |
|---|---|
| **Corporations Act 2001, s766B** | Statutory definition of Financial Product Advice: a recommendation or statement of opinion intended to influence a person's decision about a financial product |
| **RG244 (ASIC)** | Guidance on the boundary between factual information and general advice — the key line the expression tree enforces |
| **RG255 (ASIC)** | Scaled and limited advice framework — informs future scoped advice pathways |
| **ASIC Act** | Complementary consumer protection provisions covering misleading or deceptive conduct |

---

## Relationship Between the Two Definitions

```
Financial Advice (legal concept)
        |
        | defines what VRM must never produce
        v
Compliance (operational guarantee)
        |
        | enforced by
        v
Financial Advice Guardrail (FAG)
  ├── Boolean Variable Classifier (detects 14 signal categories)
  ├── Expression Tree (applies RG244/RG255 policy logic)
  ├── GaaS SLM Pre-check (fast first-pass filter)
  └── Rewrite Loop (corrects non-compliant responses)
```

Compliance is the system-level property. Financial Advice is the legal category it is designed to prevent. The guardrail is the mechanism that connects them at runtime.
