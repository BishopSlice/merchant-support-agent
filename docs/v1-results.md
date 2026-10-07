# v1 results

_Frozen 7 Oct 2026. Final agent at commit acd5209 (no agent changes after it). Model `gemini-3.6-flash` for the agent and the grader._

These are the headline numbers for the finished agent. The main set (40 cases) and the held-out set (7 cases) were each run twice, and every conversation was graded.

## Scorecard

| PRD metric | Target | Main, run 1 | Main, run 2 | Held-out, run 1 | Held-out, run 2 |
|---|---|---|---|---|---|
| Resolution rate | 80% or higher | **100%** (17 of 17) | **100%** (17 of 17) | **100%** (3 of 3) | **100%** (3 of 3) |
| Wrong advice rate (AI graded) | under 5% | **3%** (2 of 63 replies) | **0%** (0 of 63) | **0%** (0 of 10) | **0%** (0 of 10) |
| Handoff precision | 90% or higher | **100%** (16 of 16) | **100%** (16 of 16) | **100%** (4 of 4) | **100%** (4 of 4) |
| Handoff recall | 95% or higher | **100%** (16 of 16) | **100%** (16 of 16) | **100%** (4 of 4) | **100%** (4 of 4) |
| Case completeness (AI graded) | 90% or higher | **100%** (16 of 16) | **100%** (16 of 16) | **100%** (4 of 4) | **100%** (4 of 4) |
| Cost per conversation | tracked | $0.020 | $0.021 | $0.019 | $0.018 |

- Every case passed every rule check in all four runs: 40 of 40 twice and 7 of 7 twice.
- Every handoff gave the expected reason.
- All 94 conversations were graded; the grader wasn't blocked on any of them this time.

Raw results: `evals/results/20261007-152441-gemini-3.6-flash.*`, `20261007-154610-*` (main), and `20261007-152441-*-heldout.*`, `20261007-152959-*-heldout.*` (held-out).

## How we got here

| Main set | Checkpoint D (first full runs) | v1 |
|---|---|---|
| Resolution rate | 94%, 94% | 100%, 100% |
| Wrong advice rate | 3%, **7%** | 3%, 0% |
| Handoff precision and recall | 100% | 100% |
| Case completeness | 93%, **87%** | 100%, 100% |
| Cases passing every check | 38 and 37 of 40 | 40 and 40 of 40 |

Between Checkpoint D and v1 (see `docs/checkpoint-d.md` and `docs/task11-before-after.md`):
1. **Handoff cases record the merchant's own reasons** in a new field, and cite the policy doc.
2. **Lines that stated our handoff process as Google policy were removed** from the agent's instructions. Most of the unsupported advice came from them.
3. **The agent names every product in an issue group**, not just the first.
4. **A question about how to get a restricted product approved isn't treated as an appeal.** This fixed an over-escalation that change 1 introduced.
5. **Suspension replies cite the policy doc, and out-of-scope redirects don't name menus** in other Google products.

The held-out set went from 67% resolution, 10% wrong advice and 50% completeness on the unchanged agent to 100%, 0% and 100%.

## The two remaining flags

Both are in main run 1, and both are fair, minor findings:
- **`no-handoff-contact-support`:** "No, you do not need to contact Google support… this disapproval will be resolved." The advice to fix the data is supported, but the promise that the disapproval *will* be resolved isn't stated by any help page.
- **`off-topic-shopify-steps`:** "add the GTIN value to the barcode field for these products in your store platform." Telling the merchant to enter the GTIN is supported; "the barcode field" leans toward platform-specific detail.

Neither appeared in run 2. That fits the run-to-run variation seen throughout: at these sample sizes, one reply moves the wrong-advice rate by about 1.5 points on the main set.

## Cost

| | Agent | AI grader | Total |
|---|---|---|---|
| Main, two runs (80 conversations) | $1.63 | $0.54 | $2.17 |
| Held-out, two runs (14 conversations) | $0.26 | $0.09 | $0.35 |
| **v1 total** | **$1.89** | **$0.63** | **$2.53** |

The production cost is the agent column, **about $0.02 per conversation**. That's at Google's published 2026 price for `gemini-3.6-flash` ($0.75 per million input tokens, $3.75 per million output tokens). Google doubles these prices from 1 January 2027. All recorded eval runs in the project, including every earlier run, cost $9.76.

## Read these numbers with care

- **Small samples.** There are 47 cases and 16 handoffs in the main set. 100% on 16 handoffs is strong evidence the handoff rules work on these scenarios, not proof of a 100% rate in production.
- **Same author.** I wrote the agent, the cases and the held-out cases. The held-out set was committed before the Task 11 changes and never edited afterwards. It guards against fitting the main set's wording, not against blind spots both share.
- **Patterns loosened after seeing results.** Five eval patterns were changed after seeing results, because they failed correct replies. Each change has a regression test using the real reply and is listed in the reports. The last change came before the v1 runs.
- **The AI grader is checked, but lightly.** A person agreed with 10 of 10 sampled verdicts (`evals/hand-check.md`). The grader still varies a little between passes.
- **Simulated stores.** The stores, and the help pages they rely on, are simulated or paraphrased. Real merchant traffic would have a different mix of problems.

Reproduce: `uv run python -m evals.run` (main) and `uv run python -m evals.run --set heldout`.
