# 0001: Tech stack

**Decision:** Python, Gemini models through Google's Agent Development Kit (ADK), Streamlit for screens, `uv` for packages, `pytest` for tests.

**Why:**
- The target role is at Google, so building on Google's own agent stack is a natural fit and an easy talking point.
- ADK handles the agent loop and tool calling so our code stays focused on tools, handoff rules and evals.
- Streamlit gives a usable UI in Python without a separate frontend.
- `uv` makes installs fast and repeatable.

**Not chosen (for now):** a custom web frontend (too slow for the timeline), a vector database (a handful of help docs fits in simple search; revisit if docs grow past ~100 pages).
