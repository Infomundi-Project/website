(function () {
  let state = {
  storyId: null,
  title: "",
  description: "",
  url: "",
  history: [],
  suggestions: [],   // NEW
  isSending: false,
};

const els = {
  messages: null,
  suggestions: null, // NEW
  form: null,
  input: null,
  send: null,
  error: null,
};

  function getCSRF() {
    const m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute("content") : null;
  }

  // ——— UI helpers ———
  function ensureElements() {
  els.messages = document.getElementById("maximusChatMessages");
  els.suggestions = document.getElementById("maximusChatSuggestions"); // NEW
  els.form = document.getElementById("maximusChatForm");
  els.input = document.getElementById("maximusChatInput");
  els.send = document.getElementById("maximusChatSend");
  els.error = document.getElementById("maximusChatError");
}

  function escapeText(s) {
    // Prevent XSS in message bubbles
    return s.replace(/[&<>"']/g, m => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]));
  }

  function renderSuggestions() {
  if (!els.suggestions) return;
  els.suggestions.innerHTML = "";
  if (!state.suggestions || state.suggestions.length === 0) {
    els.suggestions.classList.add("d-none");
    return;
  }
  els.suggestions.classList.remove("d-none");

  state.suggestions.forEach((q, idx) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "maximus-chat__suggestion";
    chip.textContent = q;
    chip.setAttribute("aria-label", `Ask: ${q}`);
    chip.addEventListener("click", () => {
      // remove chip immediately (moved to chat as user message)
      state.suggestions.splice(idx, 1);
      renderSuggestions();
      saveHistory();
      sendMessage(q);
    });
    els.suggestions.appendChild(chip);
  });
}

async function sendMessage(text) {
  if (state.isSending) return;
  const content = (text || "").trim();
  if (!content) return;

  setError("");
  disableComposer(true);

  addBubble("user", content);
  const typingBubble = addBubble("assistant", "", { typing: true });

  const payload = {
    message: content,
    history: state.history.slice(-10),
    title: state.title,
  };

  try {
    const headers = { "Content-Type": "application/json" };
    const csrf = getCSRF();
    if (csrf) headers["X-CSRFToken"] = csrf;

    const res = await fetch(`/api/story/chat/${encodeURIComponent(state.storyId)}`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      let msg = "Failed to get a reply.";
      try { const e = await res.json(); msg = e.message || e.error || msg; } catch {}
      throw new Error(msg);
    }

    const data = await res.json();
    const reply = data.response || "…";
    replaceTypingBubble(typingBubble, reply);

    state.history.push({ role: "user", content });
    state.history.push({ role: "assistant", content: reply });
    state.history = state.history.slice(-12);
    saveHistory();
  } catch (err) {
    replaceTypingBubble(typingBubble, "Sorry, I couldn’t answer right now.");
    setError(err.message || "Something went wrong.");
  } finally {
    disableComposer(false);
  }
}


  function addBubble(role, text, options = {}) {
    const row = document.createElement("div");
    row.className = `maximus-chat__row maximus-chat__row--${role === "user" ? "user" : "ai"}`;

    if (role !== "user") {
      const avatar = document.createElement("img");
      avatar.className = "maximus-chat__avatar";
      avatar.alt = "Maximus";
      avatar.src = "/static/img/illustrations/maximus.webp";
      row.appendChild(avatar);
    }

    const bubble = document.createElement("div");
    bubble.className = `maximus-bubble ${role === "user" ? "maximus-bubble--user" : "maximus-bubble--ai"}`;

    if (options.typing) {
      const typing = document.createElement("span");
      typing.className = "maximus-typing";
      typing.innerHTML = `<span class="maximus-dot"></span><span class="maximus-dot"></span><span class="maximus-dot"></span>`;
      bubble.appendChild(typing);
    } else {
      bubble.innerHTML = escapeText(text);
    }

    row.appendChild(bubble);
    els.messages.appendChild(row);
    els.messages.scrollTop = els.messages.scrollHeight;
    return bubble;
  }

  function replaceTypingBubble(bubbleEl, text) {
    bubbleEl.innerHTML = escapeText(text);
    els.messages.scrollTop = els.messages.scrollHeight;
  }

  function setError(msg) {
    if (!els.error) return;
    if (!msg) {
      els.error.classList.add("d-none");
      els.error.textContent = "";
    } else {
      els.error.classList.remove("d-none");
      els.error.textContent = msg;
    }
  }

  function disableComposer(disabled) {
    if (!els.input || !els.send) return;
    els.input.disabled = disabled;
    els.send.disabled = disabled;
    state.isSending = disabled;
  }

  // ——— Persistence (per story, per tab) ———
  function storageKey(storyId) {
    return `maximus-chat:${storyId}`;
  }

  function saveHistory() {
  if (!state.storyId) return;
  try {
    sessionStorage.setItem(storageKey(state.storyId), JSON.stringify({
      history: state.history.slice(-12),
      suggestions: state.suggestions.slice(0, 12), // keep it lean
    }));
  } catch {}
}

function restoreHistory(storyId) {
  try {
    const raw = sessionStorage.getItem(storageKey(storyId));
    if (!raw) return { history: [], suggestions: [] };
    const parsed = JSON.parse(raw);
    return {
      history: Array.isArray(parsed.history) ? parsed.history : [],
      suggestions: Array.isArray(parsed.suggestions) ? parsed.suggestions : [],
    };
  } catch {
    return { history: [], suggestions: [] };
  }
}


  // ——— Public init ———
  window.initMaximusChat = function ({ storyId, title, description, url }) {
  ensureElements();
  setError("");
  els.messages.innerHTML = "";
  if (els.suggestions) els.suggestions.innerHTML = "";

  state.storyId = storyId;
  state.title = title || "";
  state.description = description || "";
  state.url = url || "";

  // Restore per-story session state
  const restored = restoreHistory(storyId);
  state.history = restored.history || [];
  state.suggestions = restored.suggestions || [];

  renderSuggestions();

  if (state.history.length === 0) {
    addBubble("assistant",
      `Hi—I'm Maximus. Ask me anything about: “${state.title}”. You can also tap a suggested question.`);
  } else {
    for (const m of state.history) addBubble(m.role, m.content);
  }

  if (els.form && !els.form.dataset.bound) {
    els.form.dataset.bound = "1";
    els.form.addEventListener("submit", (e) => {
      e.preventDefault();
      sendMessage(els.input.value);
      els.input.value = "";
    });
    els.input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        els.form.requestSubmit();
      }
    });
  }

  // If summary already stashed questions on the container (see summary JS change below),
  // pick them up now:
  const apiBox = document.querySelector(".maximus-summary-api-response");
  if (apiBox?.dataset?.suggestedQuestions && state.suggestions.length === 0) {
    try {
      const q = JSON.parse(apiBox.dataset.suggestedQuestions);
      if (Array.isArray(q) && q.length) {
        state.suggestions = q.slice(0, 12);
        delete apiBox.dataset.suggestedQuestions;
        saveHistory();
        renderSuggestions();
      }
    } catch {}
  }
};

// Expose a setter the summary code can call as soon as it has the questions:
window.setMaximusChatSuggestions = function (questions) {
  if (!Array.isArray(questions)) return;
  // Replace current suggestions with fresh ones for this story
  state.suggestions = questions.slice(0, 12);
  saveHistory();
  renderSuggestions();
};


  async function onSend(e) {
    e.preventDefault();
    if (state.isSending) return;

    const content = (els.input.value || "").trim();
    if (!content) return;

    setError("");
    disableComposer(true);

    // UI: append user msg
    addBubble("user", content);
    els.input.value = "";

    // UI: show typing placeholder
    const typingBubble = addBubble("assistant", "", { typing: true });

    // Build payload
    const payload = {
      message: content,
      history: state.history.slice(-10),     // keep last N exchanges for grounding
      title: state.title,                    // small hint (backend can ignore if it rebuilds)
    };

    try {
      const headers = { "Content-Type": "application/json" };
      const csrf = getCSRF();
      if (csrf) headers["X-CSRFToken"] = csrf;

      const res = await fetch(`/api/story/chat/${encodeURIComponent(state.storyId)}`, {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        let msg = "Failed to get a reply.";
        try {
          const e = await res.json();
          msg = e.message || e.error || msg;
        } catch {}
        throw new Error(msg);
      }

      const data = await res.json();
      const reply = data.response || "…";
      replaceTypingBubble(typingBubble, reply);

      // Update rolling history
      state.history.push({ role: "user", content });
      state.history.push({ role: "assistant", content: reply });
      state.history = state.history.slice(-12);
      saveHistory();
    } catch (err) {
      replaceTypingBubble(typingBubble, "Sorry, I couldn’t answer right now.");
      setError(err.message || "Something went wrong.");
    } finally {
      disableComposer(false);
    }
  }
})();
