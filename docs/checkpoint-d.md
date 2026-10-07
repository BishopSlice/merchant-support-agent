# Checkpoint D: first full eval runs

_7 Oct 2026. Model `gemini-3.6-flash` for both the agent and the grader. 40 cases, run twice._

Runs, each with a JSON file and a markdown scorecard:
- Run 1: `evals/results/20261007-111200-gemini-3.6-flash.md`
- Run 2: `evals/results/20261007-115020-gemini-3.6-flash.md`

Reproduce with `uv run python -m evals.run`. Compare two runs with `uv run python -m evals.compare RUN1.json RUN2.json`.

## Scorecard against the PRD

| Metric | Run 1 | Run 2 | PRD target | Verdict |
|---|---|---|---|---|
| Resolution rate | 94% (16 of 17) | 94% (16 of 17) | 80% or higher | met in both |
| Wrong advice rate (AI graded) | 3% (2 of 60 replies) | 7% (4 of 60 replies) | under 5% | **missed in run 2** |
| Handoff precision | 100% (15 of 15) | 100% (15 of 15) | 90% or higher | met in both |
| Handoff recall | 100% (15 of 15) | 100% (15 of 15) | 95% or higher | met in both |
| Case completeness (AI graded) | 93% (14 of 15) | 87% (13 of 15) | 90% or higher | **missed in run 2** |
| Cost per case (agent) | $0.0182 | $0.0179 | tracked | |

Also:
- Every handoff gave the expected reason in both runs (15 of 15).
- 38 of 40 cases passed every rule check in run 1, and 37 of 40 in run 2.

In both runs the grader could not grade one case (`frustration-price-twice`), because Gemini blocked the grading prompt as `PROHIBITED_CONTENT`. Nothing in that prompt is objectionable, and this kind of block can't be turned off. The case is left out of the two AI-graded rates, and each scorecard names it.

## Worst categories

| Category | Run 1 | Run 2 | Failing cases |
|---|---|---|---|
| handoff_appeal | 2 of 4 | 2 of 4 | `appeal-cbd-after-diagnosis` (both runs), `appeal-records-merchant-reason` (run 2) |
| easy_fix | 4 of 5 | 4 of 5 | `fix-invalid-image` (both runs) |
| Every other category | all passed | all passed | |

What goes wrong:

1. **Appeal cases leave out the merchant's argument.** When the merchant explains why they disagree ("it's just a candle", "it only has trace amounts of CBD"), the case says only "merchant wants to appeal". The case also cites the request-review doc but not the CBD doc. Both the rule checks and the AI grader catch this, and it causes every completeness miss.
2. **The agent's own instructions state rules that no help doc backs.** Five of the six wrong-advice flags across both runs are sentences such as:
   - "Only a human specialist can handle policy appeals"
   - "Account suspensions must be reviewed by a human specialist"
   - "No products can show while your account is suspended"

   These come straight from the handoff section of `src/merchant_agent/agent.py`, which presents our handoff process as if it were Google's policy. The sixth flag is a vague timing ("it may take a short time to process").
3. **Image fixes are explained one product at a time.** In `fix-invalid-image` the agent explained only the first broken image. It never mentioned the second product's placeholder image, and the merchant then said everything was fixed.

## Run-to-run variance

- The rule-based metrics (resolution, handoff precision and recall, reason accuracy) were identical across the two runs.
- Only 1 of 40 cases changed outcome: `appeal-records-merchant-reason` passed in run 1 and failed in run 2. That's the appeal weakness above showing up some of the time rather than every time.
- The AI-graded metrics moved more: wrong advice 2 vs 4 flagged replies, completeness 14 vs 13 of 15. At these sample sizes, one reply or one case moves a rate by 2 to 7 points. Both runs sit near the targets, so one run isn't enough to say whether a target is met.
- The grader also varies on its own at temperature 0. The same suspension reply was graded "supported" on one grading pass and "unsupported" on another during calibration.

## Cost

| | Run 1 | Run 2 |
|---|---|---|
| Agent (40 conversations) | $0.727 | $0.715 |
| AI grader | $0.268 | $0.271 |
| **Total** | **$0.995** | **$0.986** |

Both full runs together cost **$1.98**. The smoke run and grader calibration added about $0.12. Prices are Google's published paid-tier rates for 2026 ($0.75 per 1M input tokens, $3.75 per 1M output tokens). They double from 1 January 2027.

## Honesty notes on the measurement

- **I fixed four of my own eval patterns after seeing results, because they failed correct replies.** For example, "No, *not* all of your products are approved" matched the approval-claim pattern, and "limited-reach" with a hyphen didn't match "limited reach". Each fix has a regression test that uses the exact reply. Both runs were re-scored from their saved transcripts, with no agent rerun. Before the fixes, run 1 showed 4 failures, not 2.
- **I calibrated the completeness rubric before the full runs.** I added a worked example after the grader rated an incomplete appeal case as complete.
- **Both runs were resumed, not run in one go.** Run 1 was resumed after the Mac went offline mid-run (which is why model calls now time out after 2 minutes). Both runs were resumed after the grader crashed on the blocked prompt (it now retries and records the failure instead).
- **Hand-check:** Vikrant reviewed 10 graded items from run 1 (7 passes, 3 fails) and agreed with all 10 verdicts (`evals/hand-check.md`). That supports trusting the AI-graded numbers, though a sample of 10 is small.

## Recommendation for Task 11

**Fix the handoff section of the agent's instructions first.** One change addresses both metrics that missed in run 2:

1. **Record the merchant's own reasons.** Tell the agent to put what the merchant said in the case: their argument and any details they gave. It should cite every help doc that applies, including the policy doc (CBD) and not only the request-review doc. This targets case completeness and both appeal failures.
2. **Stop presenting our handoff process as Google's policy.** The agent should say "this needs a specialist, so I've passed it on" rather than "only a human specialist can handle appeals". It should state facts about suspensions only when a retrieved doc supports them. This targets 5 of the 6 wrong-advice flags.

Then rerun the evals twice and compare against these two runs.

Second priority: tell the agent to name every product in an issue group when explaining it (the image case).
