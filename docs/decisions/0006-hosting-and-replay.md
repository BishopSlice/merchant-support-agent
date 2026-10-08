# 0006: Hosting, free replay by default and gated live chat

_8 Oct 2026. Status: accepted (Vikrant)._

**Decision:** The public demo is hosted (one container, which serves both the FastAPI API and the static front end).
- **Default mode: replay.** Recorded real conversations from the current agent version are played back in the UI, so every visitor sees the full journey instantly at no model cost.
- **Live mode** needs an **access code** and is capped: 30 messages per session and 400 per day across all sessions by default. Over a cap, the visitor gets a friendly message.

**Why:**
- With connecting real accounts dropped ([ADR 0004](0004-mcp-shaped-data-layer.md)), the demo needs no Merchant Center account, only simulated data and our Gemini key.
- The remaining risk is strangers spending that budget. Replay removes it for most visitors, and the code plus caps bound it for the rest.
- Recruiters get a working demo in one click, without waiting on a model.

**Guardrails:**
- Each replay file records an **agent version** (a hash of instructions, tool schemas and model name). A test fails if any replay is stale, so the demo can't show behaviour the current agent no longer has.
- Replays are recorded from real runs, never written by hand.
- Each browser session gets its own copy of the demo data, so one visitor's edits never leak to another.
- Keys live only in the host's secret store, never in the repo or the browser.

**Not chosen:**
- **No hosting** (video plus clone-and-run): safest, but reviewers rarely clone repos.
- **Live chat open to everyone:** unbounded cost and abuse.

**Open:** the choice of host (for example Cloud Run) is made in the plan's hosting phase, and it's a separate approval because it may need an account and billing.
