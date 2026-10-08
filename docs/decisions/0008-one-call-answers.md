# 0008: One model call per answer

_8 Oct 2026. Status: accepted (Vikrant asked for it: "keep the quality but target answering in one model call than 3")._

**Problem:** A reply took about 13 to 16 seconds at the median against an 8-second target. Each model call takes about 4 to 5 seconds, and the tool loop needs about three per turn: one to ask for the data, one to ask for help passages, and one to write the answer. Lowering the thinking level was faster but dropped citations, so quality would suffer ([Task 18 notes](../../tasks/todo.md)).

**Decision:** Code, not the model, gathers what an answer needs, and the model writes the answer in **one call**.

1. **Preload in code, every turn.** Before the model is called, code runs the read-only data tools through the same `merchant_data` source the tools use:
   - `list_account_issues`
   - `list_aggregate_product_statuses`
   - `list_products`
   - `get_automatic_improvements`
   - `get_product_by_name` for the product the panel was opened from

   It then picks the help docs:
   - every doc whose issue codes match an issue in the store (an issue-code-to-doc map)
   - the automation docs for automation-solvable issues
   - the policy doc behind an account issue
   - the passages `search_help_docs` finds for the merchant's message
2. **One structured call.** The model gets the instructions, the preloaded context, the conversation so far and the new message. It returns the reply, and optionally the fields of a handoff case.
3. **Code makes the case.** If the model asks for a handoff, code calls `create_handoff_case` (which adds the account issues, affected products and automation state from the data) and puts the case number into the reply.
4. **Recorded like tool calls.** Every preload and the handoff are recorded in the turn as tool calls marked as made by code. So the evals' tool, re-check and no-invention checks, the trace view and the event store all keep working.
5. **Fallback.** If the pre-step can't connect a free-text question to the store or to a help doc (no product, issue or account word matched, and help search found nothing), the turn uses the existing tool loop. It's recorded as a fallback, so the fallback rate is visible.
6. **Follow-ups reload the data,** so a "done, I fixed it" turn is checked against fresh data in the same single call.

**Kept:**
- **Read-only access.** The preload runs the read tools only. The model can't call any tool on the one-call path, so write calls stay at zero by construction.
- **Graceful failure.** If a preload call fails, the context says it couldn't be loaded, and the instructions say not to fill the gap. The `data_tool_failure` cases still test it.
- **Injection resistance.** Product titles and account issue details are in the context as data, marked as untrusted. Product descriptions and product types aren't included at all, because no answer needs them. That's a deliberate reduction in untrusted text, and it means the description and product-type injection cases now test that minimisation rather than the model's resistance (logged in `evals/CHANGELOG.md`).
- **Case-preview fidelity.** The preview is still the saved case.

**Measured:** model calls per turn, and the share of turns on the fallback path, are recorded per turn. They're reported in the eval scorecard and on /ops, through the shared metrics module.

**Consequences:**
- **Some checks become true by design.** "Re-checked after the last fix" and "called `get_automatic_improvements` first" now hold because code always does them. That's logged in `evals/CHANGELOG.md` as a change made after seeing results, so the scores aren't read as the model's own judgement.
- **More input tokens per call, fewer calls.** The cost per conversation is tracked against the $0.03 target.

**Model:** the agent moves to `gemini-3.5-flash-lite` (Vikrant's choice: a balance of cost and quality, judged once, with no comparison runs). It's confirmed available to our key, at $0.30 per million input tokens and $2.50 per million output, against $0.75 and $3.75 for `gemini-3.6-flash` (pricing page, 7 Oct 2026). The grader stays on `gemini-3.6-flash`, so scores stay comparable. If Flash-Lite misses a quality target or any hard gate on the one-call design, the agent goes back to Flash, with no tuning around it.

**Result (8 Oct):** Flash-Lite was run through the full E2 once on the one-call design (`20261008-162054` to `20261008-164932`). It was fast and cheap: one call per turn, a median of 1.6 to 2.2 s and about $0.002 per conversation. But it missed targets, including a hard gate:

| Measure | Main run 1 | Main run 2 | Target |
|---|---|---|---|
| Injection resistance (hard gate) | 71% | 86% | 100% |
| Triage accuracy | 25% | 25% | 90% |
| Handoff precision | 80% | 83% | 90% |
| Handoff recall | 91% | 91% | 95% |
| Automation routing | 87% | 93% | 95% |

The misses were:
- handing off when a plain fix or a question was all that was needed
- missing the no-doc handoffs
- listing warnings before disapprovals
- in `injection-in-account-issue`, repeating the planted "suspension is lifted" text

Wrong advice was 0% and case completeness 100%, and the held-out sets did better: the v1 held-out set passed 7 of 7 twice. **So the agent goes back to `gemini-3.6-flash`, keeping the one-call design**, with no tuning around the misses, as agreed.

**E2 on Flash with the one-call design (8 Oct, `20261008-165526` to `20261008-180539`):** each set was run twice.

| | Main run 1 | Main run 2 | v1 held-out (both runs) | v2 held-out (both runs) |
|---|---|---|---|---|
| Cases passed | 68 of 69 | 68 of 69 | 7 of 7 | 8 of 8 |
| Median latency | 13.4 s | 10.7 s | 8.7 and 10.2 s | 11.6 and 10.6 s |
| Cost per conversation | $0.0135 | $0.0135 | about $0.012 | about $0.012 |

- **Model calls per turn:** 1.00 in every run, with 2% fallback on the main set.
- **Targets and gates:** every quality target and hard gate was met, except triage on the main set (75%). In both runs `triage-suspended-then-products` handed off on the suspension without summarising the product issues.
- **Latency:** still above 8 s. The single call does all the thinking, about 2,000 output tokens per turn.

**Not chosen:**
- **Lower thinking level:** faster, but it dropped citations.
- **Parallel tool calls in the loop:** measured with no gain (2.95 calls per turn instead of 3.15).
