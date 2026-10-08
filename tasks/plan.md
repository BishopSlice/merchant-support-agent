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
- [ ] **Task 12a: Guided landing walkthrough.** A first screen that explains the problem (Google Shopping disapprovals) and who the app is for. Then a step-by-step walkthrough that casts the user as the merchant, tells them what to type or click at each step, and hands them over to the specialist inbox to see the case. Every screen makes clear which role the user is in (merchant, specialist or demo operator) and what the demo buttons do. Write the script after Task 11, once the agent's behaviour is settled, and follow the `frontend-ui-engineering` skill (accessibility, clear states, no AI-generated look).
- [ ] **Task 12: Write-up.** README as a case study, responsible AI page, one-slide business case. You record the demo video.

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| ADK API differs from what I expect | High | Task 3 proves it before anything else depends on it |
| Gemini free-tier rate limits slow evals | Medium | Small eval batches, retry with backoff, cache results |
| AI grader is unreliable | Medium | Hand-check a sample; keep rule-based scores as the main numbers |
| Two days is tight | Medium | Phases 1 to 3 are the must-have; Phase 4 trims to 20 cases if needed |

---

# v2 plan

_Draft for review, 8 Oct 2026. Based on PRD v2, SPEC v2 and ADRs 0003 to 0006. v1 (Tasks 1 to 12) is above. The tick boxes there weren't kept up to date; `tasks/todo.md` is the record._

## Ordering principle

Every eval expectation lands **before** the change it tests:
- **Data layer first.** The MCP-shaped data layer is built, and v1 behaviour is proven unchanged on it.
- **Then the evals.** The eval extensions, a blind held-out set and the new expectations are committed.
- **Then the agent.** The agent changes only after that.
- **Then the UI.** The new UI comes after the agent passes its gates, so the screenshots and replays show final behaviour.

## Phase 6: MCP-shaped data layer (no behaviour change)

- [ ] **Task 13: Merchant API models and mock.** `merchant_api` pydantic models for the documented resources; the `MerchantData` interface; `MockMerchantMcp` built on the v1 stores and feed rules; explicit automation settings for every store. Contract tests (SPEC, Evals d1 and d2): documented fixtures, the severity enum, the name format, the read-only allowlist, and an error on non-allowlisted calls.
- [ ] **Task 14: Port the agent's data tools.** Replace `check_feed` with the allowlisted MCP-shaped tools, with no change to the agent's instructions beyond naming them. Add per-turn latency to `chat`. Port the 47 v1 cases.

**Checkpoint E1:** pytest exits 0, and two runs of the 47 ported v1 cases pass (the regression gate in SPEC, Evals a). That shows the port changed nothing.

## Phase 7: Evals first (spec before prompt)

- [ ] **Task 15: Eval format and scorers.** Test-first support for `must_call` (tool and argument patterns), mock failure injection, entry context, the triage order rule, case-preview checks, the write-call counter, the no-invented-data check, latency p50 and p95, and new metrics in the scorecard.
- [ ] **Task 16: v2 held-out set, written blind.** 8 cases on new stores, committed before any prompt change. The leak guard is extended to it.
- [ ] **Task 17: New expectations and cases.** The `automatic-item-updates` help doc, written from its source page and verified against it. The six re-labelled v1 cases. 29 new main cases (SPEC, Evals c). Rubric updates, calibrated on v1 transcripts. A baseline run on the unchanged agent, so the "before" picture is recorded.

## Phase 8: Agent v2

- [ ] **Task 18: Agent behaviour.**
  - Automation routing (check `get_automatic_improvements` first)
  - The triage order
  - Graceful failure when data tools fail
  - Using entry context instead of re-asking
  - `create_handoff_case` returning the merchant-facing preview and recording the automation state

  Each is one small, test-first change, with an eval run per change on the affected categories.

**Checkpoint E2:** two runs of the main v2 set (69), the v1 held-out set (7) and the v2 held-out set (8) meet every target and hard gate in SPEC, Evals e. `evals.compare` runs v1 against v2 on the ported cases.

**Task 18b: One call per answer** ([ADR 0008](../docs/decisions/0008-one-call-answers.md)). Vikrant asked for it on 8 Oct, replacing the latency decision. Code preloads the context, and the model answers in one structured call; the tool loop is the recorded fallback. Model calls per turn and the fallback rate are in the shared metrics. `gemini-3.5-flash-lite` was tried and missed targets, including a hard gate, so the agent stays on `gemini-3.6-flash`, as does the grader. Check on the 14 latency cases, then Checkpoint E2 in full.

**Eval runs are parallel by default** (Vikrant, 8 Oct): 5 cases at a time, with `--workers 1` for latency measurements.

## Phase 9: Product surface

- [ ] **Task 19: FastAPI app.** Endpoints, per-session isolated demo data, the access code, session and daily caps, replay serving, the specialist demo login. API tests for all of it (SPEC, Evals f).
- [ ] **Task 20: Material Web shell.**
  - App bar and disabled nav
  - Needs attention table
  - Edit product dialog
  - Agent side panel with "Help me fix this" and a Help entry
  - Case preview
  - Specialist page
  - The "Concept prototype" label

  Follow the frontend-ui-engineering skill. Browser checks: the merchant journey, keyboard, contrast script, the branding test, phone width. Screenshots.
- [ ] **Task 21: Retire Streamlit.** Remove the Streamlit app and guide after Task 20's checks pass, then remove the dependency, in separate commits. Update the README commands.

**Checkpoint F:** the full merchant journey works in the shell in live and replay modes, and all product checks pass.

## Phase 9b: Observability ([ADR 0007](../docs/decisions/0007-observability-dashboard.md))

- [ ] **Task 21a: Shared metrics module and event store.** `merchant_agent.metrics` holds every metric definition, used by both evals and the dashboard, with tests that they agree. A SQLite event store. Masking of emails and phone numbers before storage. 30-day text retention. Events written after each reply, with the overhead measured.
- [ ] **Task 21b: Tracing.** ADK OpenTelemetry spans tagged with session, agent version, entry point and traffic source. Eval runs traced as "eval traffic"; replay excluded. *Declaring OpenTelemetry directly needs approval first.*
- [ ] **Task 21c: Feedback and sampled grading.** Thumbs up and down in the side panel. Grading of about 10% of live conversations within a daily budget, with the sample size recorded.
- [ ] **Task 21d: The /ops page.** Its own access code, panels 1 to 5, trace drill-down, alerts banner, source labels and small-sample warnings. *A chart library needs approval; the fallback is plain SVG.* Minimum if short on time: panels 1, 3 and 4 plus the trace view.

**Checkpoint F2:** /ops shows live and eval traffic correctly labelled, safety panel definitions match the eval hard gates (tested), and logging adds no wait to replies.

## Phase 10: Release

- [ ] **Task 22: Replays and hosting.** Record replays from the release candidate, with a freshness test. Container setup. **The host choice and its account and billing are a separate approval.**
- [ ] **Task 23: Final evals and write-up.** A new 10-item hand-check with Vikrant. Final two runs of every set. The `evals/CHANGELOG.md` disclosure log. Update the README, `docs/v1-results.md` (as history), a new `docs/v2-results.md`, the business case (using the uniquely agent-resolved rate) and the responsible AI page.

**Checkpoint G:** every release gate in SPEC, Evals h passes. Vikrant records the demo video.

## v2 risks

| Risk | Impact | Mitigation |
|---|---|---|
| Material Web gaps (maintenance mode) | Medium | Pin a version; fall back to plain elements with Material 3 tokens ([ADR 0003](../docs/decisions/0003-ui-stack-material-web.md)) |
| The port silently changes agent behaviour | High | Checkpoint E1: 47 v1 cases, two runs, before anything else changes |
| Overfitting new expectations | Medium | Blind v2 held-out set (Task 16), the leak guard, the disclosure log |
| Automation advice wrong or unsupported | High | Verified help doc, routing cases, grader rubric update |
| Hosted demo cost or abuse | Medium | Replay by default; code and caps; separate approval for hosting |
| The mock drifts from Google's real shapes | Medium | Contract tests from documented fixtures, each citing its source |
| Scope creep beyond Needs attention | Medium | The PRD non-goals; disabled nav |
| Eval spend | Low | About $8 estimated for v2 (SPEC, Evals g); reported per run |
