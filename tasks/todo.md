# Task list

- [x] Task 1: Data shapes and sample store
- [x] Task 2: Feed checker
- [x] Checkpoint A: unit tests pass, all planted problems found
- [x] Task 3: Agent with one tool (terminal chat)
- [x] Task 4: Help docs and search
- [x] Task 5: Handoff
- [x] Checkpoint B: full journey in terminal
- [x] Task 6: Merchant chat screen
- [x] Task 7: Specialist inbox screen
- [x] Checkpoint C: browser demo works
- [x] Task 8: Eval cases
- [x] Task 9: Runner and rule-based scores
- [x] Task 10: AI grader
- [x] Checkpoint D: full scorecard
- [x] Task 11: Fix the worst failure
- [x] Task 12a: Guided landing walkthrough
- [ ] Task 12: Write-up and demo

Details for each task are in `tasks/plan.md`.

## v2 (draft plan, awaiting approval)

- [x] Task 13: Merchant API models and mock, plus contract tests
- [x] Task 14: Port the agent's data tools
- [ ] Checkpoint E1: 47 v1 cases pass on the port, twice. **Not cleanly met** (commit 4b88343): run 2 passed 47 of 47, run 1 passed 45 of 47. Both failures were intermittent agent slips, and both cases passed 6 of 6 reruns on 8 Oct (about 1 slip in 8 runs each). No patterns were changed.
  - `no-doc-refurbished`: the reply named the "condition attribute", which no retrieved doc supports. This is a grounding slip, so it's watched in E2.
  - `suspended-why-not-showing`: the saved case left out the suspension's detail (missing returns policy and contact details). Fixed in Task 18: `create_handoff_case` records the account issues from the data itself, not from the model.
- [x] Task 15: Eval format and scorers
- [x] Task 16: v2 held-out set, written blind
- [ ] Task 17: New expectations, re-labelled cases, automation help doc, baseline run
- [ ] Task 18: Agent v2 behaviour
- [ ] Checkpoint E2: all eval targets and hard gates, twice
- [ ] Task 19: FastAPI app
- [ ] Task 20: Material Web shell
- [ ] Task 21: Retire Streamlit
- [ ] Checkpoint F: merchant journey in the shell, product checks
- [ ] Task 21a: Shared metrics module and event store
- [ ] Task 21b: Tracing (OpenTelemetry needs approval)
- [ ] Task 21c: Feedback and sampled grading
- [ ] Task 21d: The /ops page (a chart library needs approval)
- [ ] Checkpoint F2: /ops correct, definitions match the evals, no added wait
- [ ] Task 22: Replays and hosting (hosting needs separate approval)
- [ ] Task 23: Final evals and write-up
- [ ] Checkpoint G: v2 release gates
