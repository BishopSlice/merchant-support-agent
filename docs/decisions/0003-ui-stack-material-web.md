# 0003: UI stack, Material Web on FastAPI

_8 Oct 2026. Status: accepted (Vikrant)._

**Decision:** Replace the Streamlit app with a static front end built from Google's **Material Web** components (`@material/web`, Material 3). It's loaded from a CDN as ES modules, pinned to an exact version, with no build step. A **FastAPI** app served by **Uvicorn** provides the JSON API and serves the static files. The agent, tools and evals don't change.

**Why:**
- v2 places the agent inside a Merchant Center-like shell. Streamlit can't render Material components or a convincing product shell; a theme only gets part of the way.
- Material Web is Google's own Material 3 implementation, so it's the most faithful look for the least effort: plain HTML and JS, nothing to compile.
- FastAPI gives a small, testable API (FastAPI's `TestClient`). It's the natural place for sessions, access codes, caps and replay.

**Risk, accepted knowingly:** Material Web is officially in **maintenance mode** ([announcement](https://github.com/material-components/material-web/discussions/5642)): bug fixes only, no new components. For a pinned prototype that's acceptable. Pinning an exact version keeps it stable. If a needed component is missing, we use a plain HTML element styled with Material 3 tokens rather than switch libraries.

**Not chosen:**
- **Angular with Angular Material:** Google's actively maintained stack and the most authentic, but it means a Node and TypeScript build and much more effort for a PM portfolio.
- **React with MUI:** popular, but Material-inspired rather than Google's own, and closer to Material 2.
- **Streamlit with a theme:** cheapest, but it can't produce the in-product shell.

**Consequences:**
- Two new dependencies (FastAPI, Uvicorn; approved).
- The Streamlit app and guide are retired after the new UI passes its checks.
- UI tests move to API tests plus browser checks in the Claude browser pane. Playwright isn't approved.
- No Google logo or product name; a persistent "Concept prototype, not a Google product" label.
