const launcher = document.getElementById("chat-launcher");
const win = document.getElementById("chat-window");
const header = document.getElementById("chat-header");
const closeBtn = document.getElementById("chat-close");
const minBtn = document.getElementById("chat-min");
const statusEl = document.getElementById("chat-status");
const form = document.getElementById("chat-form");
const input = document.getElementById("chat-input");
const messagesEl = document.getElementById("chat-messages");
const langEl = document.getElementById("lang");

let minimized = false;
let isDragging = false;
let dragOffsetX = 0;
let dragOffsetY = 0;
let activePointerId = null;

const state = {
  lang: "mn",
  messages: [],
};

let thinkingEl = null;

function renderMarkdown(text) {
  const raw = String(text ?? "");
  if (window.marked && window.DOMPurify) {
    const html = window.marked.parse(raw, {
      gfm: true,
      breaks: true,
      headerIds: false,
      mangle: false,
    });
    return window.DOMPurify.sanitize(html, { USE_PROFILES: { html: true } });
  }
  // Fallback (should rarely happen): escape
  const div = document.createElement("div");
  div.textContent = raw;
  return div.innerHTML;
}

function setStatus(text) {
  statusEl.textContent = text;
}

function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function addMessage(role, content) {
  state.messages.push({ role, content });
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.innerHTML = renderMarkdown(content);
  messagesEl.appendChild(div);
  scrollToBottom();
}

function showThinking() {
  if (thinkingEl) return;
  thinkingEl = document.createElement("div");
  thinkingEl.className = "msg assistant thinking";
  thinkingEl.setAttribute("aria-label", "Thinking");
  const typing = document.createElement("div");
  typing.className = "typing";
  typing.innerHTML = "<span></span><span></span><span></span>";
  thinkingEl.appendChild(typing);
  messagesEl.appendChild(thinkingEl);
  scrollToBottom();
}

function hideThinking() {
  if (!thinkingEl) return;
  thinkingEl.remove();
  thinkingEl = null;
}

function addMeta(content) {
  const div = document.createElement("div");
  div.className = "msg meta";
  div.textContent = content;
  messagesEl.appendChild(div);
  scrollToBottom();
}

function openChat() {
  win.classList.add("open");
  win.setAttribute("aria-hidden", "false");
  launcher.style.display = "none";
  minimized = false;
  win.style.height = "520px";
  input.focus();

  if (state.messages.length === 0) {
    const greet =
      state.lang === "en"
        ? "Hi! I’m Nero. Ask me anything."
        : "Сайн байна уу! Би Nero. Юу асуух вэ?";
    addMessage("assistant", greet);
  }
}

function closeChat() {
  win.classList.remove("open");
  win.setAttribute("aria-hidden", "true");
  launcher.style.display = "inline-flex";
}

function toggleMinimize() {
  minimized = !minimized;
  if (minimized) {
    win.style.height = "56px";
    setStatus(state.lang === "en" ? "Minimized" : "Жижиглэсэн");
  } else {
    win.style.height = "520px";
    setStatus("Ready");
  }
}

async function sendToServer(userText) {
  setStatus(state.lang === "en" ? "Thinking…" : "Бодож байна…");
  showThinking();
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      lang: state.lang,
      messages: state.messages,
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const msg = err.error || `HTTP ${res.status}`;
    throw new Error(msg);
  }
  const data = await res.json();
  return data.reply;
}

launcher.addEventListener("click", openChat);
closeBtn.addEventListener("click", closeChat);
minBtn.addEventListener("click", toggleMinimize);

langEl.addEventListener("change", () => {
  state.lang = langEl.value || "mn";
  addMeta(state.lang === "en" ? "Language: English" : "Хэл: Монгол");
});

// Drag behavior
function startDrag(clientX, clientY) {
  isDragging = true;
  const rect = win.getBoundingClientRect();
  dragOffsetX = clientX - rect.left;
  dragOffsetY = clientY - rect.top;

  // Convert from bottom/right anchored to top/left anchored on first drag
  win.style.right = "auto";
  win.style.bottom = "auto";
  win.style.left = `${rect.left}px`;
  win.style.top = `${rect.top}px`;
}

function moveDrag(clientX, clientY) {
  if (!isDragging) return;
  const newLeft = clientX - dragOffsetX;
  const newTop = clientY - dragOffsetY;

  const margin = 8;
  const maxLeft = window.innerWidth - win.offsetWidth - margin;
  const maxTop = window.innerHeight - win.offsetHeight - margin;

  win.style.left = `${Math.min(Math.max(newLeft, margin), maxLeft)}px`;
  win.style.top = `${Math.min(Math.max(newTop, margin), maxTop)}px`;
}

function endDrag() {
  isDragging = false;
  activePointerId = null;
}

// Pointer events (works for mouse + touch)
header.addEventListener("pointerdown", (e) => {
  if (!win.classList.contains("open")) return;
  if (activePointerId !== null) return;
  activePointerId = e.pointerId;
  header.setPointerCapture(e.pointerId);
  startDrag(e.clientX, e.clientY);
});

header.addEventListener("pointermove", (e) => {
  if (!isDragging || e.pointerId !== activePointerId) return;
  moveDrag(e.clientX, e.clientY);
});

header.addEventListener("pointerup", (e) => {
  if (e.pointerId !== activePointerId) return;
  endDrag();
});

header.addEventListener("pointercancel", (e) => {
  if (e.pointerId !== activePointerId) return;
  endDrag();
});

// Submit
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = (input.value || "").trim();
  if (!text) return;
  input.value = "";

  addMessage("user", text);
  try {
    const reply = await sendToServer(text);
    hideThinking();
    addMessage("assistant", reply);
    setStatus("Ready");
  } catch (err) {
    hideThinking();
    addMessage(
      "assistant",
      state.lang === "en"
        ? `Sorry — error: ${err.message}`
        : `Уучлаарай — алдаа: ${err.message}`
    );
    setStatus(state.lang === "en" ? "Error" : "Алдаа");
  }
});

// ESC closes
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && win.classList.contains("open")) closeChat();
});

