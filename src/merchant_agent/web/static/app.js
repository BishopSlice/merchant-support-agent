// The merchant shell: Needs attention table, Edit product dialog and the assistant side panel.

const $ = (selector) => document.querySelector(selector);
const state = { mode: "replay", products: [], context: null, busy: false, editing: null };

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof body.detail === "string"
      ? body.detail
      : response.status === 422 ? "That message couldn't be sent. Keep it under 2,000 characters." : "Something went wrong.";
    throw Object.assign(new Error(detail), { status: response.status });
  }
  return body;
}

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "class") node.className = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child != null) node.append(child instanceof Node ? child : document.createTextNode(child));
  }
  return node;
}

function icon(name) {
  return el("span", { class: "material-symbols-outlined", "aria-hidden": "true" }, name);
}

function toast(message) {
  const node = $("#toast");
  node.textContent = message;
  node.classList.add("show");
  setTimeout(() => node.classList.remove("show"), 3000);
}

// --- Minimal, safe Markdown for agent replies: escape first, then a few inline forms. ---

function escapeHtml(text) {
  return text.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

function inline(text) {
  return escapeHtml(text)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\[([^\]]+)\]\((https:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
}

function renderMarkdown(text) {
  const html = [];
  let list = null;
  for (const raw of text.split("\n")) {
    const line = raw.trim();
    const item = line.match(/^(?:[*-]|\d+\.)\s+(.*)$/);
    if (item) {
      if (!list) { list = []; }
      list.push(`<li>${inline(item[1])}</li>`);
      continue;
    }
    if (list) { html.push(`<ul>${list.join("")}</ul>`); list = null; }
    if (!line || /^-{3,}$/.test(line)) continue;
    const heading = line.match(/^#{1,6}\s+(.*)$/);
    html.push(heading ? `<p><strong>${inline(heading[1])}</strong></p>` : `<p>${inline(line)}</p>`);
  }
  if (list) html.push(`<ul>${list.join("")}</ul>`);
  return html.join("");
}

// --- Needs attention ---

const SEVERITY = {
  DISAPPROVED: { label: "Disapproved", icon: "block", cls: "severity--disapproved" },
  DEMOTED: { label: "Warning: fewer shoppers", icon: "trending_down", cls: "severity--demoted" },
};

const AUTOMATIONS = [
  ["price_updates", "Price updates"],
  ["availability_updates", "Availability updates"],
  ["image_improvements", "Image improvements"],
  ["shipping_improvements", "Shipping improvements"],
];

async function loadIssues() {
  const data = await api("/api/issues");
  state.products = data.products;
  $("#stat-disapproved").textContent = data.stats.disapprovedCount ?? "0";
  const demoted = data.products.filter((p) => p.issues.some((i) => i.severity === "DEMOTED")).length;
  $("#stat-demoted").textContent = String(demoted);

  const banner = $("#account-banner");
  banner.replaceChildren();
  banner.hidden = data.accountIssues.length === 0;
  for (const issue of data.accountIssues) {
    banner.append(icon("gpp_bad"), el("div", {}, el("strong", {}, `Account issue: ${issue.title}`), issue.detail || ""));
  }

  const automation = $("#automation");
  automation.replaceChildren(
    ...AUTOMATIONS.map(([key, label]) => {
      const on = data.automation?.[key];
      return el("li", {}, label, el("span", { class: on ? "on" : "off" }, on ? "On" : "Off"));
    }),
  );

  const body = $("#issues-body");
  body.replaceChildren();
  const rows = data.products.flatMap((product) => product.issues.map((issue) => [product, issue]));
  if (rows.length === 0) {
    body.append(el("tr", {}, el("td", { colspan: "4" }, "Nothing needs attention. Every product can show.")));
    return;
  }
  rows.sort((a, b) => (a[1].severity === b[1].severity ? 0 : a[1].severity === "DISAPPROVED" ? -1 : 1));
  for (const [product, issue] of rows) {
    const severity = SEVERITY[issue.severity] || { label: issue.severity, icon: "info", cls: "" };
    body.append(
      el("tr", {},
        el("td", {}, el("div", { class: "product-title", title: product.title }, product.title), el("div", { class: "offer-id" }, product.offerId)),
        el("td", {}, el("div", {}, issue.description), el("div", { class: "offer-id" }, issue.detail || "")),
        el("td", {}, el("span", { class: `severity ${severity.cls}` }, icon(severity.icon), severity.label)),
        el("td", { class: "actions" }, el("div", { class: "actions__stack" },
          el("md-text-button", { onclick: () => openEdit(product), "aria-label": `Edit ${product.title}` }, "Edit"),
          el("md-filled-tonal-button", {
            onclick: () => openPanel({ offer_id: product.offerId, issue_code: issue.code, title: product.title, description: issue.description }),
            "aria-label": `Help me fix this: ${issue.description} on ${product.title}`,
          }, "Help me fix this"),
        )),
      ),
    );
  }
}

// --- Edit product dialog ---

function openEdit(product) {
  state.editing = product;
  $("#edit-offer").textContent = product.offerId;
  $("#edit-error").textContent = "";
  const form = $("#edit-form");
  for (const [name, value] of Object.entries(product.edit)) {
    const field = form.querySelector(`[name="${name}"]`);
    if (field) field.value = value ?? "";
  }
  $("#edit-dialog").show();
}

async function saveEdit() {
  const product = state.editing;
  const form = $("#edit-form");
  const changes = {};
  for (const [name, original] of Object.entries(product.edit)) {
    const field = form.querySelector(`[name="${name}"]`);
    if (field && field.value !== (original ?? "")) changes[name] = field.value;
  }
  try {
    if (Object.keys(changes).length) {
      await api(`/api/products/${encodeURIComponent(product.offerId)}`, { method: "POST", body: JSON.stringify(changes) });
    }
    $("#edit-dialog").close();
    toast(`Saved ${product.offerId}. Ask the assistant to check again.`);
    await loadIssues();
  } catch (error) {
    $("#edit-error").textContent = error.status === 422 ? "One of the values isn't in the expected format." : error.message;
  }
}

// --- Assistant side panel ---

function openPanel(context = null) {
  state.context = context;
  const panel = $("#panel");
  panel.hidden = false;
  $(".layout").classList.add("panel-open");
  $("#messages").replaceChildren();
  const chip = $("#context-chip");
  chip.hidden = !context;
  chip.textContent = context ? `About: ${context.description}, ${context.title} (${context.offer_id})` : "";
  state.newConversation = true;
  renderMode();
  $("#panel-close").focus();
}

function closePanel() {
  $("#panel").hidden = true;
  $(".layout").classList.remove("panel-open");
  $("#help-button").focus();
}

function addMessage(kind, content) {
  const item = el("li", { class: `msg msg--${kind}` });
  if (kind === "agent") item.innerHTML = renderMarkdown(content);
  else item.textContent = content;
  $("#messages").append(item);
  item.scrollIntoView({ block: "end" });
  return item;
}

function addSteps(steps) {
  if (!steps?.length) return;
  $("#messages").append(el("li", {}, el("details", { class: "steps-box" },
    el("summary", {}, `Checked your account (${steps.length} steps)`),
    el("ul", { class: "steps", "aria-label": "What the assistant checked" }, steps.map((s) => el("li", {}, s))))));
}

function addFeedback(turnId) {
  const status = el("span", { class: "feedback__status", role: "status" });
  const vote = async (value, button) => {
    try {
      await api("/api/feedback", { method: "POST", body: JSON.stringify({ turn_id: turnId, value }) });
      for (const b of row.querySelectorAll("md-icon-button")) b.selected = b === button;
      status.textContent = "Thanks for the feedback.";
    } catch (error) {
      status.textContent = error.message;
    }
  };
  const button = (value, iconName, label) => {
    const b = el("md-icon-button", { toggle: "", "aria-label": label },
      icon(iconName), el("span", { slot: "selected", class: "material-symbols-outlined filled", "aria-hidden": "true" }, iconName));
    b.addEventListener("click", () => vote(value, b));
    return b;
  };
  const row = el("li", { class: "feedback" },
    button(1, "thumb_up", "This reply was helpful"),
    button(-1, "thumb_down", "This reply was not helpful"),
    status);
  $("#messages").append(row);
}

function addPreview(caseResult) {
  if (!caseResult?.preview) return;
  const p = caseResult.preview;
  const list = (items) => (items?.length ? el("ul", {}, items.map((i) => el("li", {}, i))) : "None");
  const automation = p.automation
    ? AUTOMATIONS.map(([key, label]) => `${label}: ${p.automation[key] ? "on" : "off"}`).join(", ")
    : "Not available";
  const card = $("#messages").appendChild(
    el("li", { class: "preview", "aria-label": "Case preview" },
      el("h3", {}, `What the specialist will see: case ${caseResult.case_id}`),
      el("p", { class: "note" }, "This is exactly what was saved. You won't need to repeat any of it."),
      el("dl", {},
        el("dt", {}, "Reason"), el("dd", {}, p.reason.replaceAll("_", " ")),
        el("dt", {}, "Your request"), el("dd", {}, p.merchant_request),
        el("dt", {}, "Your reasons"), el("dd", {}, list(p.merchant_reasons)),
        el("dt", {}, "Issues"), el("dd", {}, list([...(p.account_issues || []), ...p.issues_found])),
        el("dt", {}, "Affected products"), el("dd", {}, list(Object.entries(p.product_issues || {}).map(([code, ids]) => `${code.replaceAll("_", " ")}: ${ids.join(", ")}`))),
        el("dt", {}, "Already tried"), el("dd", {}, list(p.already_tried)),
        el("dt", {}, "Automations"), el("dd", {}, automation),
        el("dt", {}, "Next step"), el("dd", {}, p.suggested_next_step),
      ),
    ),
  );
  card.scrollIntoView({ block: "nearest" });
}

function setMode(mode) {
  state.mode = mode;
  renderMode();
}

async function renderMode() {
  const live = state.mode === "live";
  for (const radio of document.querySelectorAll('md-radio[name="mode"]')) radio.checked = radio.value === state.mode;
  $("#access").hidden = !live;
  $("#chat-form").hidden = !live;
  const picker = $("#replay-picker");
  picker.hidden = live;
  if (live) return;
  picker.replaceChildren(el("p", {}, "Watch a recorded conversation with the real agent. No code needed."));
  try {
    const { replays } = await api("/api/replays");
    if (!replays.length) picker.append(el("p", {}, "No replays are recorded yet. Use Live mode with an access code."));
    for (const replay of replays) {
      picker.append(el("md-outlined-button", { onclick: () => playReplay(replay.id) }, replay.title));
    }
  } catch {
    picker.append(el("p", {}, "Couldn't load the replays."));
  }
}

const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function playReplay(id) {
  const replay = await api(`/api/replays/${encodeURIComponent(id)}`);
  $("#messages").replaceChildren();
  const chip = $("#context-chip");
  chip.hidden = !replay.entry_context;
  if (replay.entry_context) {
    chip.textContent = `Recorded from the issue row for ${replay.entry_context.product} (${replay.entry_context.issue_code.replaceAll("_", " ")})`;
  }
  for (const turn of replay.turns) {
    if (turn.fix) {
      $("#messages").append(el("li", { class: "working" }, `The merchant edited the products to fix the ${turn.fix.replaceAll("_", " ")}.`));
    }
    addMessage("merchant", turn.merchant);
    const working = addWorking();
    await pause(900);
    working.remove();
    addSteps(turn.steps);
    addMessage("agent", turn.reply);
    addPreview(turn.case);
    await pause(600);
  }
}

function addWorking() {
  const item = el("li", { class: "working" }, el("md-circular-progress", { indeterminate: "", "aria-label": "Working" }), "Checking your account…");
  $("#messages").append(item);
  return item;
}

async function sendMessage(event) {
  event.preventDefault();
  const input = $("#chat-input");
  const message = input.value.trim();
  if (!message || state.busy) return;
  const code = $("#access-code").value.trim();
  if (!code) {
    addMessage("error", "Enter the access code to use live chat.");
    return;
  }
  sessionStorage.setItem("accessCode", code);
  state.busy = true;
  $("#send").disabled = true;
  input.value = "";
  addMessage("merchant", message);
  const working = addWorking();
  const body = { message, new_conversation: Boolean(state.newConversation) };
  if (state.newConversation && state.context) {
    body.entry_context = { offer_id: state.context.offer_id, issue_code: state.context.issue_code };
  }
  try {
    const result = await api("/api/chat", { method: "POST", body: JSON.stringify(body), headers: { "X-Access-Code": code } });
    state.newConversation = false;
    working.remove();
    addSteps(result.steps);
    addMessage("agent", result.reply);
    addFeedback(result.turn_id);
    addPreview(result.case);
    $("#remaining").textContent = `${result.remaining} messages left in this session`;
  } catch (error) {
    working.remove();
    addMessage("error", error.message);
  } finally {
    state.busy = false;
    $("#send").disabled = false;
    input.focus();
  }
}

function init() {
  $("#help-button").addEventListener("click", () => openPanel(null));
  $("#panel-close").addEventListener("click", closePanel);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !$("#panel").hidden && !$("#edit-dialog").open) closePanel();
  });
  for (const radio of document.querySelectorAll('md-radio[name="mode"]')) {
    radio.addEventListener("change", () => setMode(radio.value));
  }
  $("#chat-form").addEventListener("submit", sendMessage);
  $("#chat-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) sendMessage(e);
  });
  $("#edit-save").addEventListener("click", saveEdit);
  $("#edit-cancel").addEventListener("click", () => $("#edit-dialog").close());
  $("#access-code").value = sessionStorage.getItem("accessCode") || "";
  loadIssues().catch((error) => {
    $("#issues-body").replaceChildren(el("tr", {}, el("td", { colspan: "4" }, `Couldn't load the issues: ${error.message}`)));
  });
}

init();
