# 0002: Issue severity

**Decision:** Every issue the feed checker finds has a severity: "disapproved" (the product can't show at all) or "limited" (the product shows, but reaches fewer shoppers). Missing GTIN is limited; the other six checks are disapproved.

**Why:** Google's own GTIN help page calls the GTIN "recommended" and says products missing one may get limited visibility. Treating it as a disapproval meant the agent would cite a doc that contradicted our checker. A product could still be disapproved if it has a GTIN and the merchant leaves it out, but our simulated feed can't tell whether a manufacturer assigned one, so we model the common case. The other six help docs either say the issue leads to disapproval or give no reason to soften it, so they stay disapproved.

**Not chosen (for now):** a third "info" level, and per-product severity based on brand or category. Revisit if a new rule needs it.
