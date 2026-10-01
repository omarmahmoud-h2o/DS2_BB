# PRD 2 — Judge independence fixes (`sdgf`)

Follow-up work found while setting up the groundness task (`sdgf/tasks/groundness`). The guardrails and conventions in [PRD.md](PRD.md) apply unchanged; section numbers (§) refer to FRAMEWORK_DESIGN.md.

Status: **open, in progress.**

## Problem 1 — L6 votes in label_first are not independent

**Where:** `validate/l6_consistency.py` (`_judge_votes`), `pipeline.py` (`_layer_implementations`, L6 is built with `judge=self.judge`).

**What happens:** under `label_first`, L6 takes its K votes by calling the *same* `LLMJudge` K times: same model, same prompt, and `models.judge.temperature` (0.0 in FAG and groundness). A deterministic judge returns the same verdict K times, so L6 repeats L5's answer at K× the cost and adds almost no information. Every record that escalates pays for it; in groundness most hard defects escalate (`on_hard_cells`).

**Contrast:** under `answer_emergent`, `BackendAnswerer` cycles temperatures (0.7, 0.8, 0.9) per vote, so votes vary. The judge-vote path has no equivalent.

**Why it matters:** §6.4 and §11 rely on K votes to catch records where a single verdict is unreliable. With identical votes, a wrong L5 verdict is confirmed, not challenged, and the escalation budget is spent for nothing.

## Problem 2 — the judge's context is the generator's instructions

**Where:** `judge/llm_judge.py` (`from_spec` sets `context = spec.task.description`).

**What happens:** `task.description` serves both the generation prompt and the judge prompt. It is written for the writer (in groundness: "annotate every claim as a span… is_target… the fixed parameters"), so the judge reads instructions meant for someone else. It is also the only place the judge learns domain definitions (support levels, category minimums), and it can't receive judge-only material such as worked examples (e.g. `rubric.md`'s "up to 3 days" vs "3 days" cases). No label leaks — the record section carries only `judge_fields` — but the judge's view of the task can't be shaped separately.

## Tasks

- [x] Add per-vote diversity for label_first L6: a `validation.consistency` section (or extend `consistency_k`) with `temperatures` (cycled per vote, default `[0.7, 0.8, 0.9]` to match `BackendAnswerer`) and an optional `models.consistency_judge` stage so votes can come from a different model than L5; L6 builds its own judge from these instead of reusing `self.judge`; tests with a MockBackend that returns different verdicts per temperature, proving votes differ and the majority is computed over them
- [x] Decide and document whether a temperature-0 judge with no diversity configured should warn at stage 0 (K identical votes) or be rejected when `consistency_k > 1`; implement the chosen behaviour with a test
- [ ] Record per-vote model and temperature in L6 details and provenance, so vote agreement can be analysed after a run
- [ ] Add an optional `rubric.judge_context` (string) used as the judge's `## Context` instead of `task.description`; fall back to `task.description` when unset so FAG and CFA are unchanged; tests that the generation prompt and the judge prompt get their own text and that the label still never appears in the judge prompt
- [ ] Allow judge-only worked examples (`rubric.examples`: record view + expected verdict, fictional only, scanned for PII at stage 0 like seeds); render them in the judge's static prefix; tests
- [ ] Write `judge_context` for `sdgf/tasks/groundness`: support levels, category minimums and the rubric's worked examples, without generator instructions
- [ ] Update `sdgf/docs/framework.md` (L5 and L6 sections) and the README `rubric` / `validation` reference for the new keys
- [ ] Checkpoint: full suite passes; a mock groundness run shows L6 votes that differ across temperatures
