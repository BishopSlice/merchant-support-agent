# Task 11: before and after

_7 Oct 2026. Model `gemini-3.6-flash` for the agent and the grader._

## What changed

Checkpoint D (`docs/checkpoint-d.md`) traced the worst failures to the handoff section of the agent's instructions, plus one explanation habit. Four commits addressed them:

1. **Cases carry the merchant's reasons** (c258a83). Cases have a new `merchant_reasons` field: every reason or detail the merchant gave, in their own words. The specialist inbox shows it right after what the merchant wants.
2. **Handoff rules rewritten** (1f15007).
   - Cases must cite every relevant doc, including the policy doc behind the issue.
   - For an appeal, the agent searches for the policy and explains it with a citation first.
   - Two sentences that no help doc supports are gone ("no products can show until it is resolved", "only a human can decide an appeal"). The agent presents a handoff as how this service works, never as a Google rule.
3. **Every product in an issue group is named** (441637f). When the agent explains an issue, it lists every affected product and what's wrong with each.
4. **The prompt no longer quotes eval cases** (3226cc4). My review of the diff found that commit 2's example merchant reasons ("only has trace amounts of CBD", "other shops sell the same product") echoed two eval cases, one of them held-out. They were replaced with wording no case uses, and a test now fails if any five-word phrase from an eval merchant message appears in the instructions. **The "after" numbers below come from runs made after this commit.**

## Guarding against overfitting

Before touching the instructions, I wrote 7 held-out cases on 4 new stores, with new merchant wording, and committed them first (b2dfa5d). They cover:
- appeals with different arguments (a hemp cosmetic oil, "other shops sell these")
- a second suspension reason, and a merchant asking for a date
- issue groups with 3 and 2 products
- an angry merchant with several plain fixes who must not be handed off

I ran them twice on the unchanged agent as a baseline (819b97e). They were not edited afterwards.

## Results

Before = the unchanged agent, run twice (the Checkpoint D runs for the main set, plus the held-out baseline). After = the agent with all four commits.
- **Main set after:** one full run of all 40 cases, plus a second run of the four appeal cases (the category most affected).
- **Held-out set after:** two full runs.

### Main set (40 cases)

| Metric | Before (run 1 / run 2) | After (clean prompt) | Target |
|---|---|---|---|
| Resolution rate | 94% / 94% (16 of 17) | 94% (16 of 17) | 80% or higher |
| Wrong advice (AI graded) | 3% / 7% (2 and 4 of 60 replies) | **2%** (1 of 61) | under 5% |
| Handoff precision | 100% / 100% (16 of 16) | **94%** (16 of 17) | 90% or higher |
| Handoff recall | 100% / 100% (16 of 16) | 100% (16 of 16) | 95% or higher |
| Case completeness (AI graded) | 93% / 87% (14 and 13 of 15) | **100%** (17 of 17) | 90% or higher |
| Cases passing every rule check | 38 / 37 of 40 | 38 of 40 | |
| Cost per case (agent) | $0.018 / $0.018 | $0.019 | tracked |

Main appeal cases on the clean prompt, second run: all 4 pass. That's 3 of 3 handoffs, with the merchant's reasons recorded and the CBD doc cited, and no wrong advice in 6 replies.

### Held-out set (7 cases)

| Metric | Before (run 1 / run 2) | After (run 1 / run 2, clean prompt) | Target |
|---|---|---|---|
| Resolution rate | 67% / 67% (2 of 3) | **100% / 100%** (3 of 3) | 80% or higher |
| Wrong advice (AI graded) | 10% / 10% (1 of 10 replies) | **0% / 0%** | under 5% |
| Handoff precision | 100% / 100% (4 of 4) | 100% / 100% (4 of 4) | 90% or higher |
| Handoff recall | 100% / 100% (4 of 4) | 100% / 100% (4 of 4) | 95% or higher |
| Case completeness (AI graded) | 50% / 50% (2 of 4) | **100% / 100%** (4 of 4) | 90% or higher |
| Cases passing every rule check | 4 / 4 of 7 | 7 / 7 of 7 | |

### For reference: runs with the first version of the fixes

Before commit 4 removed the echoing examples, I made two full main runs and two held-out runs. All four met every target: main resolution 100%, wrong advice 0% and 2%, precision and recall 100%, completeness 100%; held-out 100% everywhere with 0% wrong advice. They're saved in `evals/results/` (from 20261007-124751 to 20261007-132139). They are not used as the "after" numbers, because the prompt echoed two of the cases they measure. The clean-prompt runs above came out very close, which suggests the echo wasn't driving the improvement.

## Cases that flipped (main set, before vs clean after)

**Fixed:**
- `appeal-cbd-after-diagnosis`: failed in both before-runs, passes in both clean appeal runs.
- `appeal-records-merchant-reason`: failed in before-run 2, passes in both clean appeal runs.
- `fix-invalid-image`: failed in both before-runs, passes. All products in the group are now named.
- On the held-out set: `heldout-appeal-hemp-oil`, `heldout-appeal-other-shops` and `heldout-angry-many-images` failed in both baseline runs and pass in both clean runs. The two appeal cases record the merchant's own arguments, for example "Says it is a cosmetic oil for the skin" and "Says it is sold legally in every shop near them", and cite the CBD policy doc.

**Regressed:**
- **`multi-cbd-edit-not-a-fix`: a must-not-handoff case was handed off.** The merchant asked "Can I just edit the CBD candle's description to get it approved?" The agent explained the policy correctly, then opened a `policy_appeal` case although the merchant never asked to appeal or said they disagreed. This case passed in all four earlier runs, both before and with the first version of the fixes. So it happened in 1 of 3 post-fix runs. The likely cause is that the appeal step got more prominent in the rewrite. It's the only drop in handoff precision (94%, still above the 90% target), and the one over-escalation in this task.
- **`off-topic-billing`: this is my pattern, not the agent.** The agent said "I am unable to assist with questions about billing", which my out-of-scope pattern doesn't list. I've widened four patterns after seeing results already, so I left this one alone and am reporting it.

**Other must-not-handoff cases:** no regressions. The three `no_handoff_data_fix` cases, the angry merchants, the off-topic asks, the injection attempts and the held-out angry case were all handled without a handoff.

**Remaining wrong-advice flag** (main clean run): on `suspended-why-not-showing`, the agent said listings must clearly show returns policies and contact information. The misrepresentation doc talks about payment terms, shipping costs and post-purchase terms, so "returns policy" is the agent's own reading. The grader flagged it as unsupported. It's a fair, borderline flag.

## Cost

| | Agent | Grader | Total |
|---|---|---|---|
| Held-out baseline, two runs | $0.235 | $0.109 | $0.34 |
| First-version after-runs (2 main, 2 held-out) | $1.879 | $0.621 | $2.50 |
| Clean after-runs (1 main, 1 appeal, 2 held-out) | $1.160 | $0.407 | $1.57 |
| **Task 11 total** | | | **$4.41** |

Cost per case rose about 7%, from $0.018 to $0.019. Appeals now search for and explain the policy before handing off, and explanations name every product.

## Do the held-out results confirm the improvement?

Yes, for the two failures the fixes targeted, with three caveats.

The held-out cases were committed before any prompt change and not edited afterwards. Their stores and arguments appear nowhere in the main set. On the clean prompt, both held-out runs fixed every failure the unchanged agent showed:
- appeal cases dropping the merchant's argument
- the angry merchant hearing about 1 of 3 products
- the one unsupported claim

On the main set, case completeness went from 87 to 93% up to 100%, and wrong advice from 3 to 7% down to 2%.

**Caveat 1: the samples are small.** There are 7 held-out cases and one clean main run. On the main set, the AI-graded metrics moved by up to 6 points between identical runs at Checkpoint D. Read the after-results as "comfortably inside the targets", not as exact rates.

**Caveat 2: I wrote both the fixes and the held-out cases.** They test the same kinds of failure with new content, which guards against fitting the main set's wording, but not against blind spots both sets share. A set written by someone else would be a stronger test.

**Caveat 3: the fix introduced a new failure.** The rewrite made appeals more prominent, and in one run that tipped a merchant's how-do-I-get-approved question into an unwanted appeal handoff. Precision held above target, but this is the first over-escalation the evals have seen.

## Still open, in priority order

1. **Over-escalation on approval questions.** Add one line: a question about how to get a restricted product approved is not an appeal. Explain the policy and offer an appeal; hand off only if the merchant says they want one. Rerun the appeal and multi-issue categories at least twice.
2. **Suspension replies sometimes skip the policy citation,** and once paraphrased beyond the doc (`suspended-why-not-showing`).
3. **The out-of-scope pattern misses "unable to assist"** (eval fix, `off-topic-billing`). The billing redirect also adds a Google Ads navigation hint from memory.
4. **The grader is blocked on some prompts.** Gemini blocks some grading prompts as `PROHIBITED_CONTENT` (`frustration-price-twice` in every run, `fix-price-mismatch` once). Those cases are left out of the AI-graded rates, and each scorecard names them.

PRD and SPEC need no changes. The PRD's list of what a specialist sees in a case gains the merchant's reasons, which adds to the list and doesn't contradict it.
