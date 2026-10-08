# 0005: One persona in the main journey, the merchant

_8 Oct 2026. Status: accepted (Vikrant)._

**Decision:**
- The main journey serves only the **merchant**.
- v1's "demo operator" role is removed. The merchant fixes data in an Edit product form inside the shell, as they would in the real product.
- The **specialist** view moves to a separate page behind a simple demo login, outside the merchant journey.
- After a handoff the merchant sees a **case preview**: exactly what the specialist will receive, including the merchant's own reasons.

**Why:**
- Testing the v1 app showed that playing three roles (merchant, demo operator, specialist) was confusing.
- The merchant is the user the agent exists for. One persona keeps the story and the UI simple.
- The case preview keeps the handoff's quality visible without switching persona. It's also good practice: the merchant can see what's being passed on about them.
- The specialist page still exists, because the handoff only proves its value if someone can act on the case.

**Measured by:**
- Case-preview fidelity: the preview equals the saved case, a 100% gate.
- Case completeness, as v1.

**Not chosen:**
- **Dropping the specialist view entirely:** the handoff would become invisible and unverifiable.
- **Keeping the role switch in the main journey:** that's the cognitive overload we're removing.
