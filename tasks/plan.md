# Implementation plan: Merchant Support Agent

_Based on the approved `SPEC.md` and `docs/PRD.md` (approved 7 Oct 2026)._

## Overview

We build in thin vertical slices. The riskiest piece is getting a real Gemini agent calling our tools, so we prove that early (Phase 2) with just one tool, then add the rest. Screens come after the agent works from the command line, and evals come after the screens.

## Architecture decisions

- **Tools are plain functions.** The ADK agent wraps them; tests never call the model.
- **Rule checks are a list of small functions.** Each takes a product and returns zero or more issues. Adding a rule means adding one function and one test.
- **Stores live in files.** `data/stores/<store_id>/store.json` + `feed.csv`. Evals can point at their own small stores.
- **Cases are JSON files** in `runtime/cases/` (gitignored). Simple to inspect, easy to swap for a database later.
- **Help search starts as keyword scoring.** Good enough for ~10 docs; the search function's interface stays the same if we switch to embeddings later.

## Who runs what

- Unit tests: I can run these myself.
- Anything that calls Gemini: runs on your Mac (my sandbox can't reach Google's API). I'll give you one command per checkpoint, or run it through a session on your Mac if you prefer.

## Phase 1: Foundation (no AI yet)

- [ ] **Task 1: Data shapes and sample store.** `models.py`, `config.py`, a store loader, and a sample store (~30 products) with at least 6 planted problem types plus one suspended-account store.
- [ ] **Task 2: Feed checker.** One rule check per planted problem, written test-first, plus `check_feed(store_id)` that groups issues by type.

**Checkpoint A:** `uv run pytest` passes; the checker finds every planted problem.

## Phase 2: Thin agent end to end (riskiest, so early)

- [ ] **Task 3: Agent with one tool.** ADK agent with `check_feed` only, plus a terminal chat script. You run it once and paste me the transcript.
- [ ] **Task 4: Help docs and search.** ~10 paraphrased help summaries with source links, `search_help_docs` tool, wired into the agent.
- [ ] **Task 5: Handoff.** `create_handoff_case` tool, case storage, and the PRD handoff rules in the agent's instructions.

**Checkpoint B:** the full PRD journey works in the terminal, including one handoff.

## Phase 3: Screens

- [ ] **Task 6: Merchant chat screen** in Streamlit.
- [ ] **Task 7: Specialist inbox screen** listing cases with their full summary.

**Checkpoint C:** you can demo the journey in the browser.

## Phase 4: Evals

- [ ] **Task 8: Eval cases.** Case file format plus 40 cases: easy fixes, multi-issue feeds, every handoff rule (3+ each), angry merchants, off-topic asks.
- [ ] **Task 9: Runner and rule-based scores.** Resolution rate, handoff precision and recall, cost per case. Results saved per run.
- [ ] **Task 10: AI grader.** Second model grades wrong advice and case completeness against a rubric; you hand-check 10.

**Checkpoint D:** one command prints the full PRD scorecard.

## Phase 5: Improve and package

- [ ] **Task 11: Fix the worst failure** and rerun evals, recording before vs after.
- [ ] **Task 12: Write-up.** README as a case study, responsible AI page, one-slide business case. You record the demo video.

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| ADK API differs from what I expect | High | Task 3 proves it before anything else depends on it |
| Gemini free-tier rate limits slow evals | Medium | Small eval batches, retry with backoff, cache results |
| AI grader is unreliable | Medium | Hand-check a sample; keep rule-based scores as the main numbers |
| Two days is tight | Medium | Phases 1 to 3 are the must-have; Phase 4 trims to 20 cases if needed |
