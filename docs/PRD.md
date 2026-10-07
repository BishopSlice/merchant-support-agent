# PRD: Merchant Support Agent

_Status: draft for review, 7 Oct 2026. Owner: Vikrant Narayan._

## 1. Problem

Small online stores sell through Google Shopping by uploading a product feed (a spreadsheet of their products) to Merchant Center. When a product breaks a rule, Google "disapproves" it and it stops showing in ads. The store owner usually finds out because sales drop.

Fixing it is hard for them today:
- The error messages are short and technical ("Missing value [gtin]").
- The rules live across many help pages.
- A single feed can have several different problems at once.
- Some problems (policy appeals, account suspensions) need a human at Google, and when the merchant finally reaches one, they explain everything from scratch.

For Google, every one of these cases that reaches a human specialist costs money, and every hour a product stays disapproved is lost ad revenue.

## 2. Users

| User | What they want |
|---|---|
| **Merchant** (primary): owner of a small online store, not technical | "Tell me what's wrong, in plain words, and exactly what to change." |
| **Support specialist** (secondary): human at Google who handles escalated cases | "When a case reaches me, give me the full picture so I don't re-ask the merchant." |

## 3. Goals and non-goals

**Goals**
1. Diagnose every disapproved or limited product in a merchant's feed and group them by root cause.
2. Explain each issue in plain language, grounded in the official help docs (no made-up rules).
3. Walk the merchant through fixes one issue at a time, most impactful first.
4. Hand off to a human, with a structured case summary, whenever the agent should not act alone.

**Non-goals (for v1)**
- Editing the merchant's real feed or calling real Google APIs. We use a simulated store.
- Handling billing, ad performance or bidding questions (these get politely redirected).
- Languages other than English.

## 4. User journey

1. Merchant: "Half my products got disapproved yesterday, what happened?"
2. Agent runs the feed check and replies with a short summary: "12 of 30 products are disapproved for 4 reasons. The biggest one is prices that don't match your website, on 5 items. Another 6 products have a warning that limits their reach: missing product barcode numbers (GTINs)."
3. Agent explains the top issue, cites the help page, and gives the exact fix.
4. Merchant asks follow-ups or says "done". Agent re-checks and moves to the next issue.
5. If the merchant hits something the agent must not handle, the agent says so, creates a case, and tells the merchant what happens next.
6. The specialist opens the case in their inbox and sees: the store, the issues found, what was already tried, what the merchant wants, and the agent's suggested next step.

## 5. What the agent can do (tools)

| Tool | What it does |
|---|---|
| `check_feed` | Runs rule checks over the store's feed and returns issues grouped by type |
| `search_help_docs` | Finds the relevant help page passages for an issue or question |
| `create_handoff_case` | Saves a structured case for a human specialist |

## 6. Handoff rules

The agent **must** hand off when:
- The account is suspended or has a policy strike.
- A product is disapproved for a restricted or prohibited content policy and the merchant wants to appeal.
- The merchant asks for a human, or is clearly frustrated after two failed attempts.
- The agent can't find a help doc that supports its answer.

The agent **must not** hand off when the issue is a plain data fix the merchant can make themselves (missing GTIN, price mismatch, bad image link, and so on).

## 7. Success metrics

| Metric | What it means | v1 target |
|---|---|---|
| Resolution rate | % of fixable cases the agent fully resolves | 80% or higher |
| Wrong advice rate | % of answers that state a rule not supported by the docs | under 5% |
| Handoff precision | Of the cases it handed off, % that truly needed a human | 90% or higher |
| Handoff recall | Of the cases that needed a human, % it handed off | 95% or higher (missing one is worse than an extra one) |
| Case completeness | Specialist wouldn't need to re-ask the merchant anything (graded with a rubric) | 90% or higher |
| Cost per case | Average model cost for a full conversation | tracked, no target yet |

## 8. Risks and responsible AI

| Risk | Why it matters | Mitigation |
|---|---|---|
| Confident wrong policy advice | Merchant makes a bad change or loses trust | Answers must cite a help doc; "not sure" triggers handoff |
| Agent tries to resolve appeals | Only humans can decide policy appeals | Hard handoff rule, tested in evals |
| Merchant data in logs | Privacy | Simulated data only in v1; case files contain no personal info |
| Over-escalation | Defeats the cost goal | Track handoff precision |

## 9. Open questions

1. Should the agent also handle "my products are approved but not getting clicks"? (Proposed: no, out of scope for v1.)
2. Is one simulated store enough, or do evals need 3 to 4 stores with different problem mixes? (Proposed: one main store plus small per-test stores inside eval cases.)
