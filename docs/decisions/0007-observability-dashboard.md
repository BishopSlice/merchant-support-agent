# 0007: Observability dashboard

_8 Oct 2026. Status: accepted (Vikrant). Two dependency questions are **pending approval** (see Consequences)._

**Decision:** Build our own read-only **/ops** page in the same Material shell, behind its own access code (separate from the specialist's). It has five panels (Outcomes, Quality, Safety, Operations, Releases) and a per-conversation trace drill-down. Merchants can give **thumbs up or down** on agent replies. About **10% of live conversations** get sampled AI grading, within a daily budget.

**Why:**
- The evals say how the agent behaves on 91 scripted cases. A dashboard says how it behaves on real conversations.
- Product teams running agents in production need to see outcomes, quality, safety and cost together. That's what the target roles ask for: measurable impact, accuracy reviews, value measurement.
- Our own page keeps everything in one product and one repo, and the eval scorecard can sit next to live metrics. A hosted vendor tool would split that and add an account.

**How (SPEC, Observability):**
- **Tracing:** ADK's built-in OpenTelemetry tracing, with spans tagged with session, agent version, entry point and traffic source. Staying on the OTel standard means a Cloud Trace export later is a configuration change, not a rewrite.
- **Storage:** a SQLite event store.
- **One metrics module** shared by the eval runner and the dashboard, with tests that both compute every definition the same way. A metric can't mean one thing in the evals and another on the dashboard.
- **Off the critical path:** logging writes happen after each reply, never during the merchant's wait, and the overhead is measured.

**Honesty rules:**
- Every chart says which traffic it includes: live, eval (labelled "eval traffic"), or replay (always excluded from metrics).
- Small samples get a warning.
- No chart is ever filled with made-up data.

**Privacy:**
- Emails and phone numbers are masked before storing.
- Message text is kept for 30 days, and aggregate metrics after that.
- Capturing the full prompt is off by default.

**Not chosen:**
- **A hosted observability vendor:** it would need another account, would split the story, and couldn't show eval scorecards next to live metrics.
- **No dashboard:** the evals alone can't show live behaviour, merchant feedback or spend.

**Consequences, and what's pending:**
- **OpenTelemetry.** `opentelemetry-api` and `opentelemetry-sdk` are already installed as dependencies of `google-adk`, and ADK includes a SQLite span exporter. Declaring them as direct dependencies of this project, rather than relying on them transitively, is **pending approval**.
- **Charts.** A chart library for the dashboard is **pending approval**. The fallback is plain SVG charts drawn by our own code.
- **Minimum version if time is short:** panels 1 (Outcomes), 3 (Safety) and 4 (Operations), plus the trace view.
