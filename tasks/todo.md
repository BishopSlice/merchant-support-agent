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
- [x] Task 17: New expectations, re-labelled cases, automation help doc, baseline run
- [x] Task 18: Agent v2 behaviour. Latency experiments, all on the same 14 cases with nothing saved, 8 Oct:

  | Variant | Passed | p50 | p95 | Cost per case |
  |---|---|---|---|---|
  | Current (default thinking) | 13 of 14 | 13.8 s | 17.7 s | $0.025 |
  | Ask for parallel tool calls | 14 of 14 | 14.4 s | 18.9 s | $0.026 |
  | Thinking level MEDIUM | 14 of 14 | 14.0 s | 18.3 s | $0.025 |
  | Thinking level LOW | 12 of 14 | 9.2 s | 13.3 s | $0.019 |

  Each model call takes about 4 to 5 s, and a turn needs about 3 calls (data, help search, reply). Only LOW thinking moves latency, and it dropped two citations. Even LOW misses the 8 s p50 target. Both changes are reverted. The trade-off (quality against speed, or re-targeting latency as time to the first progress update in the side panel) is for Vikrant to decide.
- [x] Checkpoint E2: run on the one-call design with lower thinking. Every target and hard gate was met except automation routing on the main set (93%, one suspected false alarm left as scored). Main ran once at Vikrant's request; the held-out sets ran once each (`docs/v2-results.md`)
- [x] Task 19: FastAPI app
- [x] Task 20: Material Web shell
- [x] Task 21: Retire Streamlit
- [ ] Checkpoint F: merchant journey in the shell, product checks
- [x] Task 21a: Shared metrics module and event store (event writes measured at about 0.4 ms per turn, after the reply)
- [x] Task 21b: Tracing with OpenTelemetry (approved 8 Oct): step-by-step spans per turn in the event store and the /ops trace view
- [x] Task 21c: Feedback and sampled grading
- [x] Task 21d: The /ops page, with plain SVG charts (no chart library needed). Panels 1 to 4 and traces; panel 5 (releases) not built
- [ ] Checkpoint F2: /ops correct, definitions match the evals, no added wait
- [ ] Task 22: Replays and hosting. Replays recorded and checked against the agent version; container setup ready. Hosting waits for Vikrant's choice of host
- [x] Task 23: Final evals and write-up: `docs/v2-results.md`, README, business case, responsible AI, and the v2 hand-check (Vikrant agreed with 10 of 10)
- [ ] Checkpoint G: v2 release gates
