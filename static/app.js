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

const state = {
  lang: "mn",
  messages: [],
};

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
  div.textContent = content;
  messagesEl.appendChild(div);
  scrollToBottom();
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
        ? "Hi! I’m your AI Assistant. Ask me anything."
        : "Сайн байна уу! Би таны AI Assistant. Юу асуух вэ?";
    addMessage("assistant", greet);
    addMeta(state.lang === "en" ? "Tip: drag the header to move." : "Зөвлөгөө: header-ийг чирээд байрлалаа өөрчилж болно.");
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
header.addEventListener("mousedown", (e) => {
  if (!win.classList.contains("open")) return;
  isDragging = true;
  const rect = win.getBoundingClientRect();
  dragOffsetX = e.clientX - rect.left;
  dragOffsetY = e.clientY - rect.top;

  // Convert from bottom/right anchored to top/left anchored on first drag
  win.style.right = "auto";
  win.style.bottom = "auto";
  win.style.left = `${rect.left}px`;
  win.style.top = `${rect.top}px`;
});

document.addEventListener("mousemove", (e) => {
  if (!isDragging) return;
  const newLeft = e.clientX - dragOffsetX;
  const newTop = e.clientY - dragOffsetY;

  const margin = 8;
  const maxLeft = window.innerWidth - win.offsetWidth - margin;
  const maxTop = window.innerHeight - win.offsetHeight - margin;

  win.style.left = `${Math.min(Math.max(newLeft, margin), maxLeft)}px`;
  win.style.top = `${Math.min(Math.max(newTop, margin), maxTop)}px`;
});

document.addEventListener("mouseup", () => {
  isDragging = false;
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
    addMessage("assistant", reply);
    setStatus("Ready");
  } catch (err) {
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

