# 0004: An MCP-shaped data layer; connecting real accounts dropped

_8 Oct 2026. Status: accepted (Vikrant)._

**Decision:** The agent reads merchant data through a `MerchantData` interface. Its only v2 backend, `MockMerchantMcp`, serves the demo stores using the **same tool names and response shapes** as [Google's Merchant API MCP Access Service](https://developers.google.com/merchant/api/guides/agentic-tools/merchant-data-mcp), which is in alpha.

The mock covers `list_products`, `get_product_by_name`, `list_account_issues`, `list_aggregate_product_statuses` and `get_automatic_improvements`. Its models mirror the documented `Product`, `ProductStatus`, `ItemLevelIssue`, `Severity` and `AutomaticImprovements` resources.

Only those read tools are exposed to the agent. The data-source tools (`create_data_source`, `fetch_data_source` and the others) and `report_search` are never exposed, and calling them raises an error.

**Connecting a real Merchant Center account is dropped.**

**Why drop connecting:**
- **It contradicts the concept.** v2 is a feature inside Merchant Center, where the merchant is already signed in and the agent would read their data natively. OAuth-connecting an account would make it a third-party app, a different product.
- **High risk, low value:**
  - the Merchant API's OAuth scope (`content`) allows writes as well as reads
  - a public app needs Google's OAuth verification
  - real catalogue data would go to the model, which brings privacy duties
  - the MCP is alpha
  - reviewers wouldn't connect real stores anyway
- **Practical barrier:** Merchant API calls need a one-time developer registration that the docs say is "only supported for production accounts". Test accounts can't be registered, and a production account needs a real store.

**Why mirror the MCP anyway:**
- It's how a real in-product agent, or Google's own tooling, would read this data, so the design is credible and the swap is small.
- It brings the real schema into the evals: the `DEMOTED` severity, account issues, and automatic-improvement settings that default to on.
- Contract tests pin our models to the documented shapes.

**Honesty notes:**
- Google doesn't publish a complete list of item-level issue codes. The mock keeps our own codes inside the documented `code` field, marked illustrative.
- The README says plainly that the prototype is MCP-shaped and not connected.

**Not chosen:**
- **Connect mode with OAuth**, for the reasons above.
- **Calling the real MCP from the evals:** it needs a registered production account, it's alpha, it would make the evals non-deterministic, and it shares Merchant API quota.
