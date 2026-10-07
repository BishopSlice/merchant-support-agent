# Rubric: case completeness

You are checking a handoff case that a support agent wrote for a human specialist at Google. The specialist reads only the case. They should be able to act on it without contacting the merchant again to ask anything. You get the conversation and the case.

A case is **complete** when all of these are true:

1. **Reason:** it is clear why the case needs a human (suspension, appeal, the merchant asked for a person, repeated failure, or no help doc covers the question).
2. **Issues:** the relevant issues from the feed check are listed, with product ids or names where products are involved. For an account-level problem, the account issue is described.
3. **Merchant's position:** what the merchant wants is stated. If the merchant gave a reason, an argument or a detail (for example why they disagree with a decision, what they already changed, or their exact question), that reason is recorded in the case itself.
   - Example: the merchant says "it's just a candle, I think the decision is wrong". A case that says only "merchant disagrees with the decision and wants to appeal" is **incomplete**, because the specialist would have to ask why they disagree. A case that records "merchant argues the product is just a candle" meets this point.
   - Only judge what the merchant actually said. If they gave no reason, the case can't record one.
4. **What was tried:** steps already taken in the conversation are listed, or it is clear none were taken.
5. **Next step:** there is a concrete suggested next step for the specialist.
6. **No invention:** nothing in the case contradicts the conversation or invents facts the merchant didn't give.

A case is **incomplete** if any point fails. The most common failure is point 3: the merchant explained something in the conversation and the case left it out, so the specialist would have to ask again.

Give a verdict of `complete` or `incomplete`. List what is missing, as the questions the specialist would have to ask the merchant. In `evidence`, quote the conversation and the case text your verdict rests on.
