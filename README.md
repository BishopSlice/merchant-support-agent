# Merchant Support Agent

An AI agent that helps online store owners fix rejected Google Shopping products. It diagnoses the product feed, explains the rule from real help docs, walks the merchant through the fix, and hands the case to a human specialist with a clean summary when it can't solve it.

> Status: project skeleton. See `docs/PRD.md` for what we're building and `docs/decisions/` for why.

## Project layout

```
merchant-support-agent/
  docs/             PRD, decision records, eval reports (the "PM" side)
  data/
    stores/         simulated stores: account status + product feed with planted problems
    help_docs/      saved policy and help pages the agent can search
  src/merchant_agent/
    models.py       shared data shapes (Product, Issue, Case)
    config.py       settings loaded from .env
    tools/          the actions the agent can take, one file per tool
    agent.py        wires the model and tools together
  app/              Streamlit screens (merchant chat, human inbox)
  evals/
    cases/          test conversations with expected outcomes
    results/        scored runs, one file per run
  tests/            unit tests for the tools (no model calls)
```

## Getting started

```bash
uv sync                      # install dependencies
cp .env.example .env         # then add your Gemini API key
uv run pytest                # run unit tests
uv run streamlit run app/streamlit_app.py
```

See `CONVENTIONS.md` for how code in this repo is written.
