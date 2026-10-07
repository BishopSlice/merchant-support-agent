# Technical spec: Merchant Support Agent

_Status: draft for review. The product "why" lives in `docs/PRD.md`; this file is the "how"._

## Objective

Build the agent described in the PRD as a local Python app: a merchant chat screen, a specialist inbox screen, and an eval suite that scores the agent against the PRD's metrics.

**Done means:** a merchant can chat through a full diagnosis and fix flow on the sample store, handoff cases appear in the inbox, and `evals` produces a scorecard for every PRD metric.

## Tech stack

- Python 3.13, managed with `uv`
- Google Agent Development Kit (`google-adk` 2.x) with `gemini-3.6-flash` (model name set in `.env`)
- `pydantic` 2 for data shapes, `python-dotenv` for settings
- Streamlit for screens
- `pytest` for tests, `ruff` for linting

## Commands

```
Install:   uv sync
Test:      uv run pytest
Lint:      uv run ruff check .
Run app:   uv run streamlit run app/streamlit_app.py
Run evals: uv run python -m evals.run
```

## Modules (build order top to bottom)

| Module | Responsibility | Depends on |
|---|---|---|
| `models` | Data shapes: Product, Issue, Case | nothing |
| `feed_checker` | Load a store's feed and run rule checks | models |
| `help_search` | Load help docs and return the best matching passages | nothing |
| `handoff` | Create, save and list specialist cases | models |
| `agent` | ADK agent: instructions plus the three tools | all tools |
| `app` | Merchant chat and specialist inbox | agent, handoff |
| `evals` | Test cases, runner, scorer, saved results | agent |

## Project structure

```
data/stores/<store_id>/   store.json (account status) + feed.csv
data/help_docs/           one markdown file per help topic, with source URL
src/merchant_agent/       models.py, config.py, agent.py, tools/
app/                      Streamlit screens
evals/cases/              one YAML/JSON file per test conversation
evals/results/            one file per eval run, never overwritten
runtime/                  cases created while running (gitignored)
tests/                    unit tests, no model calls
```

## Code style

```python
def check_feed(store_id: str) -> dict:
    """Check a store's product feed and return its problems grouped by issue type."""
    products = load_feed(store_id)
    issues = [issue for product in products for issue in run_checks(product)]
    return summarize(issues)
```

- Small functions with type hints and a plain-English docstring (the model reads tool docstrings).
- Each rule check is its own small function so new rules are added without touching others.
- No hidden state: tools take inputs and return plain data.

## Testing strategy

- **Unit tests** (`tests/`): every tool and every rule check, with no model calls. Run on every change.
- **Evals** (`evals/`): full conversations scored against the PRD metrics. Run on every prompt or tool change; results saved with the date and model name.
- Test-first for rule checks: write the failing test for a planted problem, then the check.

## Boundaries

- **Always:** run tests before each commit; keep one logical change per commit; update this spec when a decision changes.
- **Ask first:** adding a dependency; changing the PRD metrics or handoff rules; switching models.
- **Never:** commit `.env` or keys; call real Google Merchant APIs; delete or overwrite saved eval results.

## Success criteria

1. `uv run pytest` passes with tests for every rule check and tool.
2. The sample store has at least 6 planted issue types and the checker finds all of them.
3. The agent completes the PRD journey end to end in the app.
4. Every handoff rule in the PRD has at least 3 eval cases.
5. The eval runner prints a scorecard covering all six PRD metrics.

## Open questions

1. Help docs: I'll write short paraphrased summaries of real Merchant Center help pages, each with its source link, rather than copying Google's text. OK?
2. Evals: should a second model grade the fuzzy metrics (case completeness, wrong advice), with you hand-checking a sample? I recommend yes.
