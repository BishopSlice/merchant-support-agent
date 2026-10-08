# PRD: Merchant Support Agent

_Status: **v2 draft for review**, 8 Oct 2026. Owner: Vikrant Narayan. v1 (7 Oct 2026, delivered and measured in `docs/v1-results.md`) is in git history; section 10 lists what changed._

## 1. Problem

Small online stores sell through Google Shopping by sending their product data to Merchant Center. When a product breaks a rule, Google disapproves it and it stops showing in ads. The store owner usually finds out because sales drop.

Fixing it is hard for them today:
- **Terse messages.** The error messages are short and technical ("Missing value [gtin]").
- **Scattered rules.** The rules live across many help pages, and one account often has several different problems at once.
- **Unclear automations.** Merchant Center can already fix some problems automatically (price and availability updates, image improvements), but merchants don't always know which ones are on, or why a problem persists when they are.
- **Starting from scratch.** Some problems (policy appeals, account suspensions) need a person at Google, and when the merchant reaches one, they explain everything again.

For Google, every case that reaches a specialist costs money, and every hour a product stays disapproved is lost ad revenue.

## 2. Context: Merchant Advisor

In May 2026 Google began testing **Merchant Advisor**, an AI assistant inside Merchant Center, in beta ([Search Engine Roundtable, 13 May 2026](https://www.seroundtable.com/google-merchant-advisor-41319.html)). Little about how it works is public.

This project is an independent take on one slice of that space: **troubleshooting disapprovals and handing off to a person when the agent shouldn't act alone**. It makes no claim about how Merchant Advisor is built, and it uses no Google branding.

## 3. Concept

A **feature inside Merchant Center**, shown as a concept prototype:
- **Merchant Center-like shell.** The merchant is already signed in to a Material-style page, with only **Products → Needs attention** working. All other navigation is visible but disabled.
- **Agent entry points.** The agent opens as a **side panel** from an issue row ("Help me fix this") or from a **Help** entry ("What's wrong with my products?").
- **Fixing.** The merchant fixes data in an **Edit product** form inside the shell, the way they would in the real product. The agent re-checks.
- **Labelling.** Every screen carries a "Concept prototype, not a Google product" label. There's no Google logo or product name.

## 4. Users

| User | What they want | Where |
|---|---|---|
| **Merchant** (the only user of the main journey): owner of a small online store, not technical | "Tell me what's wrong, in plain words, and exactly what to change." | The shell and side panel |
| **Support specialist** (secondary): person at Google who handles escalated cases | "When a case reaches me, give me the full picture so I don't re-ask the merchant." | A separate specialist page behind a demo login. It isn't part of the merchant journey. |

v1's "demo operator" role is removed: merchants fix their own data in the Edit product form.

## 5. Goals and non-goals

**Goals**
1. **Diagnose.** Find every disapproved or demoted product and every account-level issue, and group them by root cause.
2. **Triage.** Order the work: account issues first, then disapprovals by number of products affected, then warnings.
3. **Route to automations.** If an issue is one Merchant Center can fix automatically (price and availability mismatches, through automatic item updates), say so. Recommend turning it on when it's off, citing the help page, and explain why the issue persists when it's on.
4. **Explain.** Explain every issue in plain language, grounded in cited help pages, with no rules from memory.
5. **Walk through fixes.** Go one issue at a time, name every affected product, and re-check after a fix.
6. **Hand off.** Hand off to a person with a complete case when the agent shouldn't act alone, and show the merchant a **preview** of what the specialist will receive.

**Non-goals for v2**
- Connecting a real Merchant Center account, or calling real Google APIs. The data comes from a mock with the same tool names and response shapes as Google's Merchant API MCP ([ADR 0004](decisions/0004-mcp-shaped-data-layer.md)).
- Writing to merchant data on the merchant's behalf. The agent reads data; merchants make changes themselves.
- Any Merchant Center feature other than Needs attention.
- Billing, bidding, ad performance and other Google products. These are redirected politely.
- Languages other than English.

## 6. User journey

1. The merchant opens **Needs attention** and sees the issues table: 13 disapproved and 5 demoted products, and the account's settings.
2. They click **Help me fix this** on a price mismatch. The side panel opens already knowing which issue and product, so it doesn't ask.
3. The agent checks the account's automatic improvements. Item updates are off, so it explains the mismatch and recommends turning item updates on, citing the help page. It also gives the manual fix.
4. The merchant asks "what else is wrong?". The agent triages the rest, account issues first, then the biggest disapprovals.
5. The merchant edits a product in the shell and says "done". The agent re-checks and confirms or explains what's still flagged.
6. On something the agent must not handle (an appeal, a suspension, a request for a person), it says so, creates a case, and shows the merchant a **case preview** with their own reasons recorded.
7. On the separate specialist page, a specialist sees the full case: store, issues, the merchant's reasons, what was tried, the automation state, cited policy and a suggested next step.

## 7. What the agent can do (tools)

**Data tools.** These are read-only, with the same names and response shapes as [Google's Merchant API MCP](https://developers.google.com/merchant/api/guides/agentic-tools/merchant-data-mcp), served by a local mock.

| Tool | What it returns |
|---|---|
| `list_products` | Products with their status and item-level issues |
| `get_product_by_name` | One product's full status and issues |
| `list_account_issues` | Account-level issues (for example a suspension) |
| `list_aggregate_product_statuses` | Counts of approved, pending, disapproved and demoted products |
| `get_automatic_improvements` | Whether automatic item updates, image improvements and shipping improvements are on |

**Our tools**

| Tool | What it does |
|---|---|
| `search_help_docs` | Finds the relevant help-page passages for an issue or question |
| `create_handoff_case` | Saves a structured case for a specialist and returns the preview shown to the merchant |

The data-source write tools the MCP offers (`create_data_source`, `fetch_data_source` and the others) are **never** exposed. That's enforced by an allowlist and tested as a hard release gate.

## 8. Handoff rules (unchanged from v1)

The agent **must** hand off when:
- the account is suspended or has a policy strike
- a product is disapproved under a restricted or prohibited content policy and the merchant wants to appeal or disagrees
- the merchant asks for a person, or is clearly frustrated after two failed attempts
- no help page supports an answer

The agent **must not** hand off:
- a plain data fix the merchant can make themselves
- an issue an automation would fix
- a question about how to get a product approved, as opposed to a request to appeal

## 9. Success metrics

The v1 metrics are kept. v2 adds metrics for automation routing, triage, tool safety and the product surface. Targets, reasons and measurement methods are in [SPEC.md, Evals](../SPEC.md#evals).

| Metric | What it means | v2 target |
|---|---|---|
| Resolution rate | Share of fixable cases fully resolved | 80% or higher |
| Wrong advice rate | Share of replies stating something no retrieved help page supports | under 5% |
| Handoff precision | Of handoffs, the share that were needed | 90% or higher |
| Handoff recall | Of cases needing a person, the share handed off | 95% or higher |
| Case completeness | The specialist needs nothing more from the merchant | 90% or higher |
| Automation-routing accuracy | Recommends, explains or stays silent about automations correctly | 95% or higher |
| Triage accuracy | Issues raised in the agreed order | 90% or higher |
| Write calls | Calls to any data-writing tool | **0, hard gate** |
| Graceful failure | When data can't load, it says so and invents nothing | **100%, hard gate** |
| Injection resistance | Ignores instructions planted in product or account data | **100%, hard gate** |
| Uniquely agent-resolved rate | Resolved cases that an automation couldn't have fixed | tracked; feeds the business case |
| Cost per conversation | Model cost of a full conversation | $0.03 or less at 2026 prices |

## 10. What changed from v1

| v1 | v2 | Why |
|---|---|---|
| A standalone app | A feature inside a Merchant Center-like shell | It's where merchants already are ([ADR 0003](decisions/0003-ui-stack-material-web.md)) |
| Three roles (merchant, demo operator, specialist) | The merchant only; specialist on a separate page | Three roles was cognitive overload ([ADR 0005](decisions/0005-single-persona.md)) |
| A simulated feed checker | A mock with Merchant API MCP tool names and response shapes | Credible path to real data, with no account risk ([ADR 0004](decisions/0004-mcp-shaped-data-layer.md)) |
| Counted price and availability fixes as agent wins | Routes them to Merchant Center's automations, and credits them | Honest value: the agent shouldn't compete with built-in automation |
| Local-only Streamlit | Material Web front end on FastAPI, hosted with free replay and gated live chat | Real Material look; safe public demo ([ADR 0006](decisions/0006-hosting-and-replay.md)) |
| Connecting a real account was considered | Dropped | Contradicts the in-product concept, and the risk is high and the value low ([ADR 0004](decisions/0004-mcp-shaped-data-layer.md)) |

## 11. Risks and responsible AI

| Risk | Why it matters | Mitigation |
|---|---|---|
| Confident wrong policy advice | The merchant makes a bad change or loses trust | Answers must cite a retrieved help page; "not sure" triggers a handoff; graded every run |
| Recommending an automation that won't help | Wastes the merchant's time and erodes trust | Automation routing has its own eval cases and target |
| The agent writes to merchant data | Irreversible change to a business's catalogue | Read-only allowlist; write calls are a hard gate |
| Data fails to load and the agent fills the gap | Fabricated issues are the worst kind of wrong advice | Graceful-failure cases are a hard gate |
| Planted instructions in product text | The agent gets manipulated | Injection cases are a hard gate |
| Looking like an official Google product | Misleads viewers | No Google logo or name; a persistent "Concept prototype" label; a check in the UI tests |
| A public demo spends the Gemini budget | Cost | Free replay by default; live chat needs an access code and is capped |
| Over-escalation | Defeats the cost goal | Handoff precision target |

## 12. Portfolio context

The roles this project is aimed at, and where it answers each one:
- **Agentic customer engagement (Google):** an agent that diagnoses, troubleshoots and hands off to people; this PRD; defined metrics. See sections 6 to 9 and the evals.
- **AI-redesigned workflows with responsible AI (Meta):** measured accuracy, an injection gate and a hand-checked AI grader; prompt and context engineering (entry-point context, the leak guard). See `docs/responsible-ai.md` and SPEC, Evals.
- **AI value strategy (Accenture):** the use case, the agent and process design, a business case built on stated assumptions, value measurement (the uniquely agent-resolved rate), and a knowledge layer (help-page grounding). See `docs/business-case.md`.

## 13. Open questions

1. Should the specialist page also be reachable from the case preview, as "see it as the specialist will"? Proposed: no; the separate login keeps the merchant journey single-persona.
2. Should replay transcripts be re-recorded automatically when the agent changes? Proposed: a check fails if they're stale, and re-recording is a manual step (SPEC, Evals f).
