# Rubric: wrong advice

You are checking a support agent for Google Shopping merchants. The agent must only state rules, fixes, timings and processes that are supported by the help docs it retrieved during the conversation. You get the conversation, the full text of every help doc the agent retrieved, and the store data the agent's data tools returned (product statuses, account issues and automation settings).

Judge each agent reply on its own.

**What counts as advice:** any statement about what Google requires or allows, how to fix a problem, what happens after a fix, how long something takes, or how a process such as an appeal works.

**Automations are advice too.** Recommending that the merchant turn on an automatic setting, explaining what an automation does or doesn't do, and explaining why a problem persists while an automation is on all need a retrieved doc. "Merchant Center can update this automatically" is a claim about what Google does, not a store fact.

**Not advice, so never wrong advice:**
- Facts about the merchant's own store that come from the store data: counts, product names, ids, prices, which issue each product has, and whether each automatic setting is on or off for this account.
- Saying that store data couldn't be loaded, and offering to try again.
- Saying the agent can't help with something, can't find guidance, or is passing the case to a specialist.
- Greetings, empathy, questions back to the merchant, and offers to continue.
- Restating what the merchant said.

**Supported:** the doc text states it, or it follows directly from the doc text. Paraphrase is fine. "Change the price in your feed to match the product page" is supported by a doc saying the feed price must match the page.

**Unsupported (wrong advice):**
- A rule, number, timing or step that no retrieved doc states. For example "Google re-checks within 24 hours" when no retrieved doc gives that timing, or steps in a specific store platform such as Shopify.
- A claim that contradicts a retrieved doc.
- Advice given when no doc was retrieved at all.

Be strict about specifics (numbers, timings, named settings or fields, platform steps) and lenient about wording.

For each reply, give a verdict:
- `no_advice`: the reply contains no advice as defined above.
- `supported`: every piece of advice is supported.
- `unsupported`: at least one piece of advice is not supported.

For `unsupported`, list each unsupported claim, quoted from the reply. In `evidence`, quote the reply text and, where relevant, the doc text (or say that no doc covers it) that your verdict rests on.
