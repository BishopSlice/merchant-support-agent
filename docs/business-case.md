# Business case: Merchant Support Agent

_One page. Every number is either measured in this project or cited, and every assumption is stated so it can be challenged._

## The opportunity

When a Google Shopping product is disapproved, it stops showing in ads. The merchant loses sales and Google loses ad revenue until it's fixed. Today a merchant who can't work out the fix contacts support, and many of those contacts are plain data fixes the merchant could make alone with clear guidance: a missing GTIN, a price that doesn't match the website, a placeholder image.

The agent handles those fixes itself, in plain words and grounded in Google's help pages. It hands only the cases that need a person to a specialist (suspensions, policy appeals, explicit requests), with a complete case so the specialist doesn't have to ask the merchant again.

## What we know (measured or cited)

| Fact | Value | Source |
|---|---|---|
| Cost of a contact handled in a live channel (phone, chat, email) | **$8.01** average | Gartner, 2019 Customer Service and Support Leader poll ([Gartner press release, 25 Sep 2019](https://www.gartner.com/en/newsroom/press-releases/2019-09-25-gartner-says-only-9--of-customers-report-solving-thei); figure quoted by [destinationCRM, 26 Nov 2019](https://www.destinationcrm.com/Articles/CRM-Insights/Insight/Gartner-Survey-Finds-Self-Service-Insufficient-135436.aspx)) |
| Cost of a self-service contact | **$0.10** average | Same Gartner poll |
| Customers who fully solve their issue through self-service | **9%** | Same Gartner press release |
| Model cost of one agent conversation | **$0.02** | Measured over 94 eval conversations (`docs/v1-results.md`) at Google's 2026 price for `gemini-3.6-flash`; about $0.04 at the 2027 price |
| Plain data-fix cases the agent resolved without a handoff | **100%** (17 of 17, twice) | `docs/v1-results.md` (a scripted eval mix, not real traffic) |
| Cases needing a person that it handed off, and handoffs that were needed | **100% and 100%** (16 of 16) | Same |

The 9% figure is the point: ordinary self-service (help pages, FAQs) rarely finishes the job. The agent is self-service that actually resolves the problem, at a model cost much closer to self-service ($0.10) than to a live contact ($8.01).

Gartner published newer cost benchmarks in 2024 ("Benchmarks to Assess Your Customer Service Costs"). They're behind a paywall, so I couldn't check the figures, and they aren't used here. Secondary reports put live-channel costs higher than in 2019, which would make the savings below larger.

## Assumptions (change these and the answer changes)

1. **Volume:** 10,000 merchant contacts a month about disapproved products. This is illustrative; Google's real volume isn't public. Savings scale linearly with volume.
2. **Cost of a specialist contact:** $8.01, the Gartner live-channel average. A Merchant Center specialist may cost more (expertise, policy review) or less (scale, location).
3. **Containment:** the share of contacts the agent fully resolves without a person. This is the key unknown. Our eval mix is scripted and doesn't reflect real traffic, so three scenarios are shown.
4. **Every contact starts with the agent,** and handed-off contacts still cost a full specialist contact. The time a complete case saves the specialist isn't counted, so it's upside.
5. **Costs not counted:** engineering, hosting, review and monitoring. The model cost is the only running cost included.

## The numbers

Monthly support cost for 10,000 contacts:

| | Contained by the agent | Agent cost | Specialist cost | Total | Saving vs. today |
|---|---|---|---|---|---|
| Today (all specialist) | 0 | $0 | $80,100 | $80,100 | |
| Conservative | 30% | $200 | $56,070 | $56,270 | **$23,830 (30%)** |
| Middle | 50% | $200 | $40,050 | $40,250 | **$39,850 (50%)** |
| Optimistic | 70% | $200 | $24,030 | $24,230 | **$55,870 (70%)** |

**Break-even:** the agent pays for its model cost once it contains about **1 contact in 400** (0.25%), because $0.02 against $8.01 is roughly 1 to 400. At 2027 prices it's about 1 in 200. The question isn't whether the model cost is worth paying. It's how well the agent resolves real contacts, and what it costs when it gets one wrong.

## What could erode this

- **Wrong advice.** A merchant acting on a bad answer comes back, or churns. This is measured at 0 to 3% of replies (target under 5%), and every rule must come from a cited help page.
- **Over-escalation.** Each needless handoff costs a full specialist contact. The evals caught one regression of this kind during development, and it was fixed (`docs/task11-before-after.md`).
- **Under-escalation.** Missing a suspension or an appeal is the costliest failure, which is why handoff recall has the strictest target (95%).
- **Reality differs from the evals.** The first production step should be a shadow pilot that measures real containment and accuracy before the agent faces merchants.

## Not counted, but real

- **Faster fixes recover ad revenue.** Every hour a product stays disapproved is lost revenue for the merchant and for Google. The agent answers immediately, any time of day. I found no public data on how long disapprovals last, so this isn't quantified.
- **Specialist time per case.** Cases arrive with the issues, the merchant's reasons, what was tried and the cited policy, so the specialist doesn't have to re-ask the merchant. The completeness metric (100% in v1) measures that directly.

## Recommendation

Run a **four-week shadow pilot**. The agent drafts answers and cases for real disapproval contacts, specialists review them, and nothing reaches merchants. Measure containment, wrong advice and handoff accuracy on real traffic. Go live if containment is above 30% (already about $24,000 a month per 10,000 contacts at Gartner's cost) and wrong advice stays under 5%.
