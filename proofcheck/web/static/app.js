"use strict";
/*
 * ProofCheck SPA — framework-free, offline. Hash-routed views over the /api/* contract.
 * Structure: helpers -> api client -> app state -> views -> router -> boot.
 * No business logic lives here; all matching/normalization/OCR happens server-side.
 */

// ---- helpers ----------------------------------------------------------------
const el = (tag, attrs = {}, ...kids) => {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "html") node.innerHTML = v;
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined && v !== false) node.setAttribute(k, v);
  }
  for (const kid of kids.flat()) {
    if (kid == null) continue;
    node.appendChild(typeof kid === "string" ? document.createTextNode(kid) : kid);
  }
  return node;
};
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const view = () => document.getElementById("view");
const clearView = () => {
  if (state.viewCleanup) state.viewCleanup();
  state.viewCleanup = null;
  state.viewToken++;
  view().replaceChildren();
};

// ---- file intake (drag & drop + clipboard paste) ----------------------------
// Both slots accept files by drop/paste, not just the native picker. Files are routed
// to the Excel or document (PDF/image) input by extension, falling back to MIME type so
// pasted screenshots (which arrive as a nameless image blob) still land correctly.
const EXCEL_EXTS = new Set([".xlsx", ".xlsm"]);
const DOC_EXTS = new Set([".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp", ".gif"]);
const _MIME_EXT = { "image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/gif": "gif", "image/bmp": "bmp", "image/tiff": "tiff", "application/pdf": "pdf" };

const extOf = (name) => { const i = (name || "").lastIndexOf("."); return i < 0 ? "" : name.slice(i).toLowerCase(); };

// Which input a dropped/pasted file belongs to, or null if it's neither kind.
function targetForFile(file) {
  const ext = extOf(file.name);
  if (EXCEL_EXTS.has(ext)) return "excel";
  if (DOC_EXTS.has(ext)) return "pdf";
  const t = file.type || "";
  if (t.startsWith("image/") || t === "application/pdf") return "pdf";
  if (t.includes("spreadsheetml") || t.includes("ms-excel")) return "excel";
  return null;
}

// The server validates by extension, so a nameless pasted blob needs a synthetic filename.
function withName(file) {
  if (extOf(file.name)) return file;
  const ext = _MIME_EXT[file.type] || "png";
  try { return new File([file], `pasted.${ext}`, { type: file.type || "application/octet-stream" }); }
  catch (_) { return file; }
}

// Assign a File to a native <input type=file> and fire change so existing handlers run.
function setInputFile(inputId, file) {
  const input = document.getElementById(inputId);
  if (!input || input.disabled) return false;
  try { const dt = new DataTransfer(); dt.items.add(file); input.files = dt.files; }
  catch (_) { return false; }
  input.dispatchEvent(new Event("change", { bubbles: true }));
  return true;
}

// Route every usable file in a list to its slot; returns how many were accepted.
function acceptFiles(fileList) {
  let handled = 0;
  const accepted = new Set();
  for (const raw of Array.from(fileList || [])) {
    const target = targetForFile(raw);
    if (target && !accepted.has(target) && setInputFile(target, withName(raw))) { handled++; accepted.add(target); }
  }
  return handled;
}

// Clipboard paste (Ctrl/Cmd+V) anywhere on the Check view drops files into their slots.
// Attached once at boot; a no-op unless the Check view's inputs are present.
function handlePaste(ev) {
  if (!document.getElementById("excel")) return;      // not on the Check view
  const files = ev.clipboardData && ev.clipboardData.files;
  if (files && files.length && acceptFiles(files)) {
    ev.preventDefault();
    const msgs = document.getElementById("msgs");
    if (msgs) msgs.innerHTML = "";
  }
}

function diffHtml(diff, best) {
  if (!diff || !diff.length) return esc(best || "");
  return diff.map(([op, text]) => {
    const t = esc(text);
    if (op === "equal") return t;
    if (op === "delete") return `<del>${t}</del>`;
    if (op === "insert") return `<ins>${t}</ins>`;
    return `<del>${t}</del>`;
  }).join("");
}

// ---- api client -------------------------------------------------------------
function errorMessage(data, fallback) {
  if (typeof data?.error === "string") return data.error;
  if (typeof data?.detail === "string") return data.detail;
  if (Array.isArray(data?.detail)) return data.detail.map((e) => `${(e.loc || []).slice(1).join(".")}: ${e.msg}`).join("; ");
  return fallback || "The server returned an unexpected response.";
}

const api = {
  async request(url, opts = {}, { signal, timeout = 30000 } = {}) {
    const controller = new AbortController();
    const abort = () => controller.abort();
    if (signal?.aborted) controller.abort();
    signal?.addEventListener("abort", abort, { once: true });
    let timedOut = false;
    const timer = timeout ? setTimeout(() => { timedOut = true; controller.abort(); }, timeout) : null;
    try {
      const res = await fetch(url, { ...opts, credentials: "same-origin", signal: controller.signal });
      let data;
      try { data = await res.json(); }
      catch (_) { throw new Error(res.ok ? "The server returned an unreadable response." : `Server error (${res.status}). Please retry.`); }
      if (!res.ok) {
        const e = new Error(errorMessage(data, res.statusText)); e.status = res.status; throw e;
      }
      return data;
    } catch (e) {
      if (timedOut) throw new Error("The request timed out. Check your connection and retry.");
      if (e instanceof TypeError) throw new Error("Cannot reach the server. Check your connection and retry.");
      throw e;
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener("abort", abort);
    }
  },
  json(method, url, body) {
    const opts = { method, headers: {} };
    if (body !== undefined) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
    return api.request(url, opts);
  },
  form(url, formData, options) {
    return api.request(url, { method: "POST", body: formData }, options);
  },
  health: () => api.json("GET", "/api/health"),
  me: () => api.json("GET", "/api/auth/me"),
  login: (username, password) => api.json("POST", "/api/auth/login", { username, password }),
  logout: () => api.json("POST", "/api/auth/logout"),
  history: () => api.json("GET", "/api/history"),
  historyItem: (id) => api.json("GET", `/api/history/${id}`),
  deleteHistory: (id) => api.json("DELETE", `/api/history/${id}`),
};

// ---- app state --------------------------------------------------------------
const state = { health: null, user: null, inspectData: null, lastResult: null,
  viewToken: 0, viewCleanup: null, running: false, runStarted: 0, runError: null, page: 0, rows: [] };

function banner(kind, msg) { return el("div", { class: `banner ${kind}`, role: kind === "err" ? "alert" : "status", html: msg }); }

// ---- Check view -------------------------------------------------------------
function checkView() {
  clearView();
  // The OCR pill (id="ocrPill") is filled by applyOcrStatus() from the live /api/health,
  // so restarting the server with OCR installed updates it without a hard page reload.
  const ocrNote = '<span id="ocrPill" class="pill"></span>';

  const root = el("div", {},
    el("div", { class: "panel dropzone", id: "checkPanel", html: `
      <div class="row">
        <div class="field"><label for="excel">Excel file (.xlsx / .xlsm)</label>
          <input type="file" id="excel" accept=".xlsx,.xlsm"></div>
        <div class="field"><label for="pdf">PDF or image (.pdf / .png / .jpg …)</label>
          <input type="file" id="pdf" accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp,.gif"></div>
      </div>
      <p class="filehint">Tip: you can also <b>drag &amp; drop</b> files anywhere on this panel, or
        <b>copy a file/screenshot and paste</b> (Ctrl/Cmd + V). Spreadsheets go to the Excel slot;
        PDFs and images to the document slot.</p>
      <div class="row">
        <div class="field" style="max-width:160px;"><label for="header_row">Header row</label>
          <input id="header_row" type="number" min="1" max="1048576" value="1"></div>
        <div class="field" style="max-width:240px;"><label for="sheet">Sheet</label>
          <select id="sheet"></select></div>
        <div class="field"><label for="columns">Columns to check (one or more)</label>
          <select id="columns" multiple></select>
          <span class="muted">Loaded from the Excel file. Hold Ctrl/Cmd for multiple.</span></div>
      </div>
      <div class="field" style="max-width:360px;">
        <label for="threshold">Fuzzy threshold: <span id="thresholdVal">90</span></label>
        <input type="range" id="threshold" min="0" max="100" value="90"></div>
      <div class="checks">
        <label><input type="checkbox" id="normalize_digits"> Normalize digits</label>
        <label><input type="checkbox" id="strip_punctuation"> Strip punctuation</label>
        <label><input type="checkbox" id="fold_diacritics"> Fold diacritics</label>
        <label><input type="checkbox" id="reverse"> Reverse word order</label>
        <label><input type="checkbox" id="all_columns"> Check all columns</label>
        <label><input type="checkbox" id="ocr"> OCR scanned pages ${ocrNote}</label>
        <label title="When on, an unchanged file reuses its previous OCR text instead of re-running OCR.">
          <input type="checkbox" id="ocr_cache" checked> Use OCR cache</label>
      </div>
      <div id="ocrOpts" class="row hidden" style="margin-top:.5rem;">
        <div class="field" style="max-width:160px;"><label for="ocr_lang">OCR language(s)</label>
          <input type="text" id="ocr_lang" value="eng" placeholder="eng+ara"></div>
        <div class="field" style="max-width:140px;"><label for="ocr_dpi">OCR DPI</label>
          <input type="number" id="ocr_dpi" value="300" min="72" max="600" step="1"></div>
        <div class="field" style="max-width:220px;"><label for="ocr_psm">Page layout (PSM)</label>
          <select id="ocr_psm">
            <option value="6" selected>Single block (6)</option>
            <option value="3">Automatic (3)</option>
            <option value="4">Columns (4)</option>
            <option value="11">Sparse text (11)</option>
          </select></div>
      </div>
      <div style="margin-top:1rem;">
        <button class="primary" id="run" disabled>Run check</button>
        <span id="hint" class="muted" role="status" aria-live="polite">Select an Excel and a document to begin.</span>
      </div>`}),
    el("div", { id: "msgs", "aria-live": "polite" }),
    el("div", { id: "results", class: "hidden" })
  );
  view().appendChild(root);
  wireCheck();
  applyOcrStatus();          // reflect current (cached) health immediately
  refreshHealthThenApply();  // then re-check the server in case it was just (re)started
  if (state.lastResult) renderResults(state.lastResult);
  if (state.runError) document.getElementById("msgs").appendChild(banner("err", esc(state.runError)));
}

// Update the OCR pill + checkbox from state.health. When OCR isn't available the checkbox
// is disabled with an explanatory tooltip, so it's clear *why* and how to enable it.
function applyOcrStatus() {
  const pill = document.getElementById("ocrPill");
  if (!pill) return;
  const ready = !!(state.health && state.health.ocr_available);
  pill.textContent = ready ? "OCR ready" : "OCR not installed";
  pill.title = ready
    ? "Tesseract OCR engine detected on the server."
    : "Server can't find OCR. Install with: pip install \"proofcheck[ocr]\" + the Tesseract " +
      "binary, then restart the server. (This pill reflects the server that serves this page.)";
  pill.style.color = ready ? "var(--exact)" : "var(--missing)";
  const box = document.getElementById("ocr");
  if (box) {
    box.disabled = state.running || !ready;
    if (!ready && box.checked) {
      box.checked = false;
      document.getElementById("ocrOpts").classList.add("hidden");
    }
  }
}

async function refreshHealthThenApply() {
  try { state.health = await api.health(); } catch (_) { /* keep cached health */ }
  applyOcrStatus();
}

function wireCheck() {
  const panel = document.getElementById("checkPanel");
  const root = panel.parentElement;
  const $ = (id) => root.querySelector(`#${id}`);
  let inspecting = false, inspected = false, inspectSequence = 0, inspectController;
  let elapsedTimer = null;
  const showElapsed = () => {
    if (!root.isConnected) return;
    const seconds = Math.floor((Date.now() - state.runStarted) / 1000);
    $("hint").textContent = `Processing… ${seconds}s elapsed. Scanned pages may take longer.`;
  };
  state.viewCleanup = () => { inspectController?.abort(); clearInterval(elapsedTimer); };
  const updateRun = () => {
    if (!root.isConnected) return;
    const filesReady = $("excel").files.length && $("pdf").files.length;
    const selected = $("all_columns").checked || $("columns").selectedOptions.length;
    $("run").disabled = state.running || inspecting || !inspected || !filesReady || !selected;
    if (state.running) return showElapsed();
    $("hint").textContent = inspecting ? "Reading spreadsheet headers…" : !filesReady
      ? "Choose an Excel file and a PDF or image."
      : !inspected ? "Read the spreadsheet headers to continue."
      : !selected ? "Select columns or enable Check all columns." : "Ready to check.";
  };
  const fileValid = (input, allowed) => {
    const file = input.files[0];
    if (!file) return false;
    const limit = state.health?.max_upload_bytes || 50 * 1024 * 1024;
    let message = "";
    if (!allowed.has(extOf(file.name))) message = "Unsupported file type. Choose a file in one of the listed formats.";
    else if (!file.size) message = "This file is empty. Choose a file with content.";
    else if (file.size > limit) message = `File exceeds the ${(limit / 1024 / 1024).toFixed(0)} MB limit.`;
    if (message) { input.value = ""; $("msgs").appendChild(banner("err", message)); return false; }
    return true;
  };
  $("threshold").addEventListener("input", () => { $("thresholdVal").textContent = $("threshold").value; });
  $("pdf").addEventListener("change", () => { fileValid($("pdf"), DOC_EXTS); updateRun(); });
  $("columns").addEventListener("change", updateRun);
  $("all_columns").addEventListener("change", updateRun);
  $("ocr").addEventListener("change", () => $("ocrOpts").classList.toggle("hidden", !$("ocr").checked));

  // Keep the previous selection when a native file picker is cancelled.
  ["excel", "pdf"].forEach((id) => $(id).addEventListener("cancel", updateRun));
  const isFileDrag = (e) => e.dataTransfer && Array.from(e.dataTransfer.types || []).includes("Files");
  ["dragenter", "dragover"].forEach((evt) => panel.addEventListener(evt, (e) => {
    if (!isFileDrag(e)) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = state.running ? "none" : "copy";
    if (!state.running) panel.classList.add("dragging");
  }));
  panel.addEventListener("dragleave", (e) => { if (!panel.contains(e.relatedTarget)) panel.classList.remove("dragging"); });
  panel.addEventListener("drop", (e) => {
    if (!e.dataTransfer?.files?.length) return;
    e.preventDefault(); panel.classList.remove("dragging");
    if (state.running) return;
    $("msgs").replaceChildren();
    if (!acceptFiles(e.dataTransfer.files)) $("msgs").appendChild(banner("err", "Choose an Excel file or a PDF/image."));
  });

  const inspectFile = async () => {
    const sequence = ++inspectSequence;
    inspectController?.abort(); inspectController = new AbortController();
    const previousSheet = $("sheet").value;
    const previousColumns = new Set(Array.from($("columns").selectedOptions, (o) => o.value));
    inspected = false; state.inspectData = null;
    $("sheet").replaceChildren(); $("columns").replaceChildren(); $("msgs").replaceChildren();
    if (!fileValid($("excel"), EXCEL_EXTS) || !$("header_row").reportValidity()) { inspecting = false; updateRun(); return; }
    inspecting = true; updateRun();
    const fd = new FormData(); fd.append("excel", $("excel").files[0]); fd.append("header_row", $("header_row").value);
    try {
      const data = await api.form("/api/inspect", fd, { signal: inspectController.signal });
      if (sequence !== inspectSequence || !root.isConnected) return;
      state.inspectData = data;
      data.sheets.forEach((name) => $("sheet").appendChild(el("option", { value: name }, name)));
      if (data.sheets.includes(previousSheet)) $("sheet").value = previousSheet;
      const fill = () => {
        $("columns").replaceChildren();
        const names = (data.headers[$("sheet").value] || []).filter(Boolean);
        if (new Set(names).size !== names.length) {
          inspected = false; $("msgs").replaceChildren(banner("err", "Duplicate column headers found. Rename them in the workbook before checking."));
        } else {
          inspected = names.length > 0;
          names.forEach((name) => { const option = el("option", { value: name }, name); option.selected = previousColumns.has(name); $("columns").appendChild(option); });
        }
        updateRun();
      };
      $("sheet").onchange = fill; fill();
    } catch (e) {
      if (sequence !== inspectSequence || !root.isConnected || e.name === "AbortError") return;
      if (e.status === 401) return redirectLogin();
      $("msgs").appendChild(banner("err", "Inspect failed: " + esc(e.message)));
    } finally {
      if (sequence === inspectSequence && root.isConnected) { inspecting = false; updateRun(); }
    }
  };
  $("excel").addEventListener("change", inspectFile);
  $("header_row").addEventListener("change", inspectFile);

  $("run").addEventListener("click", async () => {
    if (state.running || $("run").disabled) return;
    if (!fileValid($("excel"), EXCEL_EXTS) || !fileValid($("pdf"), DOC_EXTS)) { updateRun(); return; }
    if (!$("header_row").reportValidity() || !$("ocr_dpi").reportValidity()) return;
    $("msgs").replaceChildren(); $("results").replaceChildren(); $("results").classList.add("hidden");
    state.lastResult = null; state.runError = null;
    const fd = new FormData();
    fd.append("excel", $("excel").files[0]); fd.append("pdf", $("pdf").files[0]);
    fd.append("columns_json", JSON.stringify(Array.from($("columns").selectedOptions, (o) => o.value)));
    fd.append("sheet", $("sheet").value); fd.append("header_row", $("header_row").value);
    fd.append("fuzzy_threshold", $("threshold").value);
    ["normalize_digits", "strip_punctuation", "fold_diacritics", "reverse", "all_columns", "ocr", "ocr_cache"].forEach((id) => fd.append(id, $(id).checked));
    ["ocr_lang", "ocr_dpi", "ocr_psm"].forEach((id) => fd.append(id, $(id).value));
    state.running = true; state.runStarted = Date.now(); refreshUserBox();
    panel.querySelectorAll("input,select,button").forEach((node) => { node.disabled = true; });
    panel.setAttribute("aria-busy", "true");
    $("run").textContent = "Running…"; showElapsed(); elapsedTimer = setInterval(showElapsed, 1000);
    try {
      // No automatic retry: replaying a POST would create a duplicate check.
      state.lastResult = await api.form("/api/check", fd, { timeout: 0 });
      if (root.isConnected) renderResults(state.lastResult);
    } catch (e) {
      state.runError = "Check failed: " + e.message;
      if (e.status === 401) { state.user = null; redirectLogin(); }
      else if (root.isConnected) $("msgs").appendChild(banner("err", esc(state.runError)));
    } finally {
      state.running = false; clearInterval(elapsedTimer); refreshUserBox();
      if (root.isConnected) {
        panel.querySelectorAll("input,select,button").forEach((node) => { node.disabled = false; });
        panel.removeAttribute("aria-busy"); $("run").textContent = "Run check";
        applyOcrStatus(); updateRun();
      } else if (document.getElementById("checkPanel")) checkView();
    }
  });
  if (state.running) {
    panel.querySelectorAll("input,select,button").forEach((node) => { node.disabled = true; });
    $("run").textContent = "Running…"; showElapsed(); elapsedTimer = setInterval(showElapsed, 1000);
  } else updateRun();
}

// Plain-language mapping, mirroring proofcheck/humanize.py (presentation only — the API
// still uses EXACT/FUZZY/MISSING/SKIPPED).
const HUMAN = {
  EXACT:   { label: "Found",                  icon: "✓", meaning: "Found in the PDF exactly." },
  FUZZY:   { label: "Found with differences", icon: "≈", meaning: "Found, but not an exact match — check the highlighted differences." },
  MISSING: { label: "Not found",              icon: "✗", meaning: "This value could not be found in the PDF." },
  SKIPPED: { label: "Blank",                  icon: "–", meaning: "The spreadsheet cell was empty, so there was nothing to check." },
};

function summarySentence(s) {
  const checked = s.total - s.skipped;
  const parts = [];
  if (s.exact) parts.push(`${s.exact} found`);
  if (s.fuzzy) parts.push(`${s.fuzzy} found with small differences`);
  if (s.missing) parts.push(`${s.missing} not found`);
  const body = parts.length ? parts.join("; ") : "nothing needed checking";
  let out = `We checked ${checked} value${checked === 1 ? "" : "s"} from your spreadsheet against the PDF: ${body}.`;
  if (s.skipped) out += ` ${s.skipped} blank cell${s.skipped === 1 ? " was" : "s were"} skipped.`;
  return out;
}

function sourceBadge(source) {
  if (source === "OCR") return '<span class="src src-ocr" title="Read from a scanned/image page by OCR">OCR</span>';
  if (source === "text") return '<span class="src src-text" title="From the PDF\'s embedded text layer">Text layer</span>';
  return '<span class="src src-none">-</span>';
}

function detailText(r) {
  const where = r.page == null ? "the PDF" : `page ${r.page}`;
  if (r.status === "EXACT") return `Found on ${where}.`;
  if (r.status === "FUZZY")
    return `Found on ${where}, but not an exact match. Your spreadsheet has “${r.expected}”; ` +
           `the PDF shows “${r.best_match || ""}” (${r.score}% similar).`;
  if (r.status === "MISSING")
    return r.best_match
      ? `Not found in the PDF. The closest text was “${r.best_match}” on ${where}, ` +
        `but it was too different (${r.score}% similar).`
      : "Not found anywhere in the PDF.";
  return "The spreadsheet cell was empty, so there was nothing to check.";
}

function renderResults(data) {
  const card = (l, v) => `<div class="card"><div class="n">${v}</div><div class="l">${esc(l)}</div></div>`;
  const s = data.summary;
  const results = document.getElementById("results");
  if (!results) return;
  results.classList.remove("hidden");
  const legend = ["EXACT", "FUZZY", "MISSING", "SKIPPED"].map((st) =>
    `<li><span class="badge b-${st}">${HUMAN[st].icon} ${esc(HUMAN[st].label)}</span> — ${esc(HUMAN[st].meaning)}</li>`
  ).join("");
  results.innerHTML = `
    <div class="panel">
      <p class="lead">${esc(summarySentence(s))}</p>
      ${data.timings?.total != null ? `<p class="muted">Completed in ${data.timings.total.toFixed(2)}s · matching ${(data.timings.match || 0).toFixed(3)}s</p>` : ""}
      <div class="cards">
        ${card("Values checked", s.total - s.skipped)}${card("Found", s.exact)}
        ${card("Found w/ differences", s.fuzzy)}${card("Not found", s.missing)}
        ${card("Blank", s.skipped)}${card("Match rate", (s.pass_rate * 100).toFixed(0) + "%")}
      </div>
      ${data.warnings && data.warnings.length
        ? `<div class="banner" style="margin-top:1rem;"><b>Notes</b><ul>${data.warnings.map((w) => `<li>${esc(w)}</li>`).join("")}</ul></div>`
        : ""}
      <details class="legend"><summary>How to read these results</summary>
        <ul>${legend}<li><b>Matched via</b> — where the PDF text came from: ${sourceBadge("text")} (the PDF's real text) or ${sourceBadge("OCR")} (read from a scanned/image page).</li><li class="muted">In the differences below, <del>red struck-through</del> text is in your spreadsheet but not the PDF; <ins>green</ins> text is in the PDF but not your spreadsheet.</li></ul>
      </details>
      <div style="margin-top:1rem;">
        <a class="report" href="${esc(data.report_urls.html)}" target="_blank" rel="noopener">Download printable report</a> &nbsp;
        <a class="report" href="${esc(data.report_urls.xlsx)}">Download Excel report</a>
      </div>
    </div>
    <div class="panel">
      <div class="toolbar">
        <label>Show:
          <select id="statusFilter">
            <option value="">All results</option><option value="EXACT">Found</option>
            <option value="FUZZY">Found with differences</option><option value="MISSING">Not found</option>
            <option value="SKIPPED">Blank</option>
          </select>
        </label>
        <input type="search" id="search" aria-label="Search result values" placeholder="Search values…">
      </div>
      <div id="tables"></div><div id="pagination" class="toolbar" aria-label="Result pages"></div>
    </div>`;
  state.rows = data.columns.flatMap((col) => col.results.map((r) => ({ ...r, column: col.name,
    searchText: `${r.expected} ${r.best_match || ""}`.toLowerCase() })));
  state.page = 0;
  const reset = () => { state.page = 0; renderTables(); };
  document.getElementById("statusFilter").addEventListener("change", reset);
  let searchTimer;
  const token = state.viewToken;
  document.getElementById("search").addEventListener("input", () => {
    clearTimeout(searchTimer); searchTimer = setTimeout(() => { if (token === state.viewToken) reset(); }, 180);
  });
  renderTables();
}

function renderTables() {
  const container = document.getElementById("tables");
  if (!container || !state.lastResult) return;
  const filter = document.getElementById("statusFilter").value;
  const query = document.getElementById("search").value.trim().toLowerCase();
  const rows = state.rows.filter((r) => (!filter || r.status === filter) && (!query || r.searchText.includes(query)));
  const pageSize = 100, pages = Math.max(1, Math.ceil(rows.length / pageSize));
  state.page = Math.min(state.page, pages - 1);
  container.replaceChildren();
  if (!rows.length) container.appendChild(el("p", { class: "muted" }, "No results match the current filter."));
  else {
    const visible = rows.slice(state.page * pageSize, (state.page + 1) * pageSize);
    const table = el("table", { html:
      "<thead><tr><th scope='col'>Column</th><th scope='col'>Row</th><th scope='col'>Spreadsheet value</th><th scope='col'>Result</th><th scope='col'>Matched via</th><th scope='col'>Details</th></tr></thead><tbody>" +
      visible.map((r) => {
        const human = HUMAN[r.status] || HUMAN.MISSING;
        let details = esc(detailText(r));
        if (r.status === "FUZZY" && r.diff?.length) details += `<div class="diffline">${diffHtml(r.diff, r.best_match)}</div>`;
        return `<tr><td>${esc(r.column)}</td><td>${r.row}</td><td>${esc(r.expected) || '<span class="muted">(empty)</span>'}</td>` +
          `<td><span class="badge b-${esc(r.status)}">${human.icon} ${esc(human.label)}</span></td><td>${sourceBadge(r.source)}</td><td>${details}</td></tr>`;
      }).join("") + "</tbody>" });
    container.appendChild(el("div", { class: "table-scroll", tabindex: "0", role: "region", "aria-label": "Check results" }, table));
  }
  const pager = document.getElementById("pagination");
  pager.replaceChildren(
    el("button", { disabled: state.page === 0, onclick: () => { state.page--; renderTables(); } }, "Previous"),
    el("span", { role: "status", "aria-live": "polite" }, `${rows.length} results · Page ${state.page + 1} of ${pages}`),
    el("button", { disabled: state.page + 1 >= pages, onclick: () => { state.page++; renderTables(); } }, "Next")
  );
}

// ---- History views ----------------------------------------------------------
async function historyView() {
  clearView();
  view().appendChild(el("div", { class: "panel", id: "histPanel", html: '<p class="muted">Loading history…</p>' }));
  const token = state.viewToken;
  try {
    const data = await api.history();
    if (token !== state.viewToken) return;
    renderHistory(data.runs);
  } catch (e) {
    if (e.status === 401) return redirectLogin();
    if (token !== state.viewToken) return;
    document.getElementById("histPanel").innerHTML = "";
    document.getElementById("histPanel").appendChild(banner("err", "Could not load history: " + esc(e.message)));
  }
}

function renderHistory(runs) {
  const panel = document.getElementById("histPanel");
  panel.innerHTML = "<h2>Run history</h2>";
  if (!runs.length) { panel.appendChild(el("p", { class: "muted" }, "No runs yet. Run a check to see it here.")); return; }
  const table = el("table", { html:
    "<thead><tr><th>When</th><th>Spreadsheet</th><th>PDF</th><th>Match rate</th>" +
    "<th>Found</th><th>With differences</th><th>Not found</th><th></th></tr></thead><tbody>" +
    runs.map((r) =>
      `<tr class="history-row" data-id="${esc(r.run_id)}">
        <td>${esc(r.created_at)}</td><td><a href="#/history/${esc(r.run_id)}">${esc(r.excel)}</a></td><td>${esc(r.pdf)}</td>
        <td>${(r.summary.pass_rate * 100).toFixed(0)}%</td>
        <td>${r.summary.exact}</td><td>${r.summary.fuzzy}</td><td>${r.summary.missing}</td>
        <td><button class="danger" data-del="${esc(r.run_id)}">Delete</button></td>
      </tr>`).join("") + "</tbody>" });
  panel.appendChild(table);

  table.querySelectorAll(".history-row").forEach((tr) => {
    tr.addEventListener("click", (ev) => {
      if (ev.target.matches("[data-del]")) return;
      location.hash = "#/history/" + tr.getAttribute("data-id");
    });
  });
  table.querySelectorAll("[data-del]").forEach((btn) => {
    btn.addEventListener("click", async (ev) => {
      ev.stopPropagation();
      const id = btn.getAttribute("data-del");
      const token = state.viewToken;
      btn.disabled = true;
      try { await api.deleteHistory(id); if (token === state.viewToken) historyView(); }
      catch (e) { btn.disabled = false; if (token === state.viewToken) alert("Delete failed: " + e.message); }
    });
  });
}

async function historyDetailView(id) {
  clearView();
  view().appendChild(el("div", { class: "panel", id: "detail", html: '<p class="muted">Loading…</p>' }));
  const token = state.viewToken;
  try {
    const r = await api.historyItem(id);
    if (token !== state.viewToken) return;
    const card = (l, v) => `<div class="card"><div class="n">${v}</div><div class="l">${l}</div></div>`;
    const flags = Object.entries(r.meta.flags || {}).filter(([, v]) => v).map(([k]) => k);
    document.getElementById("detail").innerHTML = `
      <p><a class="rowlink" href="#/history">← Back to history</a></p>
      <h2>${esc(r.excel)} vs ${esc(r.pdf)}</h2>
      <p class="muted">${esc(r.created_at)} · threshold ${r.meta.fuzzy_threshold}
        ${flags.length ? "· flags: " + flags.map(esc).join(", ") : ""}</p>
      <div class="cards">
        ${card("Values checked", r.summary.total - r.summary.skipped)}${card("Found", r.summary.exact)}
        ${card("With differences", r.summary.fuzzy)}${card("Not found", r.summary.missing)}
        ${card("Blank", r.summary.skipped)}${card("Match rate", (r.summary.pass_rate * 100).toFixed(0) + "%")}
      </div>
      <div style="margin-top:1rem;">
        <a class="report" href="/reports/${esc(r.run_id)}.html" target="_blank" rel="noopener">Printable report</a> &nbsp;
        <a class="report" href="/reports/${esc(r.run_id)}.xlsx">Excel report</a>
        <span class="muted">(reports expire ~1h after the run; the summary above persists)</span>
      </div>`;
  } catch (e) {
    if (e.status === 401) return redirectLogin();
    if (token !== state.viewToken) return;
    document.getElementById("detail").innerHTML = "";
    document.getElementById("detail").appendChild(banner("err", "Could not load run: " + esc(e.message)));
  }
}

// ---- Login view -------------------------------------------------------------
function loginView() {
  clearView();
  if (state.running) { view().appendChild(banner("warn", 'A check is running. <a href="#/check">Return to the check</a> before switching users.')); return; }
  const root = el("div", { class: "auth-wrap" },
    el("div", { class: "panel", html: `
      <h2>Sign in</h2>
      <div class="field"><label for="u">Username</label><input type="text" id="u" autocomplete="username"></div>
      <div class="field"><label for="p">Password</label><input type="password" id="p" autocomplete="current-password"></div>
      <div id="loginMsg"></div>
      <button class="primary" id="loginBtn">Sign in</button>` })
  );
  view().appendChild(root);
  const token = state.viewToken;
  let submitting = false;
  const submit = async () => {
    if (submitting) return;
    submitting = true;
    const button = document.getElementById("loginBtn"); button.disabled = true;
    const u = document.getElementById("u").value.trim();
    const p = document.getElementById("p").value;
    document.getElementById("loginMsg").innerHTML = "";
    try {
      const res = await api.login(u, p);
      if (token !== state.viewToken) return;
      state.user = res;
      refreshUserBox();
      location.hash = "#/check";
    } catch (e) {
      if (token === state.viewToken) document.getElementById("loginMsg").appendChild(banner("err", esc(e.message)));
    } finally { submitting = false; if (token === state.viewToken) button.disabled = false; }
  };
  document.getElementById("loginBtn").addEventListener("click", submit);
  document.getElementById("p").addEventListener("keydown", (e) => { if (e.key === "Enter") submit(); });
}

// ---- chrome / router --------------------------------------------------------
function refreshUserBox() {
  const box = document.getElementById("userBox");
  const authOn = state.health && state.health.auth_enabled;
  if (authOn && state.user && state.user.authenticated) {
    document.getElementById("userName").textContent = state.user.username;
    box.classList.remove("hidden");
    document.getElementById("logoutBtn").disabled = state.running;
  } else {
    box.classList.add("hidden");
  }
}

function setActiveNav(route) {
  document.querySelectorAll("#nav a[data-route]").forEach((a) =>
    a.classList.toggle("active", a.getAttribute("data-route") === route));
}

function redirectLogin() { state.user = null; state.lastResult = null; state.rows = []; refreshUserBox(); location.hash = "#/login"; }

// ---- theme (dark / light) ---------------------------------------------------
function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  const btn = document.getElementById("themeBtn");
  if (btn) btn.textContent = theme === "dark" ? "☀️ Light" : "🌙 Dark";
  try { localStorage.setItem("proofcheck-theme", theme); } catch (_) { /* private mode */ }
}
function initTheme() {
  let theme = null;
  try { theme = localStorage.getItem("proofcheck-theme"); } catch (_) { /* ignore */ }
  if (!theme) {
    const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    theme = prefersDark ? "dark" : "light";
  }
  applyTheme(theme);
}
function toggleTheme() {
  applyTheme(document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark");
}

async function router() {
  const hash = location.hash || "#/check";
  const parts = hash.replace(/^#\//, "").split("/");
  const route = parts[0] || "check";
  const authOn = state.health && state.health.auth_enabled;

  // Gate everything except the login screen when auth is enabled and we're not signed in.
  if (authOn && !(state.user && state.user.authenticated) && route !== "login") {
    return redirectLogin();
  }

  setActiveNav(route === "history" ? "history" : route === "check" ? "check" : "");
  if (route === "login") return loginView();
  if (route === "history") return parts[1] ? historyDetailView(parts[1]) : historyView();
  return checkView();
}

async function boot() {
  initTheme();
  document.getElementById("themeBtn").addEventListener("click", toggleTheme);
  document.getElementById("logoutBtn").addEventListener("click", async () => {
    if (state.running) return;
    try { await api.logout(); } catch (_) { /* ignore */ }
    state.lastResult = null; state.inspectData = null; state.rows = [];
    state.user = { username: "", authenticated: false };
    refreshUserBox();
    redirectLogin();
  });

  try { state.health = await api.health(); } catch (_) { state.health = { auth_enabled: false, ocr_available: false, version: "?" }; }
  document.getElementById("footer").textContent =
    `ProofCheck v${state.health.version} · deterministic, offline` +
    (state.health.auth_enabled ? " · auth enabled" : "");

  if (state.health.auth_enabled) {
    try { state.user = await api.me(); } catch (_) { state.user = { username: "", authenticated: false }; }
  } else {
    state.user = { username: "anonymous", authenticated: false };
  }
  refreshUserBox();

  document.addEventListener("paste", handlePaste);
  window.addEventListener("hashchange", router);
  router();
}

boot();
