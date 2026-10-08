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
| Model cost of one agent conversation | **$0.0074** (v2) | Measured over 69 eval conversations (`docs/v2-results.md`) at Google's 2026 price for `gemini-3.6-flash`, with one model call per answer ([ADR 0008](decisions/0008-one-call-answers.md)). It was $0.02 in v1, and is about $0.015 at the 2027 price |
| Plain data-fix cases the agent resolved without a handoff | **100%** | `docs/v1-results.md` and `docs/v2-results.md` (a scripted eval mix, not real traffic) |
| Resolved cases that Merchant Center's automations couldn't have fixed (uniquely agent-resolved) | **82%** | `docs/v2-results.md`. The other 18% were price or availability mismatches, which automatic item updates can fix. There the agent recommends turning them on instead of claiming the fix |
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
| Conservative | 30% | $74 | $56,070 | $56,144 | **$23,956 (30%)** |
| Middle | 50% | $74 | $40,050 | $40,124 | **$39,976 (50%)** |
| Optimistic | 70% | $74 | $24,030 | $24,104 | **$55,996 (70%)** |

**Crediting only what the agent uniquely solves.** If contained contacts mix like the eval set, 18% of them were problems an automation could have fixed. Credit only the other 82% to the agent:
- the middle scenario's saving becomes about **$32,800 a month** (82% of $40,050, minus $74)
- the rest is credited to turning on the automation the agent recommended

**Break-even:** the agent pays for its model cost once it contains about **1 contact in 1,080** (0.09%), because $0.0074 against $8.01 is roughly 1 to 1,080. At 2027 prices it's about 1 in 540. (v1, with about three model calls per answer, needed about 1 in 400.) The question isn't whether the model cost is worth paying. It's how well the agent resolves real contacts, and what it costs when it gets one wrong.

## What could erode this

- **Wrong advice.** A merchant acting on a bad answer comes back, or churns. This is measured at 0% of replies in the v2 release candidate, and 0 to 3% in v1 (target under 5%), and every rule must come from a cited help page.
- **Over-escalation.** Each needless handoff costs a full specialist contact. The evals caught one regression of this kind during development, and it was fixed (`docs/task11-before-after.md`).
- **Under-escalation.** Missing a suspension or an appeal is the costliest failure, which is why handoff recall has the strictest target (95%).
- **Reality differs from the evals.** The first production step should be a shadow pilot that measures real containment and accuracy before the agent faces merchants.

## Not counted, but real

- **Faster fixes recover ad revenue.** Every hour a product stays disapproved is lost revenue for the merchant and for Google. The agent answers immediately, any time of day. I found no public data on how long disapprovals last, so this isn't quantified.
- **Specialist time per case.** Cases arrive with the issues, the merchant's reasons, what was tried and the cited policy, so the specialist doesn't have to re-ask the merchant. The completeness metric (100% in v1 and v2) measures that directly.

## Recommendation

Run a **four-week shadow pilot**. The agent drafts answers and cases for real disapproval contacts, specialists review them, and nothing reaches merchants. Measure containment, wrong advice and handoff accuracy on real traffic. Go live if containment is above 30% (already about $24,000 a month per 10,000 contacts at Gartner's cost) and wrong advice stays under 5%.
