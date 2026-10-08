# v2 results

_8 Oct 2026. Release candidate: agent version `60e5bc0b3211`.
- **Agent:** `gemini-3.6-flash`, one model call per answer ([ADR 0008](decisions/0008-one-call-answers.md)), at thinking level LOW.
- **Grader:** `gemini-3.6-flash`, unchanged from v1._

v2 widened the eval suite from 47 to 84 cases:
- **Main set:** 69 cases, up from 40.
- **v1 held-out set:** the same 7 cases.
- **v2 held-out set:** 8 new cases, written blind before any v2 prompt change.

## Scorecard (release candidate)

| Metric | Target | Main | v1 held-out | v2 held-out |
|---|---|---|---|---|
| Cases passing every check | | 68 of 69 (see note 1) | 7 of 7 | 8 of 8 |
| Resolution rate | 80% or higher | **100%** | **100%** | **100%** |
| Wrong advice rate (AI graded) | under 5% | **0%** | **0%** | **0%** |
| Handoff precision | 90% or higher | **100%** | **100%** | **100%** |
| Handoff recall | 95% or higher | **100%** | **100%** | **100%** |
| Case completeness (AI graded) | 90% or higher | **100%** | **100%** | **100%** |
| Automation-routing accuracy | 95% or higher | 93% (note 1) | not measured | **100%** |
| Triage accuracy | 90% or higher | **100%** | not measured | **100%** |
| Tool-call correctness | 95% or higher | **100%** | not measured | **100%** |
| Write calls (hard gate) | 0 | **0** | **0** | **0** |
| Graceful-failure rate (hard gate) | 100% | **100%** | not measured | **100%** |
| Injection resistance (hard gate) | 100% | **100%** | not measured | **100%** |
| Context carryover | 95% or higher | **100%** | not measured | **100%** |
| Case-preview fidelity (hard gate) | 100% | **100%** | not measured | **100%** |
| Model calls per turn | about 1 | **1.00** (2% fall back to the tool loop) | 1.00 | 1.00 |
| Latency per turn, p50 and p95 | 8 s and 20 s | **5.1 s and 8.3 s** | 4.7 s and 6.5 s | 5.4 s and 7.2 s |
| Cost per conversation | $0.03 or less | **$0.0074** | $0.0065 | $0.0053 |
| Uniquely agent-resolved rate | tracked | 82% | 100% | 100% |

Raw results:
- `evals/results/20261008-181506-gemini-3.6-flash.*` (main)
- `20261008-183256-*-heldout.*` (v1 held-out)
- `20261008-183448-*-heldout_v2.*` (v2 held-out)

**Notes and limits:**
1. **The one main-set failure is a suspected false alarm.** In `auto-irrelevant-barcodes`, the agent said "No automatic setting can fill in missing barcodes for you". That's correct, but the forbidden pattern doesn't allow for the negation. Vikrant chose to leave the check unchanged, so the result stands as scored ([evals/CHANGELOG.md](../evals/CHANGELOG.md)).
2. **One main run, not two.** Vikrant asked to skip the second main run of this version. The previous version (one call, normal thinking) was run twice on every set, and passed 68 of 69 and 68 of 69 on the main set.
3. **Some checks hold by design.** Code reloads the data every turn and always reads the automation settings. So "re-checked after the last fix" and "checked the automation settings first" measure the design, not the model's judgement.
4. **Two injection cases test minimisation.** Product descriptions and product types never reach the model, so those two cases test that the planted text is kept out, not that the model resists it.
5. **Scripted, simulated data.** These are scripted conversations on simulated stores, not real traffic.

## How we got here (main set)

| Main set | Baseline (Task 17) | Tool loop (E2 attempt 2) | Flash-Lite, one call | One call, normal thinking | **One call, thinking LOW** |
|---|---|---|---|---|---|
| Cases passing every check | 44 of 69 | 69 of 69 | 57 and 59 of 69 | 68 and 68 of 69 | **68 of 69** |
| Wrong advice rate | 12% | 0% | 0% | 0% and 1% | **0%** |
| Case completeness | 91% | 100% | 100% | 100% | **100%** |
| Automation routing | 27% | 100% | 87% and 93% | 100% | 93% (note 1) |
| Triage | 75% | 100% | 25% | 75% | **100%** |
| Injection resistance (gate) | 86% | 100% | **71% and 86%** | 100% | **100%** |
| Model calls per turn | about 3.2 | about 3.2 | 1.00 | 1.00 | **1.00** |
| Latency p50 | 12.1 s | 15.5 s | 1.6 and 2.0 s | 13.4 and 10.7 s | **5.1 s** |
| Cost per conversation | $0.022 | $0.026 | $0.002 | $0.0135 | **$0.0074** |

What changed, in order:
1. **Agent v2 behaviour (Task 18).** Automation routing, triage order, graceful failure, entry context, and handoff cases that record account issues, affected products and automation state from the data. E2 attempt 1 then missed wrong advice and case completeness. Grounding rules for "what happens after a fix" and appeals, plus product ids recorded in cases, fixed both.
2. **One call per answer (ADR 0008, Vikrant's request).** Code loads the store data and the help docs, and the model answers once.
3. **Flash-Lite was tried and rejected.** It was very fast and cheap, but it missed injection resistance (a hard gate), triage, and handoff precision and recall. Per the agreement, the agent went back to Flash without tuning around the misses.
4. **Thinking level LOW, and a suspension summary rule.** Both were chosen by Vikrant after seeing results, and both are logged in [evals/CHANGELOG.md](../evals/CHANGELOG.md). Latency met its target for the first time, and triage went to 100%.

## Disclosure

- **Every change after seeing results is logged.** Expectation changes, scorer fixes and agent changes are all in [evals/CHANGELOG.md](../evals/CHANGELOG.md), with the reply or result that led to each. That includes the runs that were stopped and the false alarms left unchanged.
- **Grader hand-check.** A new 10-item sample from three v2 runs is in [evals/hand-check-v2.md](../evals/hand-check-v2.md) for Vikrant to review. Its agreement rate will be added here when it's done.
- **Spend.** All evals on 8 Oct cost $20.07: $12.95 for the agent and $7.12 for grading. The SPEC estimated about $8; the extra came from the two agent redesigns and their full re-runs.
