# PRD — Synthetic Data Generation Framework (`sdgf`)

Build the generic synthetic-data framework specified in **FRAMEWORK_DESIGN.md**. Port the FAG (Financial Advice Guardrail) generator onto it as the first use case and the pipeline's test suite. Read FRAMEWORK_DESIGN.md before starting any task; section numbers (§) below refer to it.

## Guardrails (MUST follow — these replace .ralphy/config.yaml rules, which Ralphy does not send in PRD mode)

1. **Never read, open, list or copy** `../single_turn_financial_advice.csv`, `../multi_turn_financial_advice.csv`, or **any file outside this repository**. They are the user's held-out evaluation set.
2. **Do not modify** `src_original/`, `output/`, `scripts/`, `shell/`, `synthetic_conversations.jsonl`, `VRM_Compliance_*.md`, `Task description.md`, `environment.yml`, `CLAUDE.md`, `FRAMEWORK_DESIGN.md`, or `.git/`. You may *read* `scripts/` and `src_original/` to port logic.
3. All new code goes under `sdgf/`. Don't refactor the existing FAG pipeline in place.
4. **Don't reopen decisions in FRAMEWORK_DESIGN.md §15.** If a task seems to conflict with one, implement the decision and note the concern in `.ralphy/progress.txt`.
5. **No real PII** anywhere in code, tests, fixtures or seeds. Use obviously fictional values, e.g. `Acme Test Pty Ltd`, account `000-000 00000000`, TFN `000 000 000`.
6. **No real model or API calls** in tests. Every test uses the mock backend. Don't add API keys anywhere.
7. **Don't push** to any remote. Don't create branches or PRs.
8. Don't reintroduce a `compliance_status` field; keep FAG's `BREACH_RATE` at 0.5; never tune distributions to match any evaluation data.
9. Don't invent the Jev API. Jev's adapter stays an interface stub until its real API is documented (§7.3).

## Conventions

- **Python:** `/opt/anaconda3/bin/python` (3.13), already on PATH as `python`. Core dependencies are only `pydantic`, `pyyaml`, `jsonschema`, `numpy`, which are already installed. Heavy engines (Presidio, Detoxify, sentence-transformers, BM25 libraries) are **optional adapters**, imported lazily. Tests must never need them.
- **Layout:** a `src` layout. Package at `sdgf/src/sdgf/`, tests at `sdgf/tests/`, task specs at `sdgf/tasks/<name>/`.
- **Tests:** `cd sdgf && python -m pytest -q`. Every task adds or updates tests, and the full suite passes before a task is marked done.
- **Style:** type hints, small modules, docstrings only where intent isn't obvious. Match the plain style of `scripts/`.
- **Determinism:** every random draw takes an explicit seed or `random.Random` instance.
- **Done means:** the code is written, tests pass, the task line is marked `- [x]`, and one line is appended to `.ralphy/progress.txt` saying what changed.

## Target layout

```
sdgf/
  pyproject.toml
  src/sdgf/
    spec/        schema.py loader.py hooks.py compile.py
    tasktypes/   base.py registry.py classification_spans.py sft_qa.py
    models/      base.py registry.py mock.py openai_compat.py anthropic.py vllm.py mlx.py
    coverage/    keywords.py retrieval.py axes.py plan.py
    generate/    scheduler.py generator.py prompts.py
    tools/       registry.py gateway.py cache.py builtin.py
    governance/  profile.py pii.py toxicity.py secrets.py entities.py
    validate/    base.py cascade.py l1_schema.py l2_rules.py l3_governance.py l4_overlap.py l5_judge.py l6_consistency.py repair.py
    judge/       interface.py llm_judge.py jev.py calibration.py
    evaluation/  metrics.py diversity.py gate.py reports.py
    store/       artefacts.py provenance.py
    hitl/        queue.py
    pipeline.py  cli.py
  tasks/fag/     task.yaml hooks.py seeds.jsonl
  tests/
```

---

## M1 — Core skeleton

- [x] Create sdgf/pyproject.toml (package sdgf, src layout, python 3.11+, deps pydantic pyyaml jsonschema numpy, optional extras pii toxicity embeddings retrieval), empty package modules per the target layout, and sdgf/tests/test_smoke.py that imports sdgf; suite passes with python -m pytest -q
- [ ] Implement sdgf/src/sdgf/spec/schema.py: pydantic models for every task.yaml section in FRAMEWORK_DESIGN.md §4.2 (task, output_schema, rubric, seeds, coverage, tools, governance, models, validation, thresholds, hitl, budget), with validation errors that name the failing field; add tests for a valid minimal spec and for each missing required section
- [ ] Implement sdgf/src/sdgf/spec/hooks.py: the four hook points from §4.3 (label_rule, sampler_constraints, extra_validators, post_process) as a typed Protocol, plus a loader that imports an optional hooks.py next to task.yaml and checks each present function's signature; test with a temporary hooks file, including a wrong-signature case
- [ ] Implement sdgf/src/sdgf/spec/loader.py and compile.py: load task.yaml plus hooks.py plus seeds, return a frozen CompiledSpec, and compute spec_version as a sha256 over spec, hooks source and seeds content; test that changing any one of the three changes spec_version
- [ ] Implement sdgf/src/sdgf/tasktypes/base.py and registry.py: a TaskType interface (output JSON schema, generation_mode label_first or answer_emergent, default axes, default validators, optional answer extractor) and a registry keyed by name; unknown task type raises a clear error; tests
- [ ] Implement sdgf/src/sdgf/tasktypes/classification_spans.py: task type for label-first classification with span annotations (messages with numbered alternating turns, label, spans with turn, text, category), registered as classification_spans; tests for its schema
- [ ] Implement sdgf/src/sdgf/models/base.py, registry.py and mock.py: one ModelBackend interface with call(prompt, max_tokens, temperature, tools=None) returning text and optional tool calls; a registry that builds backends per stage from spec.models and records each backend's hosting (local or provider API) for provenance per D12; a MockBackend driven by scripted responses or a callable, for tests; tests
- [ ] Port the real backends from scripts/model_backends.py into sdgf/src/sdgf/models/openai_compat.py, anthropic.py, vllm.py and mlx.py behind the new interface, importing their SDKs lazily; fix the known issues from §12.2 (MLX must pass temperature via a sampler; backend chosen only from spec, no hardcoded default); tests use monkeypatched clients only and make no network calls
- [ ] Implement sdgf/src/sdgf/store/artefacts.py: a run directory keyed by spec_version and run id, JSONL append writers that flush per record, stage artefact read and write, and resume support that skips stages whose artefact exists for the same spec_version; tests with tmp_path
- [ ] Implement sdgf/src/sdgf/store/provenance.py: a Provenance record per §7.7 (spec_version, generator and judge model ids and hosting, prompt hash, random seed, cell id, tool trace, per-layer results, repair count, human decisions) attached to every accepted record; tests
- [ ] Create sdgf/tasks/fag/task.yaml porting the FAG domain data from scripts/config.py (Corps and non-Corps topics, tiers, 15 signals and groupings, weights, BREACH_RATE 0.5, length buckets) into the spec schema with task type classification_spans and generation_mode label_first; example thresholds from §8; loading it compiles without errors; test
- [ ] Create sdgf/tasks/fag/hooks.py porting from scripts/policy_categories.py and scripts/scenario_sampler.py: label_rule (expected_breach), sampler_constraints (tier, scope, signals, severity, is_corps_question, denial_present conditioning), post_process (derive_policy_categories); add sdgf/tests/test_fag_parity.py that imports scripts/policy_categories.py via sys.path and asserts identical outputs across all tier, scope and signal combinations
- [ ] Create sdgf/tasks/fag/seeds.jsonl with 6 hand-written, fully fictional FAG seed conversations (3 breach, 3 non-breach including one permitted-general-advice hard negative) that pass the classification_spans schema; do not derive them from any evaluation file; test that seeds load and validate
- [ ] M1 checkpoint: run the full suite, confirm the FAG spec loads and compiles, and write a short M1 summary with any open concerns to .ralphy/progress.txt

## M2 — Scheduler, generation, deterministic validation

- [ ] Implement sdgf/src/sdgf/generate/scheduler.py: cells with quotas, picks the cell furthest below quota, stops a cell once full, requeues failures into the same cell, and enforces the run budget; tests proving quotas fill exactly and that dropping records cannot change the final per-cell distribution
- [ ] Implement sdgf/src/sdgf/generate/prompts.py: build a generation prompt with all static content first (task description, rubric, output schema, few-shot seeds) and cell-specific content last, so prefix caching works; expose the static-prefix hash; test that two cells share the same prefix hash
- [ ] Implement sdgf/src/sdgf/generate/generator.py: for one cell, apply sampler_constraints, build the prompt, call the generator backend, extract JSON (port utils.extract_json), and merge model prose with code-owned fields so labels always come from the cell never the model; tests with MockBackend
- [ ] Implement sdgf/src/sdgf/validate/base.py and cascade.py: a Layer interface returning pass, fail_repairable or fail_hard with a machine-readable error, and a cascade that runs layers in configured order and stops at the first failure; tests with fake layers covering ordering and short-circuit
- [ ] Implement sdgf/src/sdgf/validate/l1_schema.py: validate records against the task type's JSON schema plus structural rules (turns numbered from 1, roles alternate starting with customer where the task type defines roles); errors are repairable; tests for each failure
- [ ] Implement sdgf/src/sdgf/validate/l2_rules.py: spec keyword rules (required or forbidden), label agreement with the label_rule hook, and extra_validators hooks; errors are repairable; tests
- [ ] Add FAG extra_validators to sdgf/tasks/fag/hooks.py porting utils.validate_conversation from scripts/utils.py: verbatim span substring check, span categories within signals, every declared signal has a span, breach implies at least one span, non-breach implies empty spans, severity iff breach, unexplained breach rejection; one test per rule
- [ ] Implement sdgf/src/sdgf/validate/repair.py: on a repairable failure, re-prompt the generator with the original prompt plus the specific validator errors, up to validation.repair_tries, in the same cell; after exhaustion drop with a logged reason per cell and layer; tests showing a MockBackend that fixes its output on the second try is accepted
- [ ] Implement sdgf/src/sdgf/pipeline.py for stages 0, 2 and 3 with L1 and L2 only: compile spec, schedule, generate, validate, repair, write accepted records with provenance and a drop log; end-to-end test running the FAG spec with a MockBackend that returns valid records for 20 records
- [ ] Add sdgf/tests/test_fag_layer_failures.py: hand-built FAG records that each fail exactly one of L1 or L2 (wrong turn order, reworded span, label disagreeing with tier and scope, missing span for a declared signal) and assert the cascade stops at that layer with the expected error
- [ ] M2 checkpoint: run the full suite, run the FAG end-to-end mock test, and write an M2 summary to .ralphy/progress.txt

## M3 — Governance

- [ ] Implement sdgf/src/sdgf/governance/profile.py: a global governance profile merged with per-task tightening from spec.governance, where a task may only tighten, never loosen, and documented exceptions must be declared; tests that loosening attempts raise
- [ ] Implement sdgf/src/sdgf/governance/pii.py: a regex PII scanner (email, phone, AU ABN, TFN, BSB and account-number patterns, plus per-task patterns from the profile) returning typed findings with spans, and an optional lazily imported Presidio adapter behind the same interface; tests use only fictional values
- [ ] Implement sdgf/src/sdgf/governance/toxicity.py, secrets.py and entities.py: a keyword-list toxicity baseline plus optional Detoxify adapter, secret and credential patterns (API keys, private keys, tokens), and a real-entity deny and allow list; tests
- [ ] Implement sdgf/src/sdgf/validate/l3_governance.py: run all governance scanners, apply stricter handling to records whose tool trace carries a sensitive label, and treat every finding as fail_hard (drop, never repair); tests
- [ ] Implement sdgf/src/sdgf/validate/l4_overlap.py: character-shingle Jaccard similarity against seeds and against the accepted corpus so far (near-duplicates), plus an optional held-out check that only runs when an explicit held-out path is passed at run time and never feeds generation; optional embedding adapter; fail_hard above thresholds; tests use synthetic strings only
- [ ] Add the stage 0 seed gate in sdgf/src/sdgf/spec/compile.py: re-scan every seed with the PII and toxicity scanners and refuse to compile if any seed fails; check that listed tools exist in the tool registry and that every release threshold is set; tests
- [ ] Add L3 and L4 to the pipeline cascade and extend sdgf/tests/test_fag_layer_failures.py with records that fail only L3 (embedded fictional TFN, secret-like token) or only L4 (copied seed, near-duplicate), asserting a hard drop
- [ ] M3 checkpoint: run the full suite and write an M3 summary to .ralphy/progress.txt

## M4 — Judge and consistency

- [ ] Implement sdgf/src/sdgf/judge/interface.py: a typed judge interface per §7.3 where the rubric compiles into an output schema of a verdict enum plus rubric-score enums or bounded ints (at most 255 values each) plus per-field confidence, and optional reason text only when the rubric requires it; tests for rubric compilation
- [ ] Implement sdgf/src/sdgf/judge/llm_judge.py: a judge backed by any ModelBackend that prompts for the compiled schema as JSON and parses verdict, scores and confidence, and can also serve as the fallback reason-writing judge; the judge prompt must not contain the intended label; tests with MockBackend including a check that the label never appears in the prompt
- [ ] Implement sdgf/src/sdgf/judge/jev.py as an interface-only stub for Jev (TypeSafe System One) that raises NotImplementedError with a pointer to FRAMEWORK_DESIGN.md §7.3 and §16 Q1; register it so a spec can select it; do not guess its API; test that selecting it fails clearly
- [ ] Implement sdgf/src/sdgf/validate/l5_judge.py: call the judge blind to the label, compute fidelity as judge verdict agreeing with the intended label, repair on disagreement, route low-confidence results to the HITL queue when enabled, and call the fallback judge for reasons only when the rubric requires them; tests
- [ ] Implement sdgf/src/sdgf/validate/l6_consistency.py: run only on escalated records (contestable, hard, low confidence); with a judge whose calibration passed, use its confidence; otherwise run K votes, where label_first requires the majority to match the fixed label and answer_emergent makes the majority the answer; count unparseable votes as abstentions, fixing the §12.1 None-in-denominator bug; tests
- [ ] Implement sdgf/src/sdgf/judge/calibration.py: given a gold set of human labels, compute Cohen's kappa and expected calibration error with reliability bins, and persist a calibration result per judge model and spec_version that L5 and L6 read to decide trust; tests with known small examples
- [ ] Add a FAG test: a non-breach record whose assistant turn contains advice wording (for example, ideal for your business) passes L1 to L4 and is caught at L5 by a MockBackend judge that returns breach, proving the §12.2 blind spot is closed
- [ ] M4 checkpoint: run the full suite and write an M4 summary to .ralphy/progress.txt

## M5 — Coverage planning

- [ ] Implement sdgf/src/sdgf/coverage/keywords.py: seed keywords from the task description and seeds, bi-directional expansion (prerequisite and advanced prompts ported from src_original/DS2-Instruct/scripts/prompts.py) with dedup, passing the current keyword list into prompts (fixing the §12.1 empty found_keywords bug), and raising instead of silently falling back to mock keywords when parsing fails; tests with MockBackend
- [ ] Implement sdgf/src/sdgf/coverage/retrieval.py: a pure-Python BM25 index built once and persisted to the artefact store (fixing the §12.1 rebuild-per-call issue), plus keyword extraction from retrieved passages; tests on a tiny in-memory corpus
- [ ] Implement sdgf/src/sdgf/coverage/axes.py and plan.py: cross keywords with spec axes including a Bloom level axis (six levels with descriptions ported from src_original/DS2-Instruct/scripts/prompts.py), drop invalid combinations with sampler_constraints, assign quotas to reach target size and balance, and write coverage_plan.json cached by spec_version; support tasks that declare fixed axis values and skip expansion, as FAG does; tests
- [ ] Wire stage 1 into the pipeline so the scheduler reads cells and quotas from the coverage plan; add a test that FAG with fixed topics produces a plan whose label balance matches BREACH_RATE 0.5 within one record
- [ ] M5 checkpoint: run the full suite and write an M5 summary to .ralphy/progress.txt

## M6 — Agentic tools

- [ ] Implement sdgf/src/sdgf/tools/registry.py: tools declared once with name, JSON input schema, sensitivity level and read_only flag (default true), with each task listing the tools it may use; tests
- [ ] Implement sdgf/src/sdgf/tools/cache.py and gateway.py: every tool call goes through the gateway, which enforces the task allowlist, a per-record call and token budget, attaches the tool's sensitivity label to the result, caches responses by tool name plus canonical arguments, and appends every call to the record's tool trace; tests for denial, budget exhaustion, cache hit and trace content
- [ ] Extend sdgf/src/sdgf/generate/generator.py into an agent loop where the generator backend may return tool calls that are executed via the gateway and fed back until it returns a final record or hits the budget; MockBackend gains scripted tool calls; tests
- [ ] Implement sdgf/src/sdgf/tools/builtin.py with two safe read-only example tools (a fictional product-catalogue lookup over a local JSON fixture and a calculator) and a test that replays a record exactly from its cached tool trace
- [ ] M6 checkpoint: run the full suite and write an M6 summary to .ralphy/progress.txt

## M7 — Evaluation and release

- [ ] Implement sdgf/src/sdgf/evaluation/diversity.py: distinct-n and self-BLEU (pure Python), plus an optional embedding cluster-entropy adapter; report overall and per cell; tests on known small inputs
- [ ] Implement sdgf/src/sdgf/evaluation/metrics.py: compute every metric in §8 (fidelity, kappa from calibration, coverage fill per cell, balance, diversity, error rate per layer from the drop log, residual error estimate, governance violations, seed and held-out overlap, cost per accepted record, yield) overall and per cell; tests
- [ ] Implement sdgf/src/sdgf/evaluation/gate.py: compare metrics with spec.thresholds, pass or fail with a list of failing metrics and short cells, where governance violations above zero always fail; tests for pass, fail and hard-fail cases
- [ ] Implement sdgf/src/sdgf/evaluation/reports.py: on pass, write a versioned release directory with the dataset JSONL, a dataset card in markdown, per-record provenance, a governance report listing which external endpoints received data per D12, and a metrics report; on fail, write a shortfall report; tests
- [ ] Wire stages 4 and 5 into the pipeline so a failed gate sends the scheduler back to fill only the short cells, with a max-rounds limit; end-to-end FAG mock test that releases successfully and another that fails then recovers after one extra round
- [ ] M7 checkpoint: run the full suite and write an M7 summary to .ralphy/progress.txt

## M8 — HITL, CLI and optimisation

- [ ] Implement sdgf/src/sdgf/hitl/queue.py: a file-based review queue for flagged records (judge disagreement, low confidence) with resolve actions accept, reject and relabel, where resolved items are appended to the task's gold set; plus a coverage-plan approval checkpoint that pauses the pipeline until an approval file exists when spec.hitl enables it; tests
- [ ] Implement sdgf/src/sdgf/cli.py with subcommands validate-spec, plan, run, resume, evaluate, review and release, exposed as the sdgf console script in pyproject.toml; tests using a CliRunner-style subprocess call on the FAG spec with the mock backend
- [ ] Add concurrency to the pipeline: a bounded thread pool for generation and judge calls with per-stage concurrency set in spec.models, keeping output order-independent and deterministic per seed; tests that concurrent and sequential runs produce the same accepted set with the mock backend
- [ ] Add budget and cost tracking: count tokens and estimated cost per stage from backend responses, stop cleanly and resumably when spec.budget is exhausted, and report cost per accepted record; tests
- [ ] Write sdgf/README.md: install, the task.yaml reference, how to add a use case (spec plus hooks), running the FAG example with the mock backend, and the list of optional adapters
- [ ] M8 checkpoint: run the full suite and write an M8 summary to .ralphy/progress.txt

## M9 — Second use case (answer-emergent)

- [ ] Implement sdgf/src/sdgf/tasktypes/sft_qa.py: an answer_emergent task type for SFT question-answer pairs with pluggable answer extractors ported from src_original/DS2-Instruct/scripts/utils.py (multiple choice, yes-no-maybe, numeric, boxed math), registered as sft_qa; tests
- [ ] Create sdgf/tasks/cfa/task.yaml and seeds.jsonl porting the DS2-Instruct cfa task (task description, Bloom axis, keyword expansion enabled, K-vote consistency) with 5 fictional seed questions; end-to-end mock test that produces released SFT pairs, proving both generation modes run on the same core
- [ ] M9 checkpoint: run the full suite and write a final summary to .ralphy/progress.txt listing what is done, what is stubbed (Jev adapter, optional engines) and the open questions from FRAMEWORK_DESIGN.md §16
