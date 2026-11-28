const input = document.getElementById("input");
const hint = document.getElementById("hint");
const sendButton = document.getElementById("send");
const newChatButton = document.getElementById("new-chat");

let chats = [];
let skills = [];
let activeId = null;
let sending = false;
let armedId = null;

document.getElementById("composer").addEventListener("submit", (event) => {
  event.preventDefault();
  send();
});

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    send();
  }
});

input.addEventListener("input", () => {
  resizeInput();
  updateSkillHint();
});

newChatButton.addEventListener("click", newChat);

document.addEventListener("click", () => {
  if (armedId === null) return;
  armedId = null;
  renderChats();
});

window.addEventListener("pagehide", () => {
  if (activeId) navigator.sendBeacon(`/api/chats/${activeId}/close`);
});

init().catch(() => {
  const box = document.getElementById("messages");
  box.innerHTML = "";
  box.append(noticeElement("The server could not be reached."));
});

async function init() {
  const response = await api("/api/skills");
  const data = await response.json();
  skills = data.skills || [];
  await loadChats();
  if (chats.length) await loadMessages(chats[0].id);
  else renderEmpty();
  input.focus();
}

function api(url, options) {
  return fetch(url, { cache: "no-store", ...(options || {}) });
}

async function loadChats() {
  const response = await api("/api/chats");
  const data = await response.json();
  chats = data.chats || [];
  renderChats();
}

function renderChats() {
  const list = document.getElementById("chat-list");
  list.innerHTML = "";
  for (const chat of chats) {
    const row = document.createElement("div");
    row.className = "chat-item" + (chat.id === activeId ? " active" : "");

    const select = document.createElement("button");
    select.type = "button";
    select.className = "chat-select";
    select.textContent = chat.title || "New chat";
    select.addEventListener("click", () => selectChat(chat.id));

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "chat-delete" + (armedId === chat.id ? " armed" : "");
    remove.textContent = armedId === chat.id ? "Delete" : "×";
    remove.setAttribute("aria-label", "Delete chat");
    remove.addEventListener("click", (event) => {
      event.stopPropagation();
      if (sending) return;
      if (armedId !== chat.id) {
        armedId = chat.id;
        renderChats();
        return;
      }
      armedId = null;
      deleteChat(chat.id);
    });

    row.append(select, remove);
    list.append(row);
  }
}

async function selectChat(id) {
  if (sending || id === activeId) return;
  const previous = activeId;
  activeId = id;
  renderChats();
  const naming = previous && previous !== id ? leaveChat(previous) : Promise.resolve();
  await loadMessages(id);
  await naming;
}

async function newChat() {
  if (sending) return;
  const previous = activeId;
  const response = await api("/api/chats", { method: "POST" });
  if (!response.ok) return;
  const chat = await response.json();
  const naming = previous && previous !== chat.id ? leaveChat(previous) : Promise.resolve();
  activeId = chat.id;
  await loadMessages(chat.id);
  await naming;
  await loadChats();
  input.focus();
}

async function leaveChat(id) {
  try {
    const response = await api(`/api/chats/${id}/close`, { method: "POST" });
    if (!response.ok) return;
    const data = await response.json();
    if (!data.chat) {
      chats = chats.filter((chat) => chat.id !== id);
    } else {
      const known = chats.some((chat) => chat.id === id);
      chats = known
        ? chats.map((chat) => (chat.id === id ? { ...chat, ...data.chat } : chat))
        : chats.concat(data.chat);
    }
    renderChats();
    if (activeId === id && data.chat) setHeader(data.chat);
  } catch (error) {
    // A later load reads the saved title.
  }
}

async function deleteChat(id) {
  const response = await api(`/api/chats/${id}`, { method: "DELETE" });
  if (!response.ok) return;
  const wasActive = activeId === id;
  if (wasActive) activeId = null;
  await loadChats();
  if (!wasActive) return;
  if (chats.length) await loadMessages(chats[0].id);
  else renderEmpty();
}

async function loadMessages(id) {
  const response = await api(`/api/chats/${id}`);
  if (!response.ok) {
    renderEmpty();
    return;
  }
  const data = await response.json();
  activeId = data.chat.id;
  setHeader(data.chat);
  renderMessages(data.messages || []);
  renderChats();
  scrollToBottom();
}

function renderEmpty() {
  activeId = null;
  setHeader({ title: "Jinance", active_skill: null });
  const box = document.getElementById("messages");
  box.innerHTML = "";
  const empty = document.createElement("div");
  empty.className = "empty";
  empty.textContent = "No chat yet. Start one, or type a message below.";
  box.append(empty);
  renderChats();
}

function setHeader(chat) {
  document.getElementById("chat-title").textContent = chat.title || "New chat";
  const tag = document.getElementById("skill-tag");
  if (chat.active_skill) {
    tag.hidden = false;
    tag.textContent = "/" + chat.active_skill;
  } else {
    tag.hidden = true;
    tag.textContent = "";
  }
}

function renderMessages(items) {
  const box = document.getElementById("messages");
  box.innerHTML = "";
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "Send a message to start.";
    box.append(empty);
    return;
  }
  for (const message of items) box.append(renderMessage(message));
}

function renderMessage(message) {
  if (message.type === "notice") return noticeElement(message.content);
  const row = document.createElement("div");
  row.className = "row " + (message.type === "user" ? "user" : "agent");
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  const who = document.createElement("div");
  who.className = "who";
  who.textContent = message.type === "user" ? "You" : "Agent";
  bubble.append(who);
  if (message.content) {
    const text = document.createElement("div");
    text.className = "text";
    renderMarkdown(text, message.content);
    bubble.append(text);
  }
  const attachments = attachmentElements(message);
  if (attachments) bubble.append(attachments);
  const time = document.createElement("div");
  time.className = "time";
  time.textContent = formatTime(message.created_at);
  bubble.append(time);
  row.append(bubble);
  return row;
}

function attachmentElements(message) {
  const box = document.createElement("div");
  box.className = "attachments";
  let count = 0;
  for (const name of message.images || []) {
    if (!safeFile(name)) continue;
    const img = document.createElement("img");
    img.src = "/images/" + encodeURIComponent(name);
    img.alt = "Chart";
    img.addEventListener("load", scrollToBottom);
    box.append(img);
    count += 1;
  }
  for (const name of message.files || []) {
    if (!safeFile(name)) continue;
    const link = document.createElement("a");
    link.href = "/reports/" + encodeURIComponent(name);
    link.target = "_blank";
    link.rel = "noopener";
    link.textContent = name;
    box.append(link);
    count += 1;
  }
  return count ? box : null;
}

function noticeElement(text) {
  const note = document.createElement("div");
  note.className = "notice";
  note.textContent = text;
  return note;
}

async function send() {
  if (sending) return;
  const text = input.value.trim();
  if (!text) return;
  sending = true;
  sendButton.disabled = true;
  newChatButton.disabled = true;
  input.value = "";
  resizeInput();
  updateSkillHint();

  const box = document.getElementById("messages");
  const empty = box.querySelector(".empty");
  if (empty) empty.remove();
  box.append(renderMessage({
    type: "user",
    content: text,
    created_at: new Date().toISOString(),
    images: [],
    files: [],
  }));
  const pending = document.createElement("div");
  pending.className = "row agent";
  const bubble = document.createElement("div");
  bubble.className = "bubble pending";
  bubble.textContent = "…";
  pending.append(bubble);
  box.append(pending);
  scrollToBottom();

  try {
    if (!activeId) {
      const created = await api("/api/chats", { method: "POST" });
      if (!created.ok) throw new Error("create");
      const chat = await created.json();
      activeId = chat.id;
      setHeader(chat);
      await loadChats();
    }
    const response = await api(`/api/chats/${activeId}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: text }),
    });
    if (!response.ok) {
      pending.remove();
      const payload = await response.json().catch(() => ({}));
      box.append(noticeElement(errorText(payload)));
      scrollToBottom();
      return;
    }
    await loadMessages(activeId);
    await loadChats();
  } catch (error) {
    if (pending.isConnected) pending.remove();
    box.append(noticeElement("The server could not be reached."));
    scrollToBottom();
  } finally {
    sending = false;
    sendButton.disabled = false;
    newChatButton.disabled = false;
    input.focus();
  }
}

function updateSkillHint() {
  input.classList.remove("skill-ok", "skill-bad");
  hint.textContent = "";
  const match = input.value.match(/^\/([A-Za-z0-9_-]*)/);
  if (!match || !match[1]) return;
  const name = match[1];
  if (skills.includes(name)) {
    input.classList.add("skill-ok");
    hint.textContent = "Skill " + name + " will be loaded";
    return;
  }
  const stillTyping = skills.some((skill) => skill.startsWith(name));
  const finished = /^\/[A-Za-z0-9_-]+(\s|$)/.test(input.value);
  if (!finished && stillTyping) return;
  input.classList.add("skill-bad");
  hint.textContent = "Skill " + name + " was not found";
}

function resizeInput() {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 160) + "px";
}

function scrollToBottom() {
  const box = document.getElementById("messages");
  box.scrollTop = box.scrollHeight;
  requestAnimationFrame(() => {
    box.scrollTop = box.scrollHeight;
  });
}

function formatTime(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function errorText(payload) {
  if (payload && typeof payload.detail === "string") return payload.detail;
  return "The message could not be sent.";
}

function safeFile(name) {
  return /^[A-Za-z0-9._-]+$/.test(name);
}
