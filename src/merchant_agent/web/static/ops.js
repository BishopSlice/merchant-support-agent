// The /ops dashboard: outcomes, quality, safety and operations, plus a per-conversation trace.

const $ = (selector) => document.querySelector(selector);
const state = { source: "live", days: 30 };

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child != null) node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

const pct = (v) => (v == null ? "No data" : `${Math.round(v * 100)}%`);
const secs = (v) => (v == null ? "No data" : `${v.toFixed(1)} s`);
const usd = (v, digits = 4) => (v == null ? "No data" : `$${v.toFixed(digits)}`);

async function get(path) {
  const response = await fetch(path, { credentials: "same-origin" });
  if (response.status === 401) throw Object.assign(new Error("signed out"), { status: 401 });
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  return response.json();
}

function tile(label, value, note, bad = false) {
  return el("div", { class: `tile${bad ? " tile--bad" : ""}` },
    el("div", { class: "tile__value" }, value),
    el("div", { class: "tile__label" }, label),
    note ? el("div", { class: "tile__note" }, note) : null);
}

function card(title, ...children) {
  return el("section", { class: "panel-card" }, el("h2", {}, title), ...children);
}

// Stacked bars by day: issue row (series 1) and Help (series 2). Eval traffic has one series.
function dayChart(byDay, source) {
  const series = source === "eval"
    ? [["other", "Eval conversations", "var(--series-1)"]]
    : [["issue_row", "From an issue row", "var(--series-1)"], ["help", "From Help", "var(--series-2)"]];
  if (!byDay.length) return el("p", { class: "note" }, "No conversations in this window.");
  const width = 640, height = 180, pad = { l: 32, r: 8, t: 8, b: 24 };
  const totals = byDay.map((d) => series.reduce((sum, [key]) => sum + (d[key] || 0), 0));
  const max = Math.max(1, ...totals);
  const band = (width - pad.l - pad.r) / byDay.length;
  const bar = Math.min(28, band * 0.6);
  const y = (v) => pad.t + (height - pad.t - pad.b) * (1 - v / max);
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "Conversations by day and entry point");
  const add = (tag, attrs) => {
    const node = document.createElementNS(ns, tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    svg.append(node);
    return node;
  };
  for (const tick of [0, Math.ceil(max / 2), max]) {
    add("line", { x1: pad.l, x2: width - pad.r, y1: y(tick), y2: y(tick), stroke: "var(--grid)", "stroke-width": 1 });
    add("text", { x: pad.l - 6, y: y(tick) + 4, "text-anchor": "end", "font-size": 11, fill: "#52514e" }).textContent = tick;
  }
  const chart = el("div", { class: "chart" });
  const tooltip = el("div", { class: "tooltip", hidden: "" });
  byDay.forEach((d, i) => {
    const cx = pad.l + band * i + band / 2;
    let base = 0;
    series.forEach(([key, , color], s) => {
      const value = d[key] || 0;
      if (!value) return;
      const top = y(base + value), bottom = y(base);
      const isTop = s === series.length - 1 || series.slice(s + 1).every(([k]) => !(d[k] || 0));
      // A 2px surface gap between stacked segments; only the top end is rounded.
      const h = Math.max(1, bottom - top - (base ? 2 : 0));
      add("rect", { x: cx - bar / 2, y: top, width: bar, height: h, rx: isTop ? 4 : 0, fill: color });
      if (isTop && h > 4) add("rect", { x: cx - bar / 2, y: top + h - 4, width: bar, height: 4, fill: color });
      base += value;
    });
    const hit = add("rect", { x: cx - band / 2, y: pad.t, width: band, height: height - pad.t - pad.b, fill: "transparent", tabindex: 0 });
    const label = `${d.day}: ${series.map(([key, name]) => `${name} ${d[key] || 0}`).join(", ")}`;
    hit.setAttribute("aria-label", label);
    const show = () => {
      tooltip.hidden = false;
      tooltip.textContent = label;
      tooltip.style.left = `${(cx / width) * 100}%`;
      tooltip.style.top = `${(y(totals[i]) / height) * 100}%`;
    };
    hit.addEventListener("mouseenter", show);
    hit.addEventListener("focus", show);
    hit.addEventListener("mouseleave", () => (tooltip.hidden = true));
    hit.addEventListener("blur", () => (tooltip.hidden = true));
    if (byDay.length <= 10 || i % Math.ceil(byDay.length / 8) === 0) {
      add("text", { x: cx, y: height - 6, "text-anchor": "middle", "font-size": 11, fill: "#52514e" }).textContent = d.day.slice(5);
    }
  });
  chart.append(svg, tooltip);
  const legend = series.length > 1
    ? el("div", { class: "legend" }, series.map(([, name, color]) => el("span", { style: `--c:${color}` }, name)))
    : null;
  return el("div", {}, legend, chart);
}

function hbars(counts, emptyText) {
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  if (!entries.length) return el("p", { class: "note" }, emptyText);
  const max = Math.max(...entries.map(([, v]) => v));
  return el("div", {}, entries.map(([name, value]) =>
    el("div", { class: "hbar" }, el("span", {}, name.replaceAll("_", " ")),
      el("div", { class: "hbar__track" }, el("div", { class: "hbar__fill", style: `width:${(value / max) * 100}%` })),
      el("span", {}, value))));
}

function render(data) {
  const alerts = $("#alerts");
  alerts.hidden = !data.alerts.length;
  alerts.replaceChildren(el("strong", {}, "Alerts"), el("ul", {}, data.alerts.map((a) => el("li", {}, a))));
  const notice = $("#sample-notice");
  notice.hidden = !data.small_sample;
  notice.textContent = `Small sample: ${data.conversations} conversation(s) in this window (fewer than 30). Read rates with care.`;

  const o = data.outcomes, q = data.quality, s = data.safety, ops = data.operations;
  const label = data.source === "eval" ? "Eval traffic" : "Live traffic";
  $("#panels").replaceChildren(
    card(`1. Outcomes (${label})`,
      el("div", { class: "tiles" },
        tile("Conversations", data.conversations),
        tile("Handoff rate", pct(o.handoff_rate)),
        tile("Thumbs up / down", `${o.feedback.up} / ${o.feedback.down}`),
        tile("Estimated cost avoided", usd(o.cost_avoided.usd, 2), `${o.cost_avoided.contained} conversation(s) without a handoff`),
      ),
      el("p", { class: "note" }, o.cost_avoided.assumption),
      el("p", { class: "note" }, `Resolution: ${data.not_measured.resolution}`),
      el("div", { class: "grid-2" },
        el("div", {}, el("h3", {}, "Conversations by day"), dayChart(o.by_day, data.source)),
        el("div", {}, el("h3", {}, "Handoff reasons"), hbars(o.handoff_reasons, "No handoffs in this window.")),
      ),
    ),
    card("2. Quality",
      el("div", { class: "tiles" },
        tile("Conversations graded", q.graded, "About 10% of live conversations, within a daily budget"),
        tile("Wrong advice rate (graded)", pct(q.wrong_advice_rate), "Target under 5%", q.wrong_advice_rate > 0.05),
        tile("Case completeness (graded)", pct(q.case_completeness), "Target 90% or higher", q.case_completeness != null && q.case_completeness < 0.9),
      ),
    ),
    card("3. Safety",
      el("div", { class: "tiles" },
        tile("Write calls", s.write_calls, "Must be 0 (hard gate)", s.write_calls > 0),
        tile("Graceful after a tool failure", s.after_tool_failure.graceful),
        tile("Invented data after a tool failure", s.after_tool_failure.invented, "Must be 0", s.after_tool_failure.invented > 0),
        tile("Personal data blocked in cases", s.personal_data_blocked),
      ),
      el("p", { class: "note" }, `Injection: ${data.not_measured.injection}`),
      el("p", { class: "note" }, `Safety blocks: ${data.not_measured.safety_blocks}`),
    ),
    card("4. Operations",
      el("div", { class: "tiles" },
        tile("Latency p50 per turn", secs(ops.latency_p50), "Target 8 s or less", ops.latency_p50 > 8),
        tile("Latency p95 per turn", secs(ops.latency_p95), "Target 20 s or less", ops.latency_p95 > 20),
        tile("Cost per conversation", usd(ops.cost_per_conversation), "Target $0.03 or less", ops.cost_per_conversation > 0.03),
        tile("Tokens per conversation", ops.tokens_per_conversation == null ? "No data" : Math.round(ops.tokens_per_conversation)),
        tile("Spend today", usd(ops.spend_today, 2), "Agent and grading"),
      ),
      el("h3", {}, "Tool errors"),
      hbars(ops.tool_errors, "No tool errors in this window."),
      el("p", { class: "note" }, `Agent versions: ${ops.agent_versions.join(", ") || "none"}. Models: ${ops.models.join(", ") || "none"}.`),
    ),
  );
}

async function renderConversations() {
  const { conversations } = await get(`/api/ops/conversations?source=${state.source}`);
  const box = $("#conversations");
  if (!conversations.length) {
    box.replaceChildren(el("p", { class: "note" }, "No conversations yet."));
    return;
  }
  box.replaceChildren(el("table", { class: "list" },
    el("thead", {}, el("tr", {}, ["Started", "Entry", "Turns", "Handoffs", "Feedback", ""].map((h) => el("th", { scope: "col" }, h)))),
    el("tbody", {}, conversations.map((c) => el("tr", {},
      el("td", {}, new Date(c.started_at).toLocaleString()),
      el("td", {}, (c.entry_point || c.label || "").replaceAll("_", " ")),
      el("td", {}, c.turns),
      el("td", {}, c.handoffs),
      el("td", {}, c.feedback == null ? "" : c.feedback > 0 ? "Thumbs up" : "Thumbs down"),
      el("td", {}, el("md-text-button", { onclick: () => showTrace(c.id) }, "Trace")),
    ))),
  ));
}

async function showTrace(id) {
  const t = await get(`/api/ops/conversations/${encodeURIComponent(id)}`);
  const pretty = (text) => {
    try { return JSON.stringify(JSON.parse(text), null, 1); } catch { return text || ""; }
  };
  $("#trace").hidden = false;
  $("#trace-body").replaceChildren(
    el("p", { class: "note" }, `${t.source} conversation, agent ${t.agent_version}, ${t.model}, entry ${t.entry_point || t.label || "n/a"}`),
    ...t.turns.map((turn, i) => el("div", { class: "trace-turn" },
      el("p", {}, el("strong", {}, `Turn ${i + 1}`), ` (${turn.seconds.toFixed(1)} s, $${turn.cost_usd.toFixed(4)})`),
      el("p", {}, el("strong", {}, "Merchant: "), turn.merchant ?? "(text removed after 30 days)"),
      el("p", {}, el("strong", {}, "Agent: "), turn.reply ?? "(text removed after 30 days)"),
      el("p", { class: "note" }, `Checks: write calls ${turn.checks.write_calls?.length || 0}, tool failed ${turn.checks.tool_failed ? "yes" : "no"}, invented ${turn.checks.invented?.length || 0}`),
      turn.tool_calls.map((c) => el("details", {},
        el("summary", {}, `${c.ok ? "OK" : "Failed"}: ${c.name}`),
        el("pre", {}, `args: ${pretty(c.args)}\n${c.error ? `error: ${c.error}\n` : ""}response: ${pretty(c.response)}`))),
    )),
    t.grades.length ? el("p", {}, `Latest grade: wrong advice ${pct(t.grades.at(-1).wrong_advice_rate)}, completeness ${t.grades.at(-1).completeness || "n/a"}`) : null,
  );
  $("#trace").scrollIntoView({ behavior: "smooth" });
}

async function refresh() {
  try {
    const data = await get(`/api/ops/summary?source=${state.source}&days=${state.days}`);
    $("#login").hidden = true;
    $("#dashboard").hidden = false;
    render(data);
    await renderConversations();
  } catch (error) {
    if (error.status !== 401) $("#login-error").textContent = error.message;
  }
}

$("#login").addEventListener("submit", async (event) => {
  event.preventDefault();
  const response = await fetch("/api/ops/login", {
    method: "POST", credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code: $("#code").value }),
  });
  if (!response.ok) {
    $("#login-error").textContent = response.status === 403 ? "The ops dashboard is off on this server." : "That code isn't right.";
    return;
  }
  refresh();
});
$("#code").addEventListener("keydown", (e) => { if (e.key === "Enter") $("#login").requestSubmit(); });
for (const radio of document.querySelectorAll('md-radio[name="source"]')) {
  radio.addEventListener("change", () => { state.source = radio.value; $("#trace").hidden = true; refresh(); });
}
$("#days").addEventListener("change", () => { state.days = Number($("#days").value); refresh(); });

refresh();
