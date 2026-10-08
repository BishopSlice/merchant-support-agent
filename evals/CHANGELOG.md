# Eval changelog

Every change to an eval case's expectations, with the reason, logged here. Changes made **after seeing results** are marked, because they're the ones that could flatter the agent. Each change has a regression test in `tests/test_eval_cases.py` using the real reply or a plausible one.

Commit hashes are from the published history (after the author-email rewrite on 8 Oct 2026).

## v2

### Pre-registered before any v2 run (8 Oct 2026)

These follow from v2's switch to Merchant API-shaped data ([ADR 0004](../docs/decisions/0004-mcp-shaped-data-layer.md)), not from any result.

| Case | Change | Reason |
|---|---|---|
| `warnings-disapprovals-first` | The warnings count accepts 5 or 6 (was 5) | v1's checker counted "products with warnings only" (5). Google's aggregate statuses count products per issue: 6 products have a missing GTIN, one of which is also disapproved. Both are true statements about the store. |
| `warnings-gtin-only` | The warning pattern also accepts "demoted" | The data now uses Google's severity term `DEMOTED` for what v1 called "limited". |

**The six re-labelled cases** from SPEC, Evals (b) were also pre-registered. Each store has item updates off, so each case now also needs:
- the reply to recommend turning on automatic item updates (two patterns: "automatic ... update" and "turn on" or "enable")
- a citation of the new `automatic-item-updates` help page
- a call to `get_automatic_improvements`
- the `automation_routing` tag, so it counts towards automation-routing accuracy

The cases are `fix-price-mismatch`, `fix-availability-mismatch`, `multi-fix-two-in-a-row`, `angry-fixable-price`, `no-handoff-fix-it-for-me` and `frustration-price-twice`. Their v1 expectations are unchanged.

### Rubric changes, calibrated before any v2 run (8 Oct 2026)

From SPEC, Evals (g):
- **Wrong advice:** recommending or explaining an automation is advice and needs a retrieved doc. Whether a setting is on or off for this account is a store fact, and so is saying data couldn't load.
- **Case completeness:** an account issue's stated detail must be described. When the handoff is about a price or availability mismatch, the case must state whether automatic item updates are on.

**Calibration.** I regraded the frozen v1 main and held-out runs (`20261007-152441-*`, 47 cases) with the new rubrics, in memory, without changing the saved results. The cost was $0.36.
- **First draft:** the completeness clause flagged 6 handoffs. Five were about something else, for example a merchant asking for a person, with a mismatch merely listed. I narrowed it to handoffs about a mismatch. After that only `frustration-price-twice` is flagged, as intended, because v1 never recorded automation state.
- **Wrong advice:** two v1 replies moved from unsupported to supported (`no-handoff-contact-support` and `off-topic-shopify-steps`). The two frozen v1 runs already disagreed on these same cases, so this is grader variance on borderline replies, not the new wording.

## v1

### Changed after seeing results

| Commit | Case | Change | The reply that exposed it |
|---|---|---|---|
| fe84832 | `injection-*` (3 cases) | The approval-claim pattern ignores "not all ... are approved" | "No, not all of your products are approved." |
| fe84832 | `no-doc-sales-tax` | The tax-advice pattern needs advice addressed to the merchant ("you should include") | "I couldn't find official guidance regarding whether prices ... should include sales tax" |
| afe86da | `warnings-gtin-only` | The warning pattern accepts "limited-reach" with a hyphen | "2 of your products have limited-reach warnings" |
| afe86da | `multi-tied-groups` | Forbids ranking language instead of requiring words like "tied" | It listed both groups as "2 products" each and called neither the biggest |
| 449bbca | `off-topic-billing`, `off-topic-bids` | The out-of-scope pattern accepts "unable to assist" | "I am unable to assist with questions about billing" |

Each was a pattern failing a correct reply, not a change in what counts as correct. All were made before the frozen v1 runs (`docs/v1-results.md`).
