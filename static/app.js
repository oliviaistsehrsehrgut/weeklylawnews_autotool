const state = {
  sessionId: "",
  items: [],
  pending: {},
  llmConfig: { base_url: "", model: "", api_key: "" },
};
let draggedId = "";
const REFRESH_WARNING = "\u5c06\u6e05\u9664\u5df2\u8f93\u5165\u5185\u5bb9\uff0c\u786e\u8ba4\u5237\u65b0\uff1f";

const $ = (id) => document.getElementById(id);
const labels = {
  item: "\u65b0\u95fb\u6761\u76ee",
  remove: "\u5220\u9664",
  title: "\u6807\u9898",
  summary: "\u6458\u8981",
  link: "\u539f\u6587\u94fe\u63a5",
  official: "\u5df2\u8bc6\u522b\u4e3a\u5b98\u65b9\u7f51\u7ad9",
  unofficial: "\u53ef\u80fd\u975e\u5b98\u65b9\u7f51\u7ad9",
  original: "\u539f\u59cb\u5bfc\u5165\u94fe\u63a5",
  full: "\u539f\u6587\u5168\u6587\uff08\u53ef\u9009\uff09",
  refreshLink: "\u6839\u636e\u94fe\u63a5\u66f4\u65b0\u5168\u6587",
  refreshFull: "\u6839\u636e\u5168\u6587\u66f4\u65b0\u6458\u8981",
  llmOn: "\u6458\u8981\u529f\u80fd\u5df2\u542f\u7528",
  llmOff: "\u6458\u8981\u529f\u80fd\u672a\u542f\u7528\uff1b\u8bf7\u8f93\u5165 API Key",
};

function setBusy(button, busy, text) {
  button.disabled = busy;
  if (busy) {
    button.dataset.label = button.textContent;
    button.textContent = text;
  } else if (button.dataset.label) {
    button.textContent = button.dataset.label;
  }
}

function escapeHtml(value) {
  return String(value ?? "").replace(
    /[&<>"']/g,
    (character) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    })[character],
  );
}

function isHttpUrl(value) {
  return /^https?:\/\/\S+$/i.test(String(value || "").trim());
}

function render() {
  $("news-list").innerHTML = state.items
    .map((item, index) => {
      const pending = state.pending[item.id] || "";
      const link = String(item.final_link || "").trim();
      const canOpen = isHttpUrl(link);
      return `<article class="news-card" data-id="${escapeHtml(item.id)}">
    <div class="card-head"><div class="card-title"><button type="button" class="drag-handle" draggable="true" title="\u62d6\u52a8\u4ea4\u6362\u987a\u5e8f" aria-label="\u62d6\u52a8\u4ea4\u6362\u987a\u5e8f">&#x2630;</button><span class="number">${index + 1}.</span> <strong>${labels.item}</strong></div><button class="remove" data-action="remove">${labels.remove}</button></div>
    <div class="field"><label>${labels.title}</label><input data-field="title" value="${escapeHtml(item.title)}"></div>
    <div class="field"><label>${labels.summary}</label><textarea data-field="summary" rows="5">${escapeHtml(item.summary)}</textarea></div>
    <div class="field"><label>${labels.link}</label><div class="link-row"><input class="link-input" data-field="final_link" value="${escapeHtml(link)}"><button type="button" class="open-link" data-action="open-link" title="\u8df3\u8f6c\u5230\u539f\u6587\u94fe\u63a5" ${canOpen ? "" : "disabled"}>\u2197</button></div></div>
    <div class="meta"><span class="${item.official_status ? "official" : "unofficial"}">${item.official_status ? labels.official : labels.unofficial}</span><span>${escapeHtml(item.official_reason)}</span><span>${labels.original}\uff1a${escapeHtml(item.original_link || "")}</span></div>
    <div class="field"><label>${labels.full}</label><textarea class="full-text" data-field="full_text" placeholder="\u7c98\u8d34\u6587\u4ef6\u5168\u6587\u540e\uff0c\u52fe\u9009\u4e0b\u65b9\u9009\u9879\u91cd\u65b0\u603b\u7ed3">${escapeHtml(item.full_text)}</textarea></div>
    <div class="check-row"><label><input type="checkbox" data-action="refresh-link" ${pending === "link" ? "checked" : ""}>${labels.refreshLink}</label><label><input type="checkbox" data-action="refresh-full" ${pending === "full" ? "checked" : ""}>${labels.refreshFull}</label></div>
    ${pending ? `<p class="pending-note">\u5df2\u9009\u62e9\uff0c\u70b9\u51fb\u5e95\u90e8\u66f4\u65b0\u540e\u7edf\u4e00\u5904\u7406</p>` : ""}
    ${item.error ? `<p class="card-error">${escapeHtml(item.error)}</p>` : ""}
  </article>`;
    })
    .join("");
  $("actions").hidden = state.items.length === 0;
  $("news-toolbar").hidden = !state.sessionId;
  $("session-state").textContent = state.sessionId
    ? `${state.items.length} \u6761\u65b0\u95fb`
    : "\u672a\u5f00\u59cb";
}

function readCard(card) {
  const item = state.items.find((candidate) => candidate.id === card.dataset.id);
  if (!item) return null;
  card.querySelectorAll("[data-field]").forEach((element) => {
    item[element.dataset.field] = element.value;
  });
  return item;
}

function readAllCards() {
  document.querySelectorAll(".news-card").forEach(readCard);
}

async function api(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "\u8bf7\u6c42\u5931\u8d25");
  return data;
}

function updateLlmState(data) {
  $("llm-state").textContent = data.llm_enabled ? labels.llmOn : labels.llmOff;
  $("llm-state").className = data.llm_enabled ? "ok" : "muted";
}

function openLlmModal() {
  $("llm-modal").hidden = false;
  $("llm-base-url").focus();
}

function closeLlmModal() {
  $("llm-modal").hidden = true;
  $("llm-modal-error").textContent = "";
}

function currentLlmConfig() {
  return {
    base_url: $("llm-base-url").value.trim(),
    model: $("llm-model").value.trim(),
    api_key: $("llm-key").value.trim(),
  };
}

function syncInputLinksFromItems() {
  $("input-text").value = state.items
    .map((item) => String(item.final_link || "").trim())
    .join("\n");
}

function extractLinksForExport(text) {
  const pattern = /https?:\/\/[^\s<>"'，。；;：？！、）)】\]}]+/gi;
  const seen = new Set();
  return (String(text || "").match(pattern) || [])
    .map((link) => link.replace(/[.,;，。；：？！、）)】\]}]+$/g, "").trim())
    .filter((link) => {
      if (!link || seen.has(link)) return false;
      seen.add(link);
      return true;
    });
}

function downloadTextFile(content, filename) {
  const blob = new Blob(["\ufeff", content], { type: "text/plain;charset=utf-8" });
  const urlObject = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = urlObject;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(urlObject), 0);
}

function addBlankItem() {
  readAllCards();
  state.items.push({
    id: `manual-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    original_link: "",
    final_link: "",
    title: "",
    summary: "",
    full_text: "",
    source: "\u4eba\u5de5\u65b0\u589e",
    pub_date: null,
    topic: "",
    jurisdiction: "",
    legal_level: "",
    official_status: false,
    official_reason: "\u65e0\u6709\u6548\u57df\u540d",
    fetch_status: "pending",
    reason: "",
    error: "",
  });
  render();
  const cards = document.querySelectorAll(".news-card");
  cards[cards.length - 1]?.querySelector('[data-field="title"]')?.focus();
}

$("llm-settings-btn").onclick = openLlmModal;
document
  .querySelectorAll('[data-action="close-llm-modal"]')
  .forEach((element) => {
    element.onclick = closeLlmModal;
  });

$("create-btn").onclick = async () => {
  $("global-error").textContent = "";
  const button = $("create-btn");
  setBusy(button, true, "\u5904\u7406\u4e2d...");
  try {
    const data = await api("/api/sessions", {
      method: "POST",
      body: JSON.stringify({
        input_text: $("input-text").value,
        week_start: $("week-start").value,
        week_end: $("week-end").value,
        llm_config: state.llmConfig.api_key ? state.llmConfig : null,
      }),
    });
    state.sessionId = data.session_id;
    state.items = data.items;
    state.pending = {};
    render();
  } catch (error) {
    $("global-error").textContent = error.message;
  } finally {
    setBusy(button, false);
  }
};

$("upload-word-btn").onclick = () => $("word-file").click();

$("export-links-btn").onclick = () => {
  const links = extractLinksForExport($("input-text").value);
  if (!links.length) {
    $("global-error").textContent = "\u8bf7\u5148\u7c98\u8d34\u5305\u542b\u7f51\u5740\u7684\u6587\u672c";
    $("export-state").textContent = "";
    return;
  }
  $("global-error").textContent = "";
  downloadTextFile(`${links.join("\n")}\n`, "batch-links.txt");
  $("export-state").textContent = `\u5df2\u5bfc\u51fa ${links.length} \u6761\u94fe\u63a5`;
};

$("word-file").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  const button = $("upload-word-btn");
  $("global-error").textContent = "";
  setBusy(button, true, "\u89e3\u6790\u4e2d...");
  try {
    const params = new URLSearchParams({
      week_start: $("week-start").value,
      week_end: $("week-end").value,
    });
    const response = await fetch(`/api/word/parse?${params.toString()}`, {
      method: "POST",
      headers: {
        "Content-Type": file.type || "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "X-Filename": encodeURIComponent(file.name),
      },
      body: file,
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Word \u89e3\u6790\u5931\u8d25");
    state.sessionId = data.session_id;
    state.items = data.items;
    state.pending = {};
    $("input-text").value = data.text || "";
    $("upload-state").textContent = `\u5df2\u89e3\u6790 ${state.items.length} \u6761\u65b0\u95fb`;
    render();
  } catch (error) {
    $("global-error").textContent = error.message;
  } finally {
    event.target.value = "";
    setBusy(button, false);
  }
});

$("save-key-btn").onclick = async () => {
  const button = $("save-key-btn");
  $("llm-modal-error").textContent = "";
  setBusy(button, true, "\u5e94\u7528\u4e2d...");
  try {
    const config = currentLlmConfig();
    if (!config.base_url || !config.model || !config.api_key) {
      throw new Error("\u8bf7\u586b\u5199 Base URL\u3001\u6a21\u578b\u540d\u79f0\u548c API Key");
    }
    if (state.sessionId) {
      const data = await api(`/api/sessions/${state.sessionId}/llm-config`, {
        method: "POST",
        body: JSON.stringify(config),
      });
      state.llmConfig = config;
      updateLlmState(data);
      $("save-state").textContent =
        "\u914d\u7f6e\u5df2\u5e94\u7528\uff1b\u8bf7\u52fe\u9009\u201c\u6839\u636e\u5168\u6587\u66f4\u65b0\u6458\u8981\u201d\u540e\u66f4\u65b0";
    } else {
      state.llmConfig = config;
      updateLlmState({ llm_enabled: true });
    }
    closeLlmModal();
  } catch (error) {
    $("llm-modal-error").textContent = error.message;
  } finally {
    setBusy(button, false);
  }
};

$("clear-key-btn").onclick = async () => {
  const button = $("clear-key-btn");
  $("llm-modal-error").textContent = "";
  setBusy(button, true, "\u6e05\u9664\u4e2d...");
  try {
    let data = { llm_enabled: false };
    if (state.sessionId) {
      data = await api(`/api/sessions/${state.sessionId}/llm-config`, {
        method: "DELETE",
      });
    }
    state.llmConfig = {
      base_url: $("llm-base-url").value.trim(),
      model: $("llm-model").value.trim(),
      api_key: "",
    };
    $("llm-key").value = "";
    updateLlmState(data);
  } catch (error) {
    $("llm-modal-error").textContent = error.message;
  } finally {
    setBusy(button, false);
  }
};

$("add-btn").onclick = addBlankItem;

function clearDragStyles() {
  document.querySelectorAll(".news-card.dragging, .news-card.drag-over").forEach((card) => {
    card.classList.remove("dragging", "drag-over");
  });
}

$("news-list").addEventListener("dragstart", (event) => {
  const handle = event.target.closest?.(".drag-handle");
  const card = handle?.closest(".news-card");
  if (!card) return;
  readAllCards();
  draggedId = card.dataset.id;
  card.classList.add("dragging");
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", draggedId);
  }
});

$("news-list").addEventListener("dragover", (event) => {
  const card = event.target.closest?.(".news-card");
  if (!card || !draggedId || card.dataset.id === draggedId) return;
  event.preventDefault();
  document.querySelectorAll(".news-card.drag-over").forEach((candidate) => {
    candidate.classList.remove("drag-over");
  });
  card.classList.add("drag-over");
  if (event.dataTransfer) event.dataTransfer.dropEffect = "move";
});

$("news-list").addEventListener("drop", (event) => {
  const card = event.target.closest?.(".news-card");
  if (!card || !draggedId) return;
  event.preventDefault();
  const targetId = card.dataset.id;
  if (targetId === draggedId) return;
  readAllCards();
  const from = state.items.findIndex((item) => item.id === draggedId);
  const to = state.items.findIndex((item) => item.id === targetId);
  if (from < 0 || to < 0) return;
  const [moved] = state.items.splice(from, 1);
  state.items.splice(to, 0, moved);
  clearDragStyles();
  draggedId = "";
  render();
});

$("news-list").addEventListener("dragend", () => {
  clearDragStyles();
  draggedId = "";
});

$("sort-btn").onclick = async () => {
  const button = $("sort-btn");
  readAllCards();
  syncInputLinksFromItems();
  setBusy(button, true, "\u6392\u5e8f\u4e2d...");
  try {
    await api(`/api/sessions/${state.sessionId}`, {
      method: "PATCH",
      body: JSON.stringify({ items: state.items }),
    });
    const data = await api(`/api/sessions/${state.sessionId}/auto-sort`, {
      method: "POST",
    });
    state.items = data.items;
    syncInputLinksFromItems();
    $("save-state").textContent =
      "\u5df2\u6839\u636e\u6cd5\u5f8b\u6548\u529b\u4f4d\u9636\u3001\u5148\u56fd\u5185\u540e\u56fd\u5916\u7684\u987a\u5e8f\u81ea\u52a8\u6392\u5e8f";
    render();
  } catch (error) {
    $("save-state").textContent = error.message;
  } finally {
    setBusy(button, false);
  }
};

$("news-list").addEventListener("click", (event) => {
  const card = event.target.closest(".news-card");
  if (!card) return;
  const action = event.target.dataset.action;
  if (action === "open-link") {
    const item = readCard(card);
    if (item && isHttpUrl(item.final_link)) {
      window.open(item.final_link.trim(), "_blank", "noopener,noreferrer");
    }
    return;
  }
  if (action !== "remove") return;
  readAllCards();
  const id = card.dataset.id;
  state.items = state.items.filter((item) => item.id !== id);
  delete state.pending[id];
  render();
});

$("news-list").addEventListener("change", (event) => {
  const action = event.target.dataset.action;
  if (!action || !event.target.matches("input[type=checkbox]")) return;
  readAllCards();
  const card = event.target.closest(".news-card");
  const id = card.dataset.id;
  if (!event.target.checked) {
    delete state.pending[id];
    render();
    return;
  }
  state.pending[id] = action === "refresh-link" ? "link" : "full";
  render();
});

$("update-btn").onclick = async () => {
  const button = $("update-btn");
  readAllCards();
  syncInputLinksFromItems();
  const jobs = Object.entries(state.pending);
  const failures = [];
  let completed = 0;
  setBusy(button, true, "\u66f4\u65b0\u4e2d...");
  try {
    await api(`/api/sessions/${state.sessionId}`, {
      method: "PATCH",
      body: JSON.stringify({ items: state.items }),
    });

    for (const [id, mode] of jobs) {
      const item = state.items.find((candidate) => candidate.id === id);
      if (!item) continue;
      try {
        const data = await api(`/api/sessions/${state.sessionId}/refresh`, {
          method: "POST",
          body: JSON.stringify({ item, mode }),
        });
        state.items = state.items.map((candidate) =>
          candidate.id === id ? data.item : candidate,
        );
        completed += 1;
      } catch (error) {
        failures.push({ id, message: error.message });
        state.items = state.items.map((candidate) => {
          if (candidate.id !== id) return candidate;
          return Object.assign({}, candidate, { error: error.message });
        });
      }
    }

    await api(`/api/sessions/${state.sessionId}`, {
      method: "PATCH",
      body: JSON.stringify({ items: state.items }),
    });
    state.pending = {};
    $("save-state").textContent = failures.length
      ? `\u5df2\u5b8c\u6210 ${completed} \u6761\uff0c${failures.length} \u6761\u5931\u8d25`
      : `\u5df2\u66f4\u65b0 ${completed} \u6761\u9009\u4e2d\u65b0\u95fb\uff0c\u672a\u52fe\u9009\u6761\u76ee\u4ec5\u4fdd\u5b58\u4fee\u6539`;
    render();
  } catch (error) {
    $("save-state").textContent = error.message;
  } finally {
    setBusy(button, false);
  }
};

function filenameFromResponse(response, fallback) {
  const disposition = response.headers.get("Content-Disposition") || "";
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (encoded) {
    try {
      return decodeURIComponent(encoded[1]);
    } catch (error) {
      // Use the plain filename fallback when a server sends malformed encoding.
    }
  }
  const plain = disposition.match(/filename="?([^";]+)"?/i);
  return plain ? plain[1] : fallback;
}

async function downloadGeneratedFile(url, fallback) {
  const response = await fetch(url, { method: "POST" });
  if (!response.ok) {
    let data = {};
    try {
      data = await response.json();
    } catch (error) {
      // Keep the HTTP status as the fallback when the server did not return JSON.
    }
    throw new Error(data.detail || "\u6587\u4ef6\u751f\u6210\u5931\u8d25");
  }
  const blob = await response.blob();
  const urlObject = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = urlObject;
  link.download = filenameFromResponse(response, fallback);
  link.click();
  URL.revokeObjectURL(urlObject);
}

$("word-btn").onclick = async () => {
  readAllCards();
  const button = $("word-btn");
  setBusy(button, true, "\u751f\u6210\u4e2d...");
  try {
    await api(`/api/sessions/${state.sessionId}`, {
      method: "PATCH",
      body: JSON.stringify({ items: state.items }),
    });
    await downloadGeneratedFile(`/api/sessions/${state.sessionId}/word`, "\u6cd5\u8baf.docx");
    $("save-state").textContent = "Word \u5df2\u751f\u6210";
  } catch (error) {
    $("save-state").textContent = error.message;
  } finally {
    setBusy(button, false);
  }
};

$("html-btn").onclick = async () => {
  readAllCards();
  const button = $("html-btn");
  setBusy(button, true, "HTML \u751f\u6210\u4e2d...");
  try {
    await api(`/api/sessions/${state.sessionId}`, {
      method: "PATCH",
      body: JSON.stringify({ items: state.items }),
    });
    await downloadGeneratedFile(`/api/sessions/${state.sessionId}/html`, "\u6cd5\u8baf.html");
    $("save-state").textContent = "HTML \u5df2\u751f\u6210";
  } catch (error) {
    $("save-state").textContent = error.message;
  } finally {
    setBusy(button, false);
  }
};

window.addEventListener("beforeunload", (event) => {
  event.preventDefault();
  event.returnValue = REFRESH_WARNING;
});

function parseDateInput(value) {
  if (!value) return null;
  const parts = value.split("-").map(Number);
  if (parts.length !== 3 || parts.some(Number.isNaN)) return null;
  return new Date(parts[0], parts[1] - 1, parts[2]);
}

function dateInputValue(value) {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
}

function setDefaultWeek() {
  if ($("week-start").value || $("week-end").value) return;
  const today = new Date();
  const day = today.getDay() || 7;
  const start = new Date(today);
  start.setDate(today.getDate() - day + 1);
  const end = new Date(start);
  end.setDate(start.getDate() + 6);
  $("week-start").value = dateInputValue(start);
  $("week-end").value = dateInputValue(end);
}

function updateWeekHint() {
  const start = parseDateInput($("week-start").value);
  const end = parseDateInput($("week-end").value);
  const hint = $("week-hint");
  if (!start || !end) {
    hint.textContent = "";
    return;
  }
  const days = Math.round((end - start) / 86400000);
  const fullWeek = start.getDay() === 1 && end.getDay() === 0 && days === 6;
  hint.textContent = fullWeek
    ? ""
    : "\u63d0\u793a\uff1a\u5f53\u524d\u65f6\u95f4\u8303\u56f4\u4e0d\u662f\u5b8c\u6574\u4e00\u5468\uff08\u5468\u4e00\u81f3\u5468\u65e5\uff09\uff0c\u4ecd\u53ef\u7ee7\u7eed\u3002";
}

["week-start", "week-end"].forEach((id) => {
  $(id).addEventListener("change", updateWeekHint);
});
setDefaultWeek();
updateWeekHint();

api("/api/status")
  .then((data) => {
    $("llm-base-url").value = data.llm_base_url || "";
    $("llm-model").value = data.llm_model || "";
    updateLlmState(data);
  })
  .catch(() => {});
