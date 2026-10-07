# Skills audit: work so far against three agent skills

_7 Oct 2026. Covers everything up to Checkpoint C (commit 26958ff) plus the fixes listed below._

I didn't use the skills in `.agents/skills/` while building Tasks 1 to 7. This audit checks that work against three of them, read in full, plus the reference they link to:

- `test-driven-development`
- `incremental-implementation`
- `code-review-and-quality`
- `references/definition-of-done.md`

The project copy of the skills doesn't include the `references/` folder, so I read it from the full pack in `~/Documents/RPM/sources/frameworks/agent-skills/references/`. Its `testing-patterns.md` is written for JavaScript, so I used only its general principles: arrange, act, assert; descriptive names; and mocking only at boundaries.

`SPEC.md` and `CONVENTIONS.md` still take priority where they differ from a skill.

## Summary

| Skill | Verdict before the audit | What changed |
|---|---|---|
| Test-driven development | Mostly met. Rule checks, the checker, help search, handoff, demo helpers and the app were written test-first. Some coverage gaps were found by experiment, and three pieces were tested after the code. | 11 missing tests added, 2 bugs fixed with a failing test first |
| Incremental implementation | Met. 49 small commits, each with tests and lint run. One commit went in with failing tests and was amended. | Nothing to fix. The gating mistake is described below |
| Code review and quality | Partly met. I never ran an explicit five-axis review of my own diffs. Doing it now found duplicated setup code and a UI bug. | 2 fixes. A review step is now part of my process |

## Test-driven development

**Meets the skill**

- Every rule check went red before it went green. For example, `tests/test_feed_rules.py` gained the price mismatch tests, they failed, and `check_price_mismatch` was added in the next commit (ca8176a).
- Bugs were handled with the Prove-It pattern. For example, the Gemini rate-limit crash got a failing retry test (`tests/test_agent.py`, `test_model_retries_when_rate_limited`) before the fix (b617784).
- Tests use fakes at the boundary, not mocks of internals. `FakeRunner` in `tests/test_chat.py` replays real ADK `Event` objects, and `FakeChatSession` in `tests/test_app.py` stands in only for the model.
- Most tests are small: pure functions over in-memory products. Store loading and the app tests are medium, on local files and Streamlit's in-process AppTest. No unit test calls the model.

**Fell short**

1. **Coverage was thinner than it looked.** The code review skill says to test coverage by experiment: flip a condition and see whether any test fails. I flipped 25 conditions in the core logic. 10 stayed green, meaning no test pinned those behaviours down:
   - `feed_rules.py`: a blank landing-page price or availability, a price with no currency, an image link missing `://`, and whitespace-only shipping
   - `handoff.py`: case ids that reach outside the cases folder (the old test only tried a path to a file that didn't exist), and handoffs for an unknown store
   - `demo.py`: title fixes that cut a word in half
   - `chat.py`: model "thought" text leaking into replies
   - `agent.py`: the retry delay cap

   The test that cases list newest first (`tests/test_handoff.py`, `test_list_cases_returns_newest_first`) passed partly by luck of file order. **Fixed in e29cb0e**, and all 25 flipped conditions now make a test fail.
2. **Some tests came after the code.** The terminal transcript (`src/merchant_agent/cli.py:15`, tested by `tests/test_cli.py:4`), the first version of `ChatSession`, and the instruction checks in `tests/test_agent.py:29` were each written in the same step as, or after, the code they test. The skill's red flag "tests that pass on the first run" applies to `test_restricted_terms_match_whole_words_only` (`tests/test_feed_rules.py:101`). It guards a real behaviour, and the mutation check above confirms it would catch a regression.
3. **Instruction tests check wording.** `tests/test_agent.py:29-70` assert that phrases such as `"do not hand off"` appear in the prompt. That checks how the prompt is written, not how the agent behaves. They are worth keeping as a cheap tripwire against deleting a rule, but the evals (Tasks 8 to 10) are what actually test behaviour.

**Bugs found while auditing (Prove-It pattern)**

- `demo.apply_fix` crashed with `IndexError` on a feed with a header but no products. **Fixed in 20128ed.**
- On the inbox page the store picker was hidden, so "Simulate a fix" quietly used `sample-store`. **Fixed in 2f2509e.**

## Incremental implementation

**Meets the skill**

- Thin slices with the riskiest first: the ADK agent with a single tool (Task 3) was proven before help search, handoff or any UI.
- One logical change per commit, with messages in the imperative mood that explain why. Data, code and doc changes went in separate commits (for example 059493d for help docs, then 15238c9 for the search tool).
- Scope discipline: I didn't touch Vikrant's tooling folders, and things noticed along the way (such as the GTIN severity question) were reported, not quietly changed.
- Safe defaults: tools read `store_id` from the session, not from the model (`src/merchant_agent/agent.py:85`). Demo fixes refuse to touch the real `data/` folder (`src/merchant_agent/demo.py:57`).

**Fell short**

- **One commit broke "keep it compilable".** In Task 2 I piped `pytest` into `tail`, which hid the failing exit code, and a commit went in with 2 failing tests. I amended it before pushing and have since gated commits with `uv run pytest -q && uv run ruff check . && git commit`, with no pipes.
- **Assumptions were stated after acting, not before.** For example, when I read "Go" as Task 5, and when I decided to scope tools to the session's store. The meta-skill (`using-agent-skills`) asks for an "assumptions I'm making" note up front. I'll do that from now on.

## Code review and quality

I hadn't reviewed my own diffs on the five axes. Doing it now:

**Correctness:** covered by the test findings above.

**Readability and simplicity**

- The runner and session setup was copied in three places (`ChatSession`, the terminal chat and the Checkpoint B script), and `cli.py` re-exported constants only so the script could import them. **Fixed in 1db9ae4** with `new_runner` and `new_session` in `chat.py`.
- File sizes are healthy: the largest module is `feed_rules.py` at 184 lines, and the whole of `src/` plus `app/` is about 1,250 lines.

**Architecture**

- Logic lives in `src/` and the Streamlit file is layout only, as the brief for Tasks 6 and 7 asked.
- FYI: the model-facing wrappers in `agent.py` (`check_feed` and `create_handoff_case`) add a layer, but it carries the security decision that the store comes from the session. That justifies it.

**Security**

- Inputs are checked at the edges: store ids against a slug pattern (`src/merchant_agent/stores.py:18-21`), case ids against a pattern, and personal contact details rejected in cases (`src/merchant_agent/models.py:116`). `.env` has never been in git history (checked with `git log --all -- .env`).
- Open: feed text (titles, descriptions) goes to the model as tool output. A merchant could plant instructions in a product title. The Task 8 evals include injection-style cases to measure this.

**Performance:** nothing material. Each tool call reads a 30-row CSV, and help docs are cached.

**Error paths**

- Open: `list_cases()` (`src/merchant_agent/tools/handoff.py:69-73`) fails on one corrupt case file, which would break the inbox.
- Open: the terminal chat (`src/merchant_agent/cli.py:95`) exits on an API error, while the app shows the error (`app/streamlit_app.py:66`).

Both are minor for a local demo. I've left them as findings rather than add silent fallbacks.

## Definition of done: standing gaps

- **Human review before merge.** All work has gone straight to `main` with no review step. The git skill favours a branch and a reviewed PR per task. This is your call (see below).
- **Observability.** Nothing is logged at runtime. Task 9 records tool calls and token usage per eval run, which covers the PRD's cost metric. Logging in the app itself is not planned.
- **Docs describe the current state.** The README is current. `SPEC.md`'s module table and project structure don't list `chat.py`, `demo.py`, `inbox.py`, `stores.py` or `scripts/` (see below).

## Needs your call

1. **Update the SPEC module table** (`SPEC.md:29-50`) to list `stores`, `chat`, `demo`, `inbox` and `scripts/`. It's documentation only, but SPEC changes are yours to approve.
2. **Branch and PR per task** instead of committing straight to `main`. That would give each task a review point that matches the definition of done. Nothing has been pushed yet, so it would start with the evals.
3. **Corrupt case files and CLI error handling** (above): fix now, or leave for Task 11 or later.

## How I'm working from here

- I'll state my assumptions before non-trivial work.
- I'll run the five-axis review on my own diff before each checkpoint, starting with Checkpoint D.
- I'll use the mutation spot-check on new core logic, starting with the eval scorers.
- Commit gating stays strict: no piping the test command.
