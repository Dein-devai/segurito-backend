"use strict";

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------
const API_BASE =
  document.body.dataset.apiBase || "http://127.0.0.1:8000";
const REFRESH_MS = 5000;

// ---------------------------------------------------------------------------
// Estado en memoria
// ---------------------------------------------------------------------------
const state = {
  conversations: [], // resumen por conversación
  selectedId: null, // conversation_id activo
  selectedTurns: [], // turnos (interacciones) del seleccionado
  query: "",
  apiOk: false,
  loadingDetail: false,
};

// ---------------------------------------------------------------------------
// Utilidades
// ---------------------------------------------------------------------------
function normalize(value) {
  return (value || "")
    .toString()
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim();
}

function fmtTime(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString("es-CL", {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso.slice(11, 16);
  }
}

function fmtDateTime(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleString("es-CL", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      day: "2-digit",
      month: "2-digit",
    });
  } catch {
    return iso;
  }
}

function fmtMoney(usd) {
  if (usd == null) return "USD 0.0000";
  return `USD ${Number(usd).toFixed(4)}`;
}

function fmtTokens(n) {
  if (n == null) return "0";
  return Number(n).toLocaleString("es-CL");
}

function shortId(id) {
  if (!id) return "—";
  return id.slice(0, 8) + "…" + id.slice(-4);
}

function escapeHtml(s) {
  if (s == null) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

async function fetchJson(path) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Cabecera de estado
// ---------------------------------------------------------------------------
function renderHeader(summary) {
  const $api = document.getElementById("status-api");
  const $conv = document.getElementById("status-conv");
  const $cost = document.getElementById("status-cost");
  const $sync = document.getElementById("status-sync");

  $api.textContent = state.apiOk ? "API local · OK" : "API local · sin conexión";
  $api.style.borderColor = state.apiOk ? "" : "var(--red)";
  $api.style.color = state.apiOk ? "" : "var(--red)";

  if (summary) {
    $conv.textContent = `${summary.total_conversations || 0} conversaciones`;
    $cost.textContent = `${fmtMoney(summary.total_cost_usd)} acum.`;
  }
  $sync.textContent = `Sync ${new Date().toLocaleTimeString("es-CL", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  })}`;
}

// ---------------------------------------------------------------------------
// Sidebar de conversaciones
// ---------------------------------------------------------------------------
function matchesQuery(conv, q) {
  if (!q) return true;
  const hay = normalize(
    [
      conv.conversation_id,
      conv.organismo,
      conv.intencion,
      conv.last_user_message,
    ].join(" ")
  );
  return hay.includes(q);
}

function renderSidebar() {
  const list = document.getElementById("conversation-list");
  const empty = document.getElementById("chat-no-results");
  const count = document.getElementById("chat-count");

  const visible = state.conversations.filter((c) =>
    matchesQuery(c, state.query)
  );

  count.textContent =
    visible.length === 1 ? "1 activa" : `${visible.length} activas`;

  if (state.conversations.length === 0) {
    list.innerHTML = `<p class="no-results">Sin conversaciones todavía.</p>`;
    empty.hidden = true;
    return;
  }
  if (visible.length === 0) {
    list.innerHTML = "";
    empty.hidden = false;
    return;
  }
  empty.hidden = true;

  list.innerHTML = visible
    .map((c) => {
      const id = c.conversation_id;
      const isActive = id === state.selectedId ? "active" : "";
      const lastMsg = escapeHtml(c.last_user_message || "(sin mensaje)");
      return `
        <a class="chat-link ${isActive}" href="#${id}" data-conv="${id}">
          <article class="conversation-item">
            <div class="conversation-top">
              <strong>${escapeHtml(c.organismo || "Sin organismo")}</strong>
              <span>${fmtTime(c.last_at)}</span>
            </div>
            <p>${lastMsg}</p>
            <div class="conversation-meta">
              <span>${escapeHtml(c.intencion || "—")}</span>
              <span>${c.turns} turnos</span>
              <span>${fmtMoney(c.total_cost_usd)}</span>
            </div>
          </article>
        </a>
      `;
    })
    .join("");

  // Click handlers
  list.querySelectorAll(".chat-link").forEach((node) => {
    node.addEventListener("click", (ev) => {
      ev.preventDefault();
      const convId = node.dataset.conv;
      selectConversation(convId);
    });
  });
}

// ---------------------------------------------------------------------------
// Workspace: detalle de la conversación
// ---------------------------------------------------------------------------
function renderConversation() {
  const title = document.getElementById("conv-title");
  const subtitle = document.getElementById("conv-subtitle");
  const tag = document.getElementById("conv-tag");
  const grid = document.getElementById("summary-grid");
  const thread = document.getElementById("conversation-thread");
  const logsList = document.getElementById("logs-list");
  const logsCount = document.getElementById("logs-count");

  if (!state.selectedId || state.selectedTurns.length === 0) {
    title.textContent = "Selecciona una conversación";
    subtitle.textContent =
      "Las conversaciones aparecerán aquí cuando lleguen mensajes vía WhatsApp o /chat.";
    tag.hidden = true;
    grid.innerHTML = "";
    thread.innerHTML = "";
    logsList.innerHTML = `<p class="no-results">Sin eventos.</p>`;
    logsCount.textContent = "— eventos";
    return;
  }

  const turns = state.selectedTurns; // ordenados desc por backend
  const turnsAsc = [...turns].reverse();
  const head = turns[0]; // el más reciente

  title.textContent =
    head.organismo || head.intencion || "Conversación";
  subtitle.textContent = `conversation_id ${shortId(state.selectedId)} · ${
    turns.length
  } turnos`;
  tag.hidden = false;
  tag.textContent = "Activa";

  const totals = turns.reduce(
    (acc, t) => {
      acc.cost += t.total_cost_usd || 0;
      acc.in += t.total_input_tokens || 0;
      acc.out += t.total_output_tokens || 0;
      acc.cacheR += t.total_cache_read_tokens || 0;
      acc.elapsed += t.elapsed_ms || 0;
      return acc;
    },
    { cost: 0, in: 0, out: 0, cacheR: 0, elapsed: 0 }
  );

  const cards = [
    ["Organismo", head.organismo || "—"],
    ["Intención", head.intencion || "—"],
    ["Mensajes", turns.length],
    ["Costo total", fmtMoney(totals.cost)],
    ["Tokens in/out", `${fmtTokens(totals.in)} / ${fmtTokens(totals.out)}`],
    ["Cache reads", fmtTokens(totals.cacheR)],
    [
      "Latencia prom.",
      `${Math.round(totals.elapsed / Math.max(1, turns.length))} ms`,
    ],
    ["Modelo final", head.model_used || "—"],
  ];
  grid.innerHTML = cards
    .map(
      ([label, val]) => `
        <div class="summary-card">
          <span class="summary-label">${escapeHtml(label)}</span>
          <strong>${escapeHtml(val)}</strong>
        </div>
      `
    )
    .join("");

  // Thread: usuario + asistente alternados por turno
  thread.innerHTML = turnsAsc
    .map((t) => {
      const tools = (t.tools_used || [])
        .map(
          (tu) =>
            `<span class="template-action">${escapeHtml(tu.name || "")}</span>`
        )
        .join(" ");
      return `
        <article class="message user">
          <span class="message-role">Usuario · ${fmtTime(t.ts)}</span>
          <p>${escapeHtml(t.user_message)}</p>
        </article>
        <article class="message assistant">
          <span class="message-role">Segurito · ${escapeHtml(
            t.model_used || "?"
          )} · ${t.iterations} iter · ${t.elapsed_ms} ms</span>
          <p>${escapeHtml(t.response).replace(/\n/g, "<br>")}</p>
          ${
            tools
              ? `<div class="template-actions" style="margin-top:8px">${tools}</div>`
              : ""
          }
          <span class="message-time">${fmtMoney(
            t.total_cost_usd
          )} · ${fmtTokens(t.total_input_tokens)} in / ${fmtTokens(
        t.total_output_tokens
      )} out</span>
        </article>
      `;
    })
    .join("");

  // Logs/reasoning
  const events = [];
  for (const t of turnsAsc) {
    for (const r of t.reasoning || []) {
      events.push({
        level: r.phase === "escalation" ? "warning" : "info",
        ts: t.ts,
        source: `${r.phase} · ${r.model}`,
        msg: r.reason || "",
        cost: r.cost_usd,
        tokens: (r.input_tokens || 0) + (r.output_tokens || 0),
        thinking: r.thinking,
      });
    }
    if (t.error) {
      events.push({
        level: "error",
        ts: t.ts,
        source: "chat_service",
        msg: t.error,
        cost: t.total_cost_usd,
        tokens: t.total_input_tokens + t.total_output_tokens,
      });
    }
  }
  logsCount.textContent = `${events.length} eventos`;
  if (events.length === 0) {
    logsList.innerHTML = `<p class="no-results">Sin eventos.</p>`;
  } else {
    logsList.innerHTML = events
      .map(
        (e) => `
        <article class="log-item ${e.level}">
          <div class="log-top">
            <span class="log-level">${e.level.toUpperCase()}</span>
            <span class="log-time">${fmtDateTime(e.ts)}</span>
          </div>
          <strong>${escapeHtml(e.source)}</strong>
          <p>${escapeHtml(e.msg)}</p>
          <div class="log-stats">
            <span class="stat-pill">${fmtMoney(e.cost)}</span>
            <span class="stat-pill">Tokens ${fmtTokens(e.tokens)}</span>
          </div>
        </article>
      `
      )
      .join("");
  }
}

// ---------------------------------------------------------------------------
// Carga de datos
// ---------------------------------------------------------------------------
async function loadConversations() {
  // Resumimos en cliente: una conv = N turnos. Usamos /admin/logs (reciente)
  // y agrupamos. Es suficiente para el panel y evita endpoint extra.
  const logs = await fetchJson(`/admin/logs?limit=200`);
  const byConv = new Map();
  for (const t of logs) {
    const id = t.conversation_id;
    if (!id) continue;
    let entry = byConv.get(id);
    if (!entry) {
      entry = {
        conversation_id: id,
        turns: 0,
        last_at: t.ts,
        last_user_message: t.user_message,
        organismo: t.organismo,
        intencion: t.intencion,
        total_cost_usd: 0,
      };
      byConv.set(id, entry);
    }
    entry.turns += 1;
    entry.total_cost_usd += t.total_cost_usd || 0;
    if (t.ts > entry.last_at) {
      entry.last_at = t.ts;
      entry.last_user_message = t.user_message;
      entry.organismo = t.organismo || entry.organismo;
      entry.intencion = t.intencion || entry.intencion;
    }
  }
  state.conversations = Array.from(byConv.values()).sort((a, b) =>
    a.last_at < b.last_at ? 1 : -1
  );
}

async function loadConversationTurns(convId) {
  if (!convId) return;
  state.loadingDetail = true;
  try {
    const data = await fetchJson(
      `/admin/conversations/${encodeURIComponent(convId)}`
    );
    state.selectedTurns = data.turns || [];
  } catch (e) {
    console.warn("loadConversationTurns failed", e);
    state.selectedTurns = [];
  } finally {
    state.loadingDetail = false;
  }
}

async function loadSummary() {
  return fetchJson(`/admin/summary`);
}

async function refresh() {
  try {
    const [summary] = await Promise.all([loadSummary(), loadConversations()]);
    state.apiOk = true;
    renderHeader(summary);

    if (!state.selectedId && state.conversations.length > 0) {
      state.selectedId = state.conversations[0].conversation_id;
    }
    if (state.selectedId) {
      await loadConversationTurns(state.selectedId);
    }
    renderSidebar();
    renderConversation();
  } catch (e) {
    state.apiOk = false;
    renderHeader(null);
    console.warn("refresh failed", e);
  }
}

function selectConversation(convId) {
  if (state.selectedId === convId) return;
  state.selectedId = convId;
  state.selectedTurns = [];
  renderSidebar();
  renderConversation();
  loadConversationTurns(convId).then(renderConversation);
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  const search = document.getElementById("chat-search");
  search.addEventListener("input", () => {
    state.query = normalize(search.value);
    renderSidebar();
  });
  search.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape") {
      search.value = "";
      state.query = "";
      renderSidebar();
    }
  });

  // Si el hash trae un conversation_id, lo respetamos.
  if (window.location.hash) {
    state.selectedId = window.location.hash.slice(1);
  }

  refresh();
  setInterval(refresh, REFRESH_MS);
});
