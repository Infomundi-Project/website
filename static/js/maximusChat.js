(function () {
  let state = {
    storyId: null,
    title: "",
    description: "",
    url: "",
    // Keep short rolling history (assistant/user messages only)
    history: [], // [{role:'user'|'assistant', content:'...'}]
    isSending: false,
  };

  const els = {
    messages: null,
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
    els.form = document.getElementById("maximusChatForm");
    els.input = document.getElementById("maximusChatInput");
    els.send = document.getElementById("maximusChatSend");
    els.error = document.getElementById("maximusChatError");
  }

  function escapeText(s) {
    // Prevent XSS in message bubbles
    return s.replace(/[&<>"']/g, m => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]));
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
        history: state.history.slice(-12) // keep it lean
      }));
    } catch {}
  }

  function restoreHistory(storyId) {
    try {
      const raw = sessionStorage.getItem(storageKey(storyId));
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed.history) ? parsed.history : [];
    } catch {
      return [];
    }
  }

  // ——— Public init ———
  window.initMaximusChat = function ({ storyId, title, description, url }) {
    ensureElements();
    setError("");
    els.messages.innerHTML = "";
    state.storyId = storyId;
    state.title = title || "";
    state.description = description || "";
    state.url = url || "";

    // Restore short history if present
    state.history = restoreHistory(storyId);

    if (state.history.length === 0) {
      addBubble("assistant",
        `Hi—I'm Maximus. Ask me anything about: “${state.title}”. I can fact-check against the article context and my structured summary.`);
    } else {
      // Re-render saved history
      for (const m of state.history) {
        addBubble(m.role, m.content);
      }
    }

    // Composer handlers (set once)
    if (els.form && !els.form.dataset.bound) {
      els.form.dataset.bound = "1";

      els.form.addEventListener("submit", onSend);
      els.input.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          els.form.requestSubmit();
        }
      });
    }
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
