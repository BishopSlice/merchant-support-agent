# Transcript

- Store: `suspended-store`
- Model: `gemini-3.6-flash`
- Started: 2026-10-07 10:22 UTC

**Merchant:** None of my products are showing on Google anymore. What's going on?

<details><summary>Tool call: <code>check_feed({})</code></summary>

```json
{
  "store_id": "suspended-store",
  "store_name": "Pine & Pebble Home",
  "account_status": "suspended",
  "suspension_reason": "Misrepresentation: the website is missing a returns policy and business contact details.",
  "total_products": 3,
  "products_with_issues": 0,
  "disapproved_products": 0,
  "limited_products": 0,
  "issue_groups": []
}
```

</details>

<details><summary>Tool call: <code>search_help_docs({"query": "account suspended misrepresentation"})</code></summary>

```json
{
  "query": "account suspended misrepresentation",
  "results": [
    {
      "doc_id": "misrepresentation",
      "title": "Misrepresentation and account suspension",
      "source_url": "https://support.google.com/merchants/answer/6150127",
      "passage": "Most violations start with a warning email that gives the merchant time to fix the problem. Serious violations can lead to the account being suspended straight away, without a warning.",
      "score": 8
    },
    {
      "doc_id": "misrepresentation",
      "title": "Misrepresentation and account suspension",
      "source_url": "https://support.google.com/merchants/answer/6150127",
      "passage": "Google's misrepresentation policy does not allow listings that leave out important information or mislead shoppers about the product or the business. For example, payment terms, shipping costs and what happens after purchase must be shown clearly before the shopper commits to buy.",
      "score": 7
    },
    {
      "doc_id": "misrepresentation",
      "title": "Misrepresentation and account suspension",
      "source_url": "https://support.google.com/merchants/answer/6150127",
      "passage": "To fix the problem, update your website and your product data so they follow the policy. After that, you can ask Google to review the account.",
      "score": 7
    }
  ]
}
```

</details>

<details><summary>Tool call: <code>create_handoff_case({"issues_found": ["Account suspended for Misrepresentation: website is missing a returns policy and business contact details."], "suggested_next_step": "Review account suspension for misrepresentation and guide merchant on adding returns policy and contact details to website before requesting a review.", "already_tried": ["Checked feed status and found account is suspended."], "reason": "account_suspended", "merchant_request": "Merchant wants to know why products are not showing and get account reactivated.", "cited_doc_ids": ["misrepresentation"]})</code></summary>

```json
{
  "status": "created",
  "case_id": "CASE-20261007-102221-156529"
}
```

</details>

**Agent:** Your account is currently suspended for Misrepresentation because your website is missing a returns policy and business contact details. Because the account is suspended, no products can show on Google Shopping until this is resolved.

For more information on these policies, you can review [Misrepresentation and account suspension](https://support.google.com/merchants/answer/6150127).

I have created a support case for you: **CASE-20261007-102221-156529**. A specialist will review your account suspension. The case already includes all details from our conversation, so you will not need to repeat yourself.

## Saved cases

```json
[
  {
    "case_id": "CASE-20261007-102221-156529",
    "store_id": "suspended-store",
    "created_at": "2026-10-07T10:22:21.354051Z",
    "reason": "account_suspended",
    "issues_found": [
      "Account suspended for Misrepresentation: website is missing a returns policy and business contact details."
    ],
    "already_tried": [
      "Checked feed status and found account is suspended."
    ],
    "merchant_request": "Merchant wants to know why products are not showing and get account reactivated.",
    "suggested_next_step": "Review account suspension for misrepresentation and guide merchant on adding returns policy and contact details to website before requesting a review.",
    "cited_doc_ids": [
      "misrepresentation"
    ]
  }
]
```
## Notes

Run with `uv run python scripts/run_checkpoint_b.py suspended`.

**Handoff behaviour: correct (pass).**
- Its first reply called `check_feed`, said the account is suspended and why, said no products can show until that is resolved, and cited the misrepresentation doc.
- In the same reply it created an `account_suspended` case, gave the case number, and said the merchant won't need to repeat themselves. It didn't try to fix the suspension itself or promise a timing.
- The case has what a specialist needs: the suspension reason, what was checked, what the merchant wants, a next step and the cited doc.
