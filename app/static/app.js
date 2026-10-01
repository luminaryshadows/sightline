/* Private Sight — local testing UI client logic.
   Talks only to the local server on 127.0.0.1. No external requests. */

(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);

  let selectedFile = null;
  let currentDocumentId = null;
  let lastResult = null;

  // ── Helpers ───────────────────────────────────────────────

  async function postJSON(url, body) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
  }

  async function getJSON(url) {
    const res = await fetch(url);
    return res.json();
  }

  function fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const result = reader.result || "";
        const comma = result.indexOf(",");
        resolve(comma >= 0 ? result.slice(comma + 1) : result);
      };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  function setStatus(msg, isError) {
    const el = $("scan-status");
    el.textContent = msg;
    el.style.color = isError ? "var(--danger)" : "var(--ink-dim)";
  }

  async function speak(text) {
    if (!text) return;
    try {
      await postJSON("/api/speak", { text });
    } catch (e) {
      // Non-fatal: TTS may be unavailable
      console.warn("TTS unavailable:", e.message);
    }
  }

  // ── Status panel ──────────────────────────────────────────

  async function refreshStatus() {
    try {
      const s = await getJSON("/api/status");
      const p = s.privacy;
      $("s-net").textContent = p.network_requests;
      $("s-loc").textContent = p.processing_location.toUpperCase();
      $("s-model").textContent = p.model_source.toUpperCase();
      $("s-privacy").textContent = p.privacy_status.toUpperCase();
      $("s-privacy").className = "ok";
      $("s-docs").textContent = p.documents_in_session;
      $("s-tts").textContent = s.tts_available
        ? `${s.tts_engine} (local)`
        : "not available";
      $("s-tts").className = s.tts_available ? "ok" : "warn";
    } catch (e) {
      console.warn("status failed", e);
    }
  }

  // ── File selection ────────────────────────────────────────

  function applyFile(file) {
    selectedFile = file;
    const wrap = $("preview-wrap");
    const img = $("preview");
    const url = URL.createObjectURL(file);
    img.onload = () => URL.revokeObjectURL(url);
    img.src = url;
    wrap.hidden = false;
    $("scan-btn").disabled = false;
    setStatus(`Selected: ${file.name} (${Math.round(file.size / 1024)} KB)`);
  }

  $("file-input").addEventListener("change", (e) => {
    const file = e.target.files && e.target.files[0];
    if (file) applyFile(file);
  });

  async function loadDemo(path, label) {
    setStatus(`Loading ${label}...`);
    try {
      const res = await fetch(path);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      applyFile(new File([blob], label, { type: blob.type || "image/png" }));
    } catch (e) {
      setStatus(`Could not load ${label}: ${e.message}`, true);
    }
  }

  $("demo-btn").addEventListener("click", () =>
    loadDemo("/static/demo/prescription.png", "prescription.png"));
  $("demo-bank-btn").addEventListener("click", () =>
    loadDemo("/static/demo/banking.png", "banking.png"));
  $("demo-gov-btn").addEventListener("click", () =>
    loadDemo("/static/demo/government_letter.png", "government_letter.png"));

  // ── Scan ──────────────────────────────────────────────────

  $("scan-btn").addEventListener("click", async () => {
    if (!selectedFile) return;
    $("scan-btn").disabled = true;
    setStatus("Reading document on this device... (this may take several seconds)");

    try {
      const imageBase64 = await fileToBase64(selectedFile);
      const data = await postJSON("/api/scan", {
        image_base64: imageBase64,
        filename: selectedFile.name,
      });
      currentDocumentId = data.document_id;
      lastResult = data.analysis;
      renderResult(data.analysis);
      setStatus("Done. Results shown below.");
      await refreshStatus();

      // Announce the summary automatically (accessibility requirement)
      if (data.analysis.accessible_summary) {
        speak(data.analysis.accessible_summary);
      }
    } catch (e) {
      setStatus(`Analysis failed: ${e.message}`, true);
    } finally {
      $("scan-btn").disabled = false;
    }
  });

  // ── Render ────────────────────────────────────────────────

  function renderResult(a) {
    $("results-card").hidden = false;

    // Document type
    const typeEmoji = {
      prescription: "💊", banking: "🏦", government: "🏛️",
      bill: "🧾", legal: "⚖️", id: "🪪", unknown: "❓",
    };
    const dtype = a.document_type || "unknown";
    $("r-doctype").textContent = `${typeEmoji[dtype] || "📄"} ${dtype.charAt(0).toUpperCase() + dtype.slice(1)}`;
    $("r-confidence").textContent =
      `Classification confidence: ${(a.confidence * 100).toFixed(0)}% · ` +
      `OCR confidence: ${a.ocr ? (a.ocr.confidence * 100).toFixed(0) : 0}% · ` +
      `${a.processing_time_ms} ms`;

    // Summary
    $("r-summary").textContent = a.accessible_summary || "(no summary)";

    // Sensitive info
    const sd = a.sensitive_data || {};
    if (sd.detected) {
      const types = (sd.entity_types || []).join(", ") || "unknown types";
      $("r-sensitive").textContent =
        `⚠ Detected — risk level ${sd.risk_level.toUpperCase()} · ${sd.entity_count} entities (${types})`;
    } else {
      $("r-sensitive").textContent = "✅ None detected";
    }
    const entityList = $("r-entities");
    entityList.innerHTML = "";

    // Fields
    const fieldsEl = $("r-fields");
    fieldsEl.innerHTML = "";
    const ex = a.extraction || {};
    (ex.fields || []).forEach((f) => {
      const dt = document.createElement("dt"); dt.textContent = f.label;
      const dd = document.createElement("dd"); dd.textContent = f.value;
      fieldsEl.appendChild(dt); fieldsEl.appendChild(dd);
    });
    (ex.monetary_values || []).forEach((m) => {
      const dt = document.createElement("dt"); dt.textContent = m.description;
      const dd = document.createElement("dd"); dd.textContent = m.amount;
      fieldsEl.appendChild(dt); fieldsEl.appendChild(dd);
    });
    (ex.deadlines || []).forEach((d) => {
      const dt = document.createElement("dt"); dt.textContent = d.description;
      const dd = document.createElement("dd"); dd.textContent = d.date;
      fieldsEl.appendChild(dt); fieldsEl.appendChild(dd);
    });
    (ex.contacts || []).forEach((c) => {
      const dt = document.createElement("dt"); dt.textContent = c.type;
      const dd = document.createElement("dd"); dd.textContent = c.value;
      fieldsEl.appendChild(dt); fieldsEl.appendChild(dd);
    });
    if (!fieldsEl.children.length) {
      const dt = document.createElement("dt"); dt.textContent = "—";
      const dd = document.createElement("dd"); dd.textContent = "No fields extracted";
      fieldsEl.appendChild(dt); fieldsEl.appendChild(dd);
    }

    // Action
    const action = ex.action_required || "";
    const trivial = ["", "No immediate action identified.", "No action required.",
      "No specific action identified. Please review the document."];
    $("r-action").textContent = trivial.includes(action) ? "" : `⚡ ${action}`;

    // Warnings
    const warnEl = $("r-warnings");
    warnEl.innerHTML = "";
    const warns = a.warnings || [];
    if (!warns.length) {
      const li = document.createElement("li");
      li.textContent = "No warnings.";
      li.style.color = "var(--accent)";
      warnEl.appendChild(li);
    } else {
      warns.forEach((w) => {
        const li = document.createElement("li");
        li.textContent = w;
        warnEl.appendChild(li);
      });
    }

    // Full text
    $("r-fulltext").textContent = (a.ocr && a.ocr.full_text) || "(no text)";

    // Reset sub-panels
    $("fulltext-wrap").hidden = true;
    $("ask-wrap").hidden = true;
    $("r-answer").textContent = "";
    $("read-answer-btn").hidden = true;

    $("results-card").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // ── Result actions ────────────────────────────────────────

  $("read-summary-btn").addEventListener("click", () => {
    if (lastResult) speak(lastResult.accessible_summary || "");
  });

  $("fulltext-btn").addEventListener("click", () => {
    $("fulltext-wrap").hidden = !$("fulltext-wrap").hidden;
  });

  $("read-full-btn").addEventListener("click", () => {
    if (lastResult && lastResult.ocr) speak(lastResult.ocr.full_text || "");
  });

  $("ask-toggle-btn").addEventListener("click", () => {
    $("ask-wrap").hidden = !$("ask-wrap").hidden;
    if (!$("ask-wrap").hidden) $("question-input").focus();
  });

  async function askQuestion(q) {
    if (!q || !currentDocumentId) return;
    $("r-answer").textContent = "Searching the document...";
    $("read-answer-btn").hidden = true;
    try {
      const data = await postJSON("/api/ask", {
        document_id: currentDocumentId,
        question: q,
      });
      let text = data.answer;
      if (data.is_medical && data.medical_disclaimer) {
        text += "\n\n⚕ " + data.medical_disclaimer;
      }
      $("r-answer").textContent = text;
      $("read-answer-btn").hidden = false;
      speak(data.answer); // speak just the answer, not the disclaimer
    } catch (e) {
      $("r-answer").textContent = `Could not answer: ${e.message}`;
    }
  }

  $("ask-btn").addEventListener("click", () => askQuestion($("question-input").value.trim()));
  $("question-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") askQuestion($("question-input").value.trim());
  });
  document.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const q = chip.getAttribute("data-q");
      $("question-input").value = q;
      askQuestion(q);
    });
  });
  $("read-answer-btn").addEventListener("click", () => speak($("r-answer").textContent));

  // ── Deletion ──────────────────────────────────────────────

  $("delete-btn").addEventListener("click", async () => {
    if (!currentDocumentId) return;
    const data = await postJSON("/api/delete", { document_id: currentDocumentId });
    currentDocumentId = null;
    lastResult = null;
    $("results-card").hidden = true;
    $("preview-wrap").hidden = true;
    $("scan-btn").disabled = true;
    selectedFile = null;
    $("file-input").value = "";
    setStatus(`Deleted. ${JSON.stringify(data.report)}`);
    await refreshStatus();
  });

  $("scan-again-btn").addEventListener("click", () => {
    $("results-card").hidden = true;
    $("preview-wrap").hidden = true;
    $("scan-btn").disabled = true;
    selectedFile = null;
    $("file-input").value = "";
    setStatus("Choose a new document image.");
    window.scrollTo({ top: 0, behavior: "smooth" });
  });

  $("delete-all-btn").addEventListener("click", async () => {
    const data = await postJSON("/api/delete-all", {});
    currentDocumentId = null;
    lastResult = null;
    $("results-card").hidden = true;
    setStatus(`All session data deleted: ${JSON.stringify(data.report)}`);
    await refreshStatus();
  });

  $("refresh-status-btn").addEventListener("click", refreshStatus);

  // ── Init ──────────────────────────────────────────────────

  refreshStatus();
  setInterval(refreshStatus, 5000);
})();
