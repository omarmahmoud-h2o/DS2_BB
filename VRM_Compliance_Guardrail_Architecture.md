# VRM Compliance System — Guardrail Architecture

## Does Compliance Rely on the Financial Advice Concept?

**Largely yes — but not entirely.**

In the project *documents*, "compliance" is effectively synonymous with "financial advice detection." But in the *actual codebase*, compliance is the broader concept, and financial advice is only **one of two independent guardrails** that together define whether a response is compliant.

---

## The Two Guardrails

The guardrails layer (`app/guardrails/`) contains two sibling guardrails, not one:

```
app/guardrails/
├── financial_advice/          ← Financial Advice Guardrail (FAG)
│   ├── policy_tree.py             (expression tree — deterministic policy logic)
│   ├── policy_variables.py        (the boolean signal variables)
│   ├── output_check.py            (output evaluation)
│   ├── core/
│   └── gaas_slm/
│       └── precheck.py            (GaaS SLM fast first-pass filter)
│
└── groundedness/              ← Groundedness Guardrail
    └── check.py                   (is the response grounded in retrieved context?)
```

### Guardrail 1 — Financial Advice Guardrail (FAG)

Answers: **"Does this response recommend or opine on a Corps Act financial product?"**

- Enforces s766B of the Corporations Act, RG244, RG255
- Uses the Boolean Variable Classifier + expression tree + GaaS SLM pre-check + rewrite loop
- Detects 14 signal categories (suitability, recommendation, action directives, etc.)
- This is the dominant, most sophisticated compliance dimension — the entire V1→V3 progression was built around it

### Guardrail 2 — Groundedness Guardrail

Answers: **"Is every claim in the response actually supported by the retrieved source context?"**

- A *hallucination / factual-fidelity* check, not an advice check
- Delegated to GaaS via a `type="groundedness"` validator
- Returns `grounded = not result.issue_detected`
- Comparatively thin: one file, one API call
- Guards against misleading or deceptive conduct (inaccurate claims), a different regulatory risk from financial advice

**Reference:** [groundedness/check.py](Documents/bb-virtual-rm-main/agents/virtual-relationship-manager.1/app/guardrails/groundedness/check.py)

---

## How Compliance and Financial Advice Actually Relate

Compliance is a **hierarchy**, not an equivalence:

| Level | Concept | Question it answers | Regulatory basis |
|---|---|---|---|
| **Compliance** (top) | Is this response safe to send to the customer? | The overall gate | — |
| ├─ Financial Advice Guardrail | Does it recommend/opine on a Corps Act product? | s766B / RG244 / RG255 | Financial product advice |
| └─ Groundedness Guardrail | Is every claim supported by retrieved context? | Factual fidelity | Misleading / deceptive conduct |

A response is **compliant** only if it passes **both** guardrails.

---

## Why the Two Concepts Are Not Interchangeable

The guardrails are independent — a response can fail one while passing the other:

| Scenario | FAG | Groundedness | Compliant? |
|---|---|---|---|
| States a rate accurately, no opinion | ✅ Pass | ✅ Pass | ✅ Yes |
| States a rate accurately, then "this is the best account for you" | ❌ Fail | ✅ Pass | ❌ No |
| Hallucinates a product feature not in the source context | ✅ Pass | ❌ Fail | ❌ No |
| Recommends a product using invented benefits | ❌ Fail | ❌ Fail | ❌ No |

**Key insight:**
- A response can be **non-compliant without being financial advice** — e.g. it hallucinates a feature. That fails groundedness, not the FAG.
- A response can be **perfectly grounded yet non-compliant** — e.g. it accurately states a fact and then recommends the product. That passes groundedness but fails the FAG.

---

## Why the Documents Made It Look 1:1

The document set (Docs 1–9) is almost entirely about the Financial Advice Guardrail, because that is where:
- the regulatory risk concentrates (financial product advice liability),
- the novel engineering lives (expression tree + boolean classifier + rewrite loop),
- the model-evaluation effort was spent (GPT-5.2 minimal selection).

Groundedness is a comparatively thin, GaaS-delegated check, so it barely appears in the design narrative — which is why the documents alone make compliance look coextensive with financial advice.

---

## Bottom Line

> Financial advice is the **dominant and most sophisticated** compliance dimension in this project — the one the whole V1→V3 progression was built around — but "compliant" formally means passing **both** the Financial Advice Guardrail **and** the Groundedness Guardrail.
>
> **Compliance relies *on* the financial-advice concept; it is not *defined by* it alone.**
