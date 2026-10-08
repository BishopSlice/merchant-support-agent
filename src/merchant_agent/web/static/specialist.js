// The specialist page: a demo login, then every escalated case in full.

const $ = (selector) => document.querySelector(selector);

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  for (const child of children.flat()) {
    if (child != null) node.append(child instanceof Node ? child : document.createTextNode(child));
  }
  return node;
}

const list = (items) => (items?.length ? el("ul", {}, items.map((i) => el("li", {}, i))) : "None recorded");

const AUTOMATIONS = [
  ["price_updates", "Price updates"],
  ["availability_updates", "Availability updates"],
  ["image_improvements", "Image improvements"],
  ["shipping_improvements", "Shipping improvements"],
];

function renderCase(c) {
  const automation = c.automation
    ? AUTOMATIONS.map(([key, label]) => `${label}: ${c.automation[key] ? "on" : "off"}`).join(", ")
    : "Not available";
  return el("article", { class: "case" },
    el("h2", {}, `${c.case_id}: ${c.reason.replaceAll("_", " ")}`),
    el("p", { class: "meta" }, `Store ${c.store_id}, created ${new Date(c.created_at).toLocaleString()}`),
    el("dl", {},
      el("dt", {}, "Merchant's request"), el("dd", {}, c.merchant_request),
      el("dt", {}, "Merchant's reasons"), el("dd", {}, list(c.merchant_reasons)),
      el("dt", {}, "Account issues"), el("dd", {}, list(c.account_issues)),
      el("dt", {}, "Issues found"), el("dd", {}, list(c.issues_found)),
      el("dt", {}, "Already tried"), el("dd", {}, list(c.already_tried)),
      el("dt", {}, "Automations"), el("dd", {}, automation),
      el("dt", {}, "Cited help docs"), el("dd", {}, list(c.cited_doc_ids)),
      el("dt", {}, "Suggested next step"), el("dd", {}, c.suggested_next_step),
    ),
  );
}

async function loadCases() {
  const response = await fetch("/api/cases", { credentials: "same-origin" });
  if (response.status === 401) return false;
  const { cases } = await response.json();
  $("#login").hidden = true;
  const container = $("#cases");
  container.replaceChildren(...(cases.length ? cases.map(renderCase) : [el("p", {}, "No cases yet. Hand off a conversation from the merchant view first.")]));
  return true;
}

$("#login").addEventListener("submit", async (event) => {
  event.preventDefault();
  const response = await fetch("/api/specialist/login", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code: $("#code").value }),
  });
  if (!response.ok) {
    $("#login-error").textContent = "That code isn't right.";
    return;
  }
  $("#login-error").textContent = "";
  await loadCases();
});

// Material text fields don't submit their form on Enter by themselves.
$("#code").addEventListener("keydown", (event) => {
  if (event.key === "Enter") $("#login").requestSubmit();
});

loadCases();
