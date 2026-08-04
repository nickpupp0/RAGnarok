const socket = io();

const chatLog = document.getElementById("chatLog");
const eventLog = document.getElementById("eventLog");
const tenantSelect = document.getElementById("tenantSelect");
const defenseSwitch = document.getElementById("defenseSwitch");
const defenseLabel = document.getElementById("defenseLabel");

function addChatMsg(who, text, sources) {
  const div = document.createElement("div");
  div.className = `msg ${who}`;
  div.innerHTML = `
    <div class="who">${who === "user" ? "you" : "helios support"}</div>
    <div class="body"></div>
    ${sources ? `<div class="sources">sources: ${sources.map(s => s.title).join(", ") || "none"}</div>` : ""}
  `;
  div.querySelector(".body").textContent = text;
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
}

function addEvent(kind, title, payload) {
  const div = document.createElement("div");
  div.className = `ev ${kind}`;
  const pre = document.createElement("pre");
  pre.textContent = JSON.stringify(payload, null, 2);
  div.innerHTML = `<div class="ev-title">${title}</div>`;
  div.appendChild(pre);
  eventLog.appendChild(div);
  eventLog.scrollTop = eventLog.scrollHeight;
}

// --- chat ---
document.getElementById("chatForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = document.getElementById("chatInput");
  const message = input.value.trim();
  if (!message) return;
  addChatMsg("user", message);
  input.value = "";

  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tenant_id: tenantSelect.value, message }),
  });
  const data = await res.json();
  addChatMsg("bot", data.answer, data.retrieved);
  if (data.context_leak || data.output_leak) {
    addChatMsg("bot", `⚠ leak detected — context_leak=${data.context_leak}, output_leak=${data.output_leak}`);
  }
});

// --- defense toggle ---
defenseSwitch.addEventListener("change", async () => {
  const enabled = defenseSwitch.checked;
  await fetch("/api/admin/defense_mode", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled }),
  });
});

socket.on("defense_mode", (data) => {
  defenseSwitch.checked = data.enabled;
  defenseLabel.textContent = data.enabled ? "DEFENDED" : "VULNERABLE";
  defenseLabel.className = `mode-label ${data.enabled ? "mode-on" : "mode-off"}`;
});

// --- tabs ---
document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(c => c.classList.add("hidden"));
    btn.classList.add("active");
    document.getElementById(`tab-${btn.dataset.tab}`).classList.remove("hidden");
  });
});

// --- ingest ---
document.getElementById("ingestBtn").addEventListener("click", async () => {
  const tenant_id = document.getElementById("ingestTenant").value;
  const title = document.getElementById("ingestTitle").value.trim();
  const content = document.getElementById("ingestContent").value.trim();
  if (!title || !content) return;

  await fetch("/api/admin/ingest", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tenant_id, title, content, source: "ui-upload" }),
  });
  document.getElementById("ingestTitle").value = "";
  document.getElementById("ingestContent").value = "";
});

// --- attacks ---
document.querySelectorAll(".attack-btn").forEach(btn => {
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    const original = btn.textContent;
    btn.textContent = "Running...";
    await fetch(`/api/attacks/run/${btn.dataset.attack}`, { method: "POST" });
    setTimeout(() => { btn.disabled = false; btn.textContent = original; }, 3000);
  });
});

socket.on("attack_log", (data) => {
  addEvent("flag", `attack script output: ${data.name}`, { output: data.output.split("\n") });
});

document.getElementById("resetBtn").addEventListener("click", async () => {
  await fetch("/api/admin/reset", { method: "POST" });
  chatLog.innerHTML = "";
  eventLog.innerHTML = "";
  refreshKb();
});

// --- kb browser ---
async function refreshKb() {
  const tenant = document.getElementById("kbTenantFilter").value;
  const res = await fetch(`/api/kb${tenant ? `?tenant_id=${tenant}` : ""}`);
  const docs = await res.json();
  const list = document.getElementById("kbList");
  list.innerHTML = docs.map(d => `
    <div class="kb-doc">
      <div class="kb-title">${d.title}</div>
      <div class="kb-meta">tenant=${d.tenant_id} · <span class="trust-${d.trust_level}">${d.trust_level}</span> · ${d.source}</div>
    </div>
  `).join("") || "<p class='hint'>No documents.</p>";
}
document.getElementById("refreshKbBtn").addEventListener("click", refreshKb);
document.getElementById("kbTenantFilter").addEventListener("change", refreshKb);

// --- live pipeline events ---
socket.on("retrieval", (data) => addEvent("retrieval", `retrieval — "${data.query}"`, data));
socket.on("response", (data) => addEvent((data.context_leak || data.output_leak) ? "flag" : "response", "response generated", data));
socket.on("ingest", (data) => addEvent("ingest", `document ingested: ${data.title}`, data));
socket.on("reset", () => addEvent("ingest", "knowledge base reset", {}));

// initial load
refreshKb();
