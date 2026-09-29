# Synthetic Data Generation Framework — Design (Draft v1)

> **Status:** draft for review · **Diagram:** [Overall architecture.drawio.xml](Overall%20architecture.drawio.xml), page *"v1 – Generic framework (draft)"*
> **Lineage:** generalises two existing codebases — [src_original/DS2-Instruct](src_original/DS2-Instruct) (the three-stage DS²-Instruct method) and this repo's Financial Advice Guardrail (FAG) generator ([scripts/](scripts/)).

---

## 1. Purpose

Build **one generic framework** that produces synthetic datasets for **any use case**. Each dataset is governed, evaluated and ready to release, with its evidence attached.

Each use case supplies only a **task specification**: a definition, a rubric or policies, a few seed examples, the tools it may use, and the thresholds it must meet. The framework provides everything else: coverage planning, generation, validation, governance, evaluation, the release decision, and a full audit trail.

The design is built around three directions, and every component serves at least one of them:

| Direction | The question it answers |
|---|---|
| **Quality** | Is each record correct (fidelity), is the set diverse, and does it cover the task space? |
| **Governance** | Is the data free of PII, toxicity, copied seeds, leaked held-out or sensitive data, and is every record traceable? |
| **Optimisation & time cost** | What does each *accepted* record cost in tokens, money and time, and how can that be reduced without losing quality? |

### Out of scope for v1

- **Obfuscating raw seeds.** This happens in a pre-preparation step outside the framework (§4.1). The framework checks that it was done but doesn't do it.
- **Human sign-off before release.** The release gate is automatic, driven by thresholds (§6.6).

---

## 2. Design principles

1. **Everything that varies per use case lives in the spec, and the core pipeline is shared.** A new use case means a new spec (plus optional hooks), never a fork of the pipeline.
2. **Code owns the facts that can be checked; the LLM writes the prose.** Wherever a label, rule or constraint can be computed, it is computed by the spec or a hook, not trusted from the model. (This comes from the FAG repo, where the scenario recipe is sampled in code and the model only writes the text.)
3. **Validate cheapest first and stop at the first hard failure.** Free deterministic checks run before paid model checks.
4. **The generator never grades its own work.** The judge is a separate model instance, ideally a different model family, and it evaluates against the task's rubric without seeing the intended label.
5. **Governance failures are never traded off against quality.** A governance failure always drops the record; quality produces scores that the release gate aggregates.
6. **Coverage is planned and filled to quotas, not left to chance.** Dropping a record must never quietly change the dataset's distribution.
7. **Every stage writes a saved artefact.** Runs can be resumed, cached and replayed, and every record can be traced back to its origin.
8. **Human review is available but optional.** A task switches it on at defined checkpoints; it is never a hidden dependency.

---

## 3. Terminology

| Term | Meaning |
|---|---|
| **Use case / task** | One dataset-producing problem, e.g. "FAG breach detection". |
| **Task spec** | `task.yaml` (declarative) plus optional `hooks.py` (code). The complete definition of a use case. |
| **Task type** | The *kind* of dataset: classification with spans, SFT question/answer, multi-turn dialogue, preference pairs, … Each type brings its own output schema, generation mode and default validators. |
| **Generation mode** | `label_first` (code fixes the label, the model writes matching text) or `answer_emergent` (the model writes the answer, and agreement across samples stands in for correctness). |
| **Seed** | An example supplied with the spec, as a few examples or a larger rubric-annotated set. Used to inspire generation, never to be copied. |
| **Rubric / policies** | The criteria the judge evaluates against, including whether a written reason is required. |
| **Coverage axis** | A dimension the dataset must span: keyword/topic, Bloom level, difficulty, label, stance, length, … |
| **Cell** | One combination of coverage-axis values. It has a **quota**, the number of accepted records it needs. |
| **Candidate record** | Generator output that hasn't been validated yet. |
| **Accepted record** | A record that passed every validation layer. |
| **Validation layer (L1–L6)** | One step of the validation cascade (§6.4). |
| **Decision model** | A low-cost, low-latency model that returns typed decisions with confidence, used as the judge (primary candidate: Jev). |
| **Gold set** | Human-labelled records used to calibrate the judge. |

---

## 4. Inputs

### 4.1 Pre-preparation (outside the framework, v1)

```
raw seeds (may contain real/customer data) ──► obfuscation / anonymisation ──► clean seeds
```

- For now, obfuscation is done **before** the pipeline. Seeds may come from real data, so this is where PII is removed or replaced.
- The framework doesn't rely on it having been done correctly. **Stage 0 re-scans every seed for PII and rejects the spec if any seed isn't clean** (§6.1).
- *Future option:* move obfuscation inside the framework as a stage. Because intake already re-scans the seeds, that move doesn't require redesigning anything else.

### 4.2 Task spec — `task.yaml` (declarative)

| Section | Contents |
|---|---|
| `task` | name, version, **task type**, **generation mode**, task definition/description |
| `output_schema` | fields, types, required fields, structure (e.g. alternating turns, spans) |
| `rubric` | criteria, how each is scored, verdict definition, **whether a reason is required** |
| `seeds` | path, format (few examples or annotated set), how they are used (few-shot, keyword seeding, gold set) |
| `coverage` | axes and their values or sources (fixed list, keyword expansion, retrieval), target size, balance targets, quota policy |
| `tools` | which tools from the registry this task may use, with per-record call/token budgets |
| `governance` | tightening beyond the global profile: extra PII patterns, entity allow/deny lists, toxicity exceptions |
| `models` | model per stage (expansion, generator, judge), with temperature and other parameters |
| `validation` | which layers are on, repair tries `N`, consistency `K`, escalation rules |
| `thresholds` | release-gate thresholds (§8) |
| `hitl` | switches for each human-review checkpoint (§10) |
| `budget` | token / money / time limits per run |

### 4.3 Task hooks — `hooks.py` (optional code)

Hooks handle logic the declarative spec can't express. The framework defines a small, fixed set of hook points:

| Hook | Purpose | FAG example |
|---|---|---|
| `label_rule(record)` | Computes the correct label from facts that can be checked | `expected_breach(advice_tier, product_scope)` |
| `sampler_constraints(cell)` | Keeps the fields sampled for a cell consistent with each other | tier/scope/signal/severity conditioning; `is_corps_question`, `denial_present` |
| `extra_validators(record)` | Task-specific L2 checks | verbatim-span check; every declared signal has a span |
| `post_process(record)` | Derived fields added after validation | `derive_policy_categories()` |

---

## 5. Architecture overview

```
 PRE-PREPARATION   raw seeds ─► obfuscation ─► clean seeds
 ═══════════════════════════════════════════════════════════════════════════
 0 TASK INTAKE      task.yaml + hooks.py ─► spec validation (incl. seed PII re-scan)
 1 COVERAGE PLAN    keyword expansion (↑/↓ + retrieval) × axes ─► cells × quotas   ◆ HITL approve
 2 GENERATE         scheduler ─► generator agent ◄─► tool gateway ─► candidate + trace
 3 VALIDATE         L1 schema ─► L2 rules ─► L3 governance ─► L4 overlap ─► L5 judge ─► L6 consistency
                      └ fail ─► repair (error fed back, ≤N) │ drop + reason │ ◆ HITL review queue
 4 DATASET EVAL     coverage · diversity · fidelity · balance · error rate · cost    ◆ HITL judge calibration
 5 RELEASE GATE     thresholds met? ─► versioned dataset + card + provenance + reports
                      └ not met ─► scheduler (fill missing cells)
 ───────────────────────────────────────────────────────────────────────────
 SHARED             task-type registry · model registry · tool registry/gateway ·
                    governance profile · artefact store · provenance · metrics engine
```

---

## 6. Stages

Each stage lists its **purpose → inputs → process → outputs** and how it serves the three directions.

### 6.1 Stage 0 — Task intake

- **Purpose:** turn a task spec into a checked, compiled spec before any money is spent.
- **Inputs:** `task.yaml`, `hooks.py`, clean seeds.
- **Process:**
  1. Validate the spec against the framework's spec schema: required sections present and types correct.
  2. Resolve the task type, and load its default output schema and validators.
  3. **Re-scan the seeds with the governance scanners (PII, toxicity).** Reject the spec if any seed fails.
  4. Check that every tool listed exists in the tool registry and is allowed for this task's data class.
  5. Check that every release threshold is set; there are no silent defaults for the gate.
  6. Check that the hook functions exist and match the expected signatures.
- **Outputs:** the compiled spec. The spec version is a hash of the spec, hooks and seeds, used for caching and provenance.
- **Directions:** governance (the seed gate), cost (fails before any spend).

### 6.2 Stage 1 — Coverage plan

- **Purpose:** define *what* the dataset must cover, as cells with quotas.
- **Inputs:** the compiled spec and seeds.
- **Process:**
  1. **Keyword generation** (from DS²-Instruct stage ❶):
     - *Seed keywords* come from the task definition and the seeds.
     - *Bi-directional expansion:* ↓ prerequisites (foundational concepts) and ↑ advanced (specialised concepts), iterated with de-duplication.
     - *Retrieval augmentation:* retrieve passages through the task's retrieval tools and extract missing domain terms.
     - A task with a fixed topic list (as FAG has today) can skip expansion and declare its axis values directly.
  2. **Axis crossing:** keywords × the task type's axes, e.g. **Bloom level** (Remember → Create, from DS²-Instruct stage ❷), difficulty, label, stance, length.
  3. `sampler_constraints` removes invalid combinations, and quotas are assigned to reach the target size and balance.
- **◆ HITL (optional):** a person approves or edits the keyword list and the grid before generation starts.
- **Outputs:** `coverage_plan.json`, cached by spec version and reused until the spec changes.
- **Directions:** quality (coverage by design), cost (planned once, reused).

### 6.3 Stage 2 — Generate (agentic)

- **Purpose:** produce candidate records for cells that are below quota.
- **Inputs:** the coverage plan, compiled spec, and model and tool registries.
- **Process:**
  1. **The scheduler** picks the cell furthest below its quota and **stops a cell once its quota is met**. Failed records are regenerated *in the same cell*, so rejections can't skew the distribution.
  2. **The generator LLM runs as an agent**, receiving the cell's parameters, the spec and few-shot seeds. It **decides for itself which of the task's tools to call**.
  3. **Every tool call goes through the tool gateway** (§7.4): allowlist, budget, sensitivity labelling, caching, tracing.
- **Outputs:** a candidate record plus its tool trace.
- **Directions:** quality (targeted generation), governance (gateway), cost (early stop per quota, tool cache, budgets).

### 6.4 Stage 3 — Validation cascade

**Purpose:** accept only records that are well formed, follow the rules, are governed, original and faithful. Layers run **in order from cheapest to most expensive**, and **the first hard failure stops the cascade**.

| Layer | Checks | Cost | On failure |
|---|---|---|---|
| **L1 Schema / layout** | Output schema, required fields, structure (turn order, alternating roles, field types) | free | repair |
| **L2 Rules & keywords** | Spec rules, required or forbidden keywords, `label_rule` agreement, `extra_validators` (e.g. verbatim spans) | free | repair |
| **L3 Governance** | PII (general engine + domain patterns), toxicity, secrets/credentials, **leakage of sensitive tool data**, real-entity deny list | cheap models | **drop** (hard fail) |
| **L4 Overlap** | n-gram + embedding similarity against **seeds** (copying), **held-out set** (contamination; only when a path is given at run time), **the corpus so far** (near-duplicates) | cheap | **drop** |
| **L5 Decision judge** | Separate decision model (Jev), **blind to the intended label**. Returns a typed **verdict + rubric scores + confidence per field**. Fidelity = the judge's verdict agrees with the intended label. A reason, if required, comes from the fallback generative judge (§7.3). | paid (very low) | repair, or review queue if confidence is low |
| **L6 Consistency** | Only on escalated cases. With a calibrated judge, **its confidence replaces K votes**. K votes are kept for `answer_emergent` tasks (majority *becomes* the answer, the DS²-Instruct method) and for judges whose calibration isn't proven (majority must agree with the fixed label). | paid × K (when used) | repair / review queue / drop |

**Handling failures:**

- **Repair:** the specific validator error is fed back to the generator (e.g. *"span not found verbatim in turn 4"*), for up to `N` tries in the same cell. This replaces the blind retry both inherited codebases use.
- **Drop + log reason:** after a governance failure or when tries run out. The drop is logged by cell and by layer, and these logs feed the error-rate metrics.
- **◆ HITL review queue (optional):** records where judges disagree or rubric scores are low go to people instead of being dropped. Their decisions are added to the gold set.

**Outputs:** accepted records with provenance (§7.7).

### 6.5 Stage 4 — Dataset evaluation

- **Purpose:** measure the dataset as a whole, not just individual records.
- **Process:** compute the metrics in §8 over the accepted records and the drop logs.
- **◆ HITL judge calibration (optional, strongly recommended):** a person labels a gold set, and judge-versus-human agreement (Cohen's κ) is measured. **The judge is trusted only once it passes the task's κ threshold**, and calibration is repeated whenever the rubric or judge model changes.
- **Outputs:** a metrics report.

### 6.6 Stage 5 — Release gate

- **Purpose:** decide automatically, with no human sign-off, whether the dataset can be released.
- **Process:** compare the metrics report with the thresholds set in `task.yaml`.
  - **Pass** → release a versioned dataset with a dataset card, per-record provenance, a governance report and a metrics report.
  - **Fail** → produce a report of which cells or metrics fall short, and send the scheduler back to fill those cells.
- **Directions:** all three. This is the single point where the evidence has to add up.

---

## 7. Components

### 7.1 Task-type registry
Each task type defines its **output schema**, **generation mode**, **default axes**, **default validators** and **answer extractor** (for `answer_emergent` consistency). Planned types:

| Type | Mode | Example |
|---|---|---|
| Classification with spans | `label_first` | FAG breach detection |
| SFT question → answer | `answer_emergent` | DS²-Instruct tasks (CFA, GSM8K, MedQA, …) |
| Multi-turn dialogue | either | customer-service conversations |
| Preference pairs | `label_first` | chosen / rejected responses for DPO |

New types are added to the registry; the core pipeline doesn't change.

### 7.2 Spec loader and compiler
Parses `task.yaml`, loads `hooks.py`, validates both, hashes the result into a spec version, and exposes a single compiled spec object to every stage.

### 7.3 Model registry
Models are configured **per stage** (expansion, generator, judge) through one `call_model` interface for each backend: local vLLM, MLX, OpenAI-compatible APIs, Anthropic, and others. This extends the existing [scripts/model_backends.py](scripts/model_backends.py).

**Judge vision:** a **decision model**, low cost and low latency, that works as a single decision-making model. The primary candidate is **Jev**, TypeSafe AI's first "System One" model ([announcement](https://typesafe.ai/blog/introducing-system-one-models-and-jev)).

What the announcement says (vendor claims, not yet checked by us):
- **Output:** structured values of a type defined in advance ("type-safe"), with **calibrated probabilities / confidence scores**. The model **does not generate free text** ("gives up string generation").
- **Choices per field:** up to **255**.
- **Latency:** 70–500 ms end to end. **Cost:** $0.042 per million input tokens; output tokens not charged.
- **Access:** early access through an API and playground. The announcement doesn't mention open weights or self-hosting.
- **Training:** its own architecture, a parallel sampler, and "Reinforcement Learning for Calibrated Decisions (RLCD)".

What this means for the design:
- **The judge interface becomes typed:** rubric + record → verdict (enum) + rubric scores (enum / bounded int, ≤ 255 values each) + **confidence per field**. The rubric in `task.yaml` compiles into this output schema.
- **Reasons need a fallback judge.** Jev can't write text, so when a task's rubric requires a reason (D9), a **secondary generative judge** writes it. To keep costs down, it runs only on records that need a reason, e.g. flagged or review-queue records, or every record if the rubric says so.
- **Confidence replaces most K-vote consistency.** Jev's calibrated confidence drives the L5 → L6 / review-queue routing directly. K-vote consistency (L6) is kept only for `answer_emergent` tasks, or where calibration hasn't been proven.
- **Calibration still has to be measured, not assumed.** "Calibrated" and "0% hallucination" are vendor claims; the second means the output always matches the schema, *not* that the decision is correct. Before the judge is trusted on a task, measure its κ against the gold set **and its calibration** (reliability curve / expected calibration error).
- **Independence from the generator** holds by construction: Jev is a different model family from every generator.
- **The judge stays swappable** behind the same typed interface, so an open-weights decision model can replace Jev if needed (e.g. for data that mustn't leave the organisation).

### 7.4 Tool registry and tool gateway
- **Registry:** every tool is declared once with its interface, **sensitivity level**, and whether it is read-only (the default) or has side effects. Each task lists the tools it may use.
- **Gateway:** every agent tool call passes through it and gets:
  - an **allowlist** check against the task's tools;
  - a **per-record call and token budget**;
  - a **sensitivity label** on the result, which travels with the record to L3;
  - a **response cache** keyed by tool and arguments (saves cost and allows exact replay);
  - a **full trace log**, saved in the record's provenance.

### 7.5 Governance profile
**Global rules** that apply to every task, which a task can only **tighten**, never loosen:
- PII detection: a general engine plus domain patterns, e.g. ABN, TFN, BSB and account numbers for banking;
- toxicity and safety classification;
- detection of secrets and credentials;
- a real-entity allow/deny list;
- **model endpoints:** where data goes is **decided by which models the task selects** (D12). Each model-registry entry records its hosting (local, or the provider's API), so a task's model choice *is* its data-destination decision. The framework records it in provenance and the governance report, so every release shows which external endpoints its data reached.

Documented exceptions are declared in the task spec, e.g. a toxicity-detection task that needs toxic examples.

### 7.6 Scheduler
Chooses cells to fill based on how far each is below its quota, keeps regeneration in the same cell, stops cells that are full, and enforces the run budget.

### 7.7 Provenance
Attached to every accepted record: spec version, generator and judge model IDs and versions, prompt hash, random seed, coverage cell, tool trace, the result of each validation layer, repair count, and any human decisions.

### 7.8 Artefact store
Saved outputs of each stage (coverage plans, tool-response cache, candidate and accepted records, drop logs, run logs), keyed by spec version. Runs can be resumed, and results are cached across runs.

### 7.9 Metrics engine
Computes §8 during the run (for monitoring) and at the end (for the gate).

### 7.10 HITL queue
An optional review interface and queue that feeds two places: records resolved by people, and new gold-set entries.

---

## 8. Metrics and release thresholds

Every metric is reported **overall and per cell**. The thresholds are **set in advance in `task.yaml`**. The values below are only examples.

| Metric | Definition | Direction | Example threshold |
|---|---|---|---|
| **Fidelity** | Share of accepted records where the judge's verdict agrees with the intended label | quality | ≥ 0.95 |
| **Judge agreement (κ)** | Cohen's κ between the judge and humans on the gold set | quality | ≥ 0.70 |
| **Coverage** | Share of cells at or above quota; minimum fill of any cell | quality | every cell ≥ 90% |
| **Balance** | Label/class distribution compared with its target | quality | within ±5 pts |
| **Diversity: lexical** | distinct-n; self-BLEU | quality | set per task |
| **Diversity: semantic** | Embedding cluster entropy or Vendi score | quality | set per task |
| **Error rate: per stage** | Rejections ÷ candidates, for each layer L1–L6 | quality / cost | monitored |
| **Error rate: residual** | Estimated error remaining in accepted records, from judge-vs-human disagreement on the gold set | quality | ≤ 0.05 |
| **Governance violations** | PII, toxicity, secrets or leakage hits in the *released* set | governance | **0** (hard) |
| **Seed / held-out overlap** | Maximum similarity to any seed or held-out item | governance | below the similarity threshold |
| **Cost per accepted record** | Tokens, money and time ÷ accepted records | cost | within budget |
| **Yield** | Accepted ÷ candidates generated | cost | monitored |

---

## 9. The three directions — features in detail

### 9.1 Quality
- Coverage planned from keyword expansion and axis crossing, with a quota for every cell.
- Bloom-level axis for variety in the kind of thinking each request asks for (from DS²-Instruct).
- **Deliberate hard negatives:** specs can declare confusable cells, e.g. FAG's permitted general advice with advisory wording but a correct "no breach" label. These stop a model learning surface cues.
- Code-owned labels in `label_first` mode.
- A judge blind to the intended label checks fidelity, calibrated against humans.
- Repair with error feedback, not blind retry.
- Diversity measured and de-duplication enforced.
- Rejection skew prevented by regenerating in the same cell.

### 9.2 Governance
- Seed PII gate at intake (checks that pre-preparation was done).
- L3 scanning of every record: PII, toxicity, secrets, sensitive tool-data leakage, real entities.
- L4 checks for seed copying and held-out contamination. The held-out set is **never used for generation**; the overlap gate reads it only when given a path at run time (as [scripts/check_test_overlap.py](scripts/check_test_overlap.py) does today).
- A tool gateway with allowlists, sensitivity labels and read-only defaults.
- Data destinations follow from each task's model selection (D12) and are recorded in provenance and the governance report.
- Full provenance per record, plus a governance report with every release.
- Governance failures are hard drops; there is no trade-off against quality.

### 9.3 Optimisation and time cost
- **The cheapest layers run first.** L1–L4 filter records before the paid judge sees them.
- **Adaptive consistency:** a calibrated judge's confidence replaces K votes; K votes only on escalated cases where confidence isn't enough.
- **Prompt layout for caching:** static content (rubric, schema, instructions) goes first and variable content last. This works with vLLM prefix caching and Anthropic prompt caching.
- **Batch and async execution:** concurrent requests, batch engines, and provider batch APIs for runs that aren't urgent.
- **A decision model as judge (Jev),** for low cost and low latency at scale (vendor-stated: 70–500 ms, $0.042 per million input tokens); the generative reason-writing judge runs only where a reason is required.
- **Model per stage,** so each stage uses the model size it actually needs.
- **Quota early-stop,** so no money is spent on cells that are already full.
- **A tool-response cache** and **cached artefacts** (coverage plans reused across runs).
- **Budgets per task** (tokens, money, time), with a clean stop that saves progress.
- **Retrieval indexes** are built once and persisted (fixing a problem in DS²-Instruct, §12.1).

---

## 10. Human-in-the-loop checkpoints

Every checkpoint is **optional**, and each task switches it on in its spec. There's no release sign-off in v1: the gate is automatic.

| Checkpoint | Stage | What people do | What it feeds |
|---|---|---|---|
| **Approve coverage plan** | 1 | Review or edit the keywords and grid before any generation spend | the coverage plan |
| **Review flagged records** | 3 | Resolve judge disagreements and low-score records | accepted/dropped records **and** the gold set |
| **Calibrate the judge** | 4 | Label a gold set | judge κ, which decides whether the judge is trusted |

With no human sign-off, **judge calibration is the main source of trust**. The residual error rate is estimated from it (§8).

---

## 11. Generation modes

| | `label_first` | `answer_emergent` |
|---|---|---|
| Who fixes the label or answer | Code (spec + hooks), before generation | The model, during generation |
| What the model writes | Text that matches a fixed recipe | The answer itself |
| L6 consistency means | K judge votes must **agree with the fixed label** | K answers vote; **the majority becomes the answer** |
| Main risk | The text doesn't match the label (caught by L5/L6) | The majority is consistently wrong (caught by calibration) |
| Inherited from | FAG repo | DS²-Instruct |

---

## 12. Lessons from the inherited codebases

### 12.1 DS²-Instruct ([src_original/DS2-Instruct](src_original/DS2-Instruct))
**Reused:** bi-directional keyword expansion; retrieval-augmented keyword extraction; Bloom-level instruction generation; self-consistency filtering; a separate stage and saved file between each step.

**Known problems to avoid:**
- The keyword-extraction prompt is always given `found_keywords=[]`, so the model can't see which keywords already exist.
- The BM25 index is rebuilt over the whole corpus on every retrieval call.
- The `wikipedia_data/` corpus isn't in the repo; its path is relative to the working directory, and `WIKIPEDIA_CONFIG` is never used.
- Keyword expansion silently falls back to random mock keywords when parsing fails, which hides a broken backend.
- The consistency score counts unparseable (`None`) answers in K, and tasks with no answer extractor skip filtering entirely.
- The shell script's default sizes are smoke-test values (e.g. `QG_MAX=20`).

### 12.2 FAG generator ([scripts/](scripts/))
**Reused:** the scenario recipe sampled in code, with the model writing only the prose; the policy rule as deterministic code; verbatim-span validation; derived (not annotated) policy categories; deliberate hard negatives; balance by design, not matched to real-world prevalence; the backend abstraction; writing records as they are generated.

**Known problems to avoid:**
- Retries resend the identical prompt, with no error feedback.
- A dropped scenario is replaced by a *new random* scenario, so the distribution can skew.
- There is no check that the text matches its label: a "no breach" record containing advice passes as long as its spans are empty.
- `USE_ANTHROPIC=1` isn't read anywhere; the backend is hard-coded to MLX in `config.py`.
- The MLX backend ignores `temperature`.

---

## 13. FAG as the reference use case and test suite

FAG is the **first task spec** and the **pipeline's main test case**.

- **Port:** FAG's `config.py` domain data becomes `task.yaml`. `expected_breach`, the sampler conditioning, the verbatim-span check and `derive_policy_categories` become `hooks.py`.
- **Why it's a good test case:** the correct outcome of every FAG record can be computed exactly, so the pipeline can be tested against known answers.
- **Test strategy:**
  - For each layer L1–L6, a set of records built to fail *only* at that layer, e.g. a wrong turn order (L1), a reworded span (L2), an embedded fake TFN (L3), a copied seed (L4), a "no breach" record containing advice (L5).
  - Checks that the cascade stops at the right layer and handles each failure correctly (repair / drop / review queue).
  - Scheduler tests: quotas are filled, same-cell regeneration works, and drops don't skew the distribution.
  - Release-gate tests: pass and fail against known metric values.
  - A mock model backend, so tests are deterministic and cost nothing.
- **Second use case:** a DS²-Instruct task (e.g. CFA, `answer_emergent`), to prove the framework handles both generation modes.
- The held-out FAG evaluation CSVs are **never** read by the pipeline or the tests. Contamination is checked only by the overlap gate, when it is given a path explicitly.

---

## 14. What needs to be built

A suggested order. Each milestone ends with FAG running end to end on what exists so far.

| # | Milestone | Components | Done when |
|---|---|---|---|
| M1 | **Core skeleton** | Spec schema and loader, hook interface, task-type registry (classification-with-spans), model registry (port the backends), artefact store, provenance | FAG spec loads and compiles; a mock backend produces records |
| M2 | **Deterministic validation** | L1, L2, repair loop with error feedback, drop logging, scheduler with quotas and same-cell regeneration | FAG runs end to end with L1–L2; per-layer failure tests pass |
| M3 | **Governance** | Governance profile, L3 scanners (PII + domain patterns, toxicity, secrets), L4 overlap (seeds, corpus, optional held-out), seed PII gate at intake | Governance failure tests pass; zero violations in output |
| M4 | **Judge** | Judge interface, decision-SLM adapter, L5 fidelity, L6 adaptive consistency, calibration workflow (gold set → κ) | FAG "no breach but advises" records are caught; κ reported |
| M5 | **Coverage planning** | Keyword expansion (↑/↓), retrieval with a persisted index, axis crossing, Bloom axis | A coverage plan is generated, cached and used by the scheduler |
| M6 | **Agentic tools** | Tool registry, tool gateway (allowlist, budgets, sensitivity labels, cache, trace), agent loop in the generator | A task uses tools; traces are in provenance; replay is exact |
| M7 | **Evaluation and release** | Metrics engine, release gate, dataset card, governance and metrics reports | FAG dataset released automatically against its thresholds |
| M8 | **HITL and optimisation** | Review queue, plan-approval step, batch/async execution, prompt-cache layout, budgets | Cost per accepted record reported and reduced |
| M9 | **Second use case** | `answer_emergent` task type (DS²-Instruct CFA) | Both generation modes run on the same core |

---

## 15. Decisions made

| # | Decision |
|---|---|
| D1 | The framework supports multiple task types; **the task definition declares its type**. |
| D2 | Seed obfuscation stays in **pre-preparation** for now; the framework re-scans seeds at intake. It may move inside later. |
| D3 | Human review is **optional per task**, at three points: coverage-plan approval, review of flagged records, judge calibration. **No human sign-off before release.** |
| D4 | Each task has **pre-defined tools**; **the generator agent decides** when to call them, through a governed gateway. |
| D5 | Release thresholds are **set in advance in the task spec**. |
| D6 | Seeds can be **a few examples or a larger annotated set**, depending on the task. |
| D7 | Use cases are defined as a **declarative spec plus optional code hooks**. |
| D8 | Target scale is **1k–50k records per task**, with **mixed hosting** (local and API) chosen per stage. |
| D9 | The judge returns **verdict + rubric scores**; a **reason** only when the rubric requires one. |
| D10 | Build the framework **as a new codebase**, and port FAG onto it as the first use case and test suite. |
| D11 | The judge is a **decision model**: primary candidate **Jev** (TypeSafe AI, System One), behind a typed, swappable interface. A secondary generative judge writes reasons when the rubric requires one. |
| D12 | **Data destinations are decided by model selection:** the endpoint of each model a task picks is its destination. No separate endpoint policy is needed; destinations are recorded in provenance and the governance report. |

## 16. Open questions

1. **Jev in practice:** get early access; confirm how a per-task rubric is supplied (zero-shot schema vs. fine-tuning), the data-retention terms of its API, rate limits, and our own measurements of κ and calibration on the FAG gold set. *(Resolved: what Jev is — see §7.3.)*
2. **Diversity metrics:** confirm the pair to use (proposed: distinct-n + embedding cluster entropy or Vendi) and the embedding model.
3. **PII / toxicity engines:** choose the tools (general PII engine, toxicity classifier) and check they are allowed to run locally.
4. **Gold-set size per task:** the minimum number of human labels needed for a meaningful κ.
5. ~~Allowed endpoints per data class~~ — **resolved by D12** (endpoints follow model selection).
6. **Codebase location and name:** a new repo, or a new top-level package inside this one.
7. **Retrieval corpora:** the source documents for keyword retrieval per task (internal documents, public regulatory guidance, …) and whether each is allowed to be used.
