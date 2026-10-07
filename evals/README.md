# Evals

Scripted merchant conversations, run against the real agent and scored against the PRD's success metrics.

## Case files

One TOML file per case in `cases/`, named after its `id`:

```toml
id = "fix-missing-shipping"
category = "easy_fix"            # see Category in case_format.py
store = "shipping-only"          # a store in data/stores/ or evals/stores/
description = "Missing shipping cost, then added."

[[turns]]
merchant = "My string lights were disapproved. What's the problem?"

[[turns]]
fix = "missing_shipping"         # optional: the merchant fixes this issue before sending
merchant = "I added the shipping cost. Can you check again?"

[expect]
should_handoff = false
# handoff_reason = "policy_appeal"   # required when should_handoff = true
resolved_issues = ["missing_shipping"]   # gone from the agent's last feed check
must_cite = ["shipping"]                 # help doc ids whose link must appear in a reply
must_mention = ['''shipping''']          # case-insensitive regexes, any reply
must_not_say = ['''CASE-\d''']
# case_must_cite = [...]        # doc ids the handoff case must list
# case_must_mention = [...]     # regexes the handoff case text must match
```

Patterns use TOML literal strings (`'''...'''`), so regex backslashes need no escaping.

`stores/` holds small stores built for single cases (one issue type each, a tie between issue groups, and planted instructions in product text). Each case runs on a fresh temporary copy of all stores and help docs, so fixes and handoff cases never leak between cases.

Checking the files: `uv run pytest tests/test_eval_cases.py` loads every case and fails if an id, store, doc, fix or pattern is wrong, or if the set stops covering every handoff rule at least three times.

## Held-out set

`cases_heldout/` holds seven cases written before Task 11 changed the agent's instructions, and committed before any prompt change, so they can show whether a fix generalizes rather than fitting the main 40. They use their own stores (a hemp oil product, a second suspension reason, three broken images, two long titles) and new merchant wording. Run them with `uv run python -m evals.run --set heldout`.
