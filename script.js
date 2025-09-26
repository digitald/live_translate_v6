// script.js (versione corretta)

const socket = io({
  reconnection: true, reconnectionAttempts: 5, reconnectionDelay: 1000,
  reconnectionDelayMax: 5000, timeout: 20000
});

// Element references
const player = document.getElementById("player");
const log = document.getElementById("log");
const statusEl = document.getElementById("status");
const playPauseBtn = document.getElementById("playPauseBtn");
const skipBtn = document.getElementById("skipBtn");
const sessionInfo = document.getElementById("sessionInfo");
const queueCount = document.getElementById("queueCount");
const downloadBtn = document.getElementById("downloadBtn");
const processBtn = document.getElementById("processBtn");
const downloadNotesBtn = document.getElementById("downloadNotesBtn");
const downloadNotesEnBtn = document.getElementById("downloadNotesEnBtn");
const viewSessionsBtn = document.getElementById("viewSessionsBtn");
const currentSessionEl = document.getElementById("currentSession");
const sessionsModal = document.getElementById("sessionsModal");
const sessionsList = document.getElementById("sessionsList");
const closeModal = document.querySelector(".close");

// State variables
let queue = [], playing = false, audioUrls = [], playbackPaused = true, selectedSessionId = null;

function selectSession(sessionData) {
  if (sessionData) {
    selectedSessionId = sessionData.id;
    currentSessionEl.textContent = `Selected: ${sessionData.id.substring(0, 20)}...`; // Mostra ID abbreviato
    currentSessionEl.style.color = "purple";
    
    // Attiva sempre il download della trascrizione per una sessione selezionata
    downloadBtn.disabled = false;
    
    // Attiva/disattiva i pulsanti degli appunti in base allo stato 'processed'
    processBtn.disabled = sessionData.processed;
    downloadNotesBtn.disabled = !sessionData.processed;
    downloadNotesEnBtn.disabled = !sessionData.processed;
  } else {
    selectedSessionId = null;
    currentSessionEl.textContent = `No active session`;
    currentSessionEl.style.color = "#666";
    downloadBtn.disabled = true;
    processBtn.disabled = true;
    downloadNotesBtn.disabled = true;
    downloadNotesEnBtn.disabled = true;
  }
}

// ... (tutte le altre funzioni come updateStatus, addLogEntry, etc. rimangono invariate) ...
function updateStatus(connected) {
  statusEl.className = connected ? "status connected" : "status disconnected";
  statusEl.textContent = connected ? "Connected to server" : "Disconnected from server";
  playPauseBtn.disabled = !connected;
  skipBtn.disabled = !connected;
}

function updatePlaybackControls() {
  skipBtn.disabled = queue.length === 0;
  queueCount.textContent = queue.length;
  playPauseBtn.textContent = playbackPaused ? "Play Audio" : "Pause";
  playPauseBtn.className = playbackPaused ? "btn-primary" : "btn-secondary";
}

function addLogEntry(it, en) {
  const timestamp = new Date().toLocaleTimeString();
  const entry = document.createElement("div");
  entry.className = "entry";
  entry.innerHTML = `<div class="it">IT: ${escapeHtml(it)}</div><div class="en">EN: ${escapeHtml(en)}</div><div class="timestamp">${timestamp}</div>`;
  log.prepend(entry);
  if (log.children.length > 50) log.removeChild(log.lastChild);
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/[&<>"']/g, s => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[s]);
}

async function fetchAndQueueAudio(url) {
  try {
    const r = await fetch(url);
    if (!r.ok) { console.warn("Audio fetch failed", r.status); return; }
    const blob = await r.blob();
    const objUrl = URL.createObjectURL(blob);
    queue.push(objUrl);
    audioUrls.push(objUrl);
    if (audioUrls.length > 10) URL.revokeObjectURL(audioUrls.shift());
    updatePlaybackControls();
    if (!playbackPaused && !playing) playNext();
  } catch (e) { console.error("Error fetching audio:", e); }
}

function playNext() {
  if (queue.length === 0) {
    playing = false;
    player.src = "";
    updatePlaybackControls();
    return;
  }
  playing = true;
  const src = queue.shift();
  player.src = src;
  player.play().catch(e => console.warn("Autoplay blocked", e));
  player.onended = () => {
    URL.revokeObjectURL(src);
    updatePlaybackControls();
    if (!playbackPaused) playNext();
    else playing = false;
  };
  player.onpause = () => { if (player.currentTime > 0 && player.currentTime < player.duration) { playbackPaused = true; updatePlaybackControls(); } };
  player.onplay = () => { playbackPaused = false; updatePlaybackControls(); };
  updatePlaybackControls();
}


// --- GESTIONE DELLO STATO DELLA SESSIONE ---
socket.on("connect", () => { updateStatus(true); sessionInfo.textContent = "Connected. Waiting for translation..."; });
socket.on("disconnect", () => { updateStatus(false); sessionInfo.textContent = "Disconnected. Please check server connection."; });
socket.on("new_translation", (data) => {
  addLogEntry(data.italian || "", data.english || "");
  sessionInfo.textContent = "New translation received.";
  if (data.audio_url) fetchAndQueueAudio(window.location.origin + data.audio_url);
});

socket.on("session_status", (data) => {
  if (data.active) {
    // Sessione Live
    selectSession(null); // Disabilita i pulsanti di azione per le sessioni passate
    currentSessionEl.textContent = `Live: ${data.session_id.substring(0, 20)}...`;
    currentSessionEl.style.color = "green";
    sessionInfo.textContent = "Session active - Receiving translations...";
  } else {
    // Sessione Appena Terminata
    sessionInfo.textContent = "Session inactive - Waiting...";
    // Seleziona la sessione appena terminata per renderla subito gestibile
    selectSession({ id: data.session_id, processed: false });
    currentSessionEl.textContent = `Ended: ${data.session_id.substring(0, 20)}...`;
    currentSessionEl.style.color = "blue";
  }
});


// --- GESTIONE DEI PULSANTI ---
playPauseBtn.addEventListener("click", () => {
  playbackPaused = !playbackPaused;
  if (!playbackPaused) {
    if (player.src) player.play().catch(e => console.warn("Playback error:", e));
    else if (queue.length > 0) playNext();
  } else if (player && !player.paused) {
    player.pause();
  }
  updatePlaybackControls();
});

skipBtn.addEventListener("click", () => {
  if (player && !player.paused) player.pause();
  if (queue.length > 0) {
    if (player.src) URL.revokeObjectURL(player.src);
    playNext();
  }
});

processBtn.addEventListener("click", async () => {
  if (!selectedSessionId) return;
  processBtn.disabled = true;
  processBtn.textContent = "Generating...";
  try {
    const response = await fetch(`/process_session/${selectedSessionId}`);
    const result = await response.json();
    if (result.success) {
      alert("Notes generated successfully!");
      downloadNotesBtn.disabled = false;
      downloadNotesEnBtn.disabled = false;
    } else {
      alert("Error generating notes: " + result.error);
      processBtn.disabled = false;
    }
  } catch (error) {
    console.error("Error:", error);
    alert("Error during note generation.");
    processBtn.disabled = false;
  }
  processBtn.textContent = "Generate Notes";
});

// Le funzioni di download ora usano sempre e solo l'ID della sessione selezionata
downloadNotesBtn.addEventListener("click", () => { if (selectedSessionId) window.location.href = `/download_notes/${selectedSessionId}`; });
downloadNotesEnBtn.addEventListener("click", () => { if (selectedSessionId) window.location.href = `/download_notes_en/${selectedSessionId}`; });
downloadBtn.addEventListener("click", () => { if (selectedSessionId) window.location.href = `/download_transcript?session_id=${selectedSessionId}`; });

viewSessionsBtn.addEventListener("click", async () => {
  try {
    const response = await fetch("/session_list");
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    const data = await response.json();
    sessionsList.innerHTML = data.sessions.length === 0 ? "<div class='session-item'>No past sessions found.</div>" : "";
    data.sessions.forEach(session => {
      const sessionEl = document.createElement("div");
      sessionEl.className = "session-item";
      sessionEl.innerHTML = `<strong>${session.materia}</strong><div style="font-size: 0.9em; color: #333;">Docente: ${session.docente}</div><div style="font-size: 0.8em; color: #666;">${session.data} - ${session.ora}</div><div style="font-size: 0.8em; font-weight: bold; color: ${session.processed ? 'green' : 'orange'};">Status: ${session.processed ? 'Notes Processed' : 'Notes Not Processed'}</div>`;
      sessionEl.onclick = () => { selectSession(session); sessionsModal.style.display = "none"; };
      sessionsList.appendChild(sessionEl);
    });
    sessionsModal.style.display = "block";
  } catch (error) {
    console.error("Error loading sessions:", error);
    alert("Could not load session list. The server may have encountered an error.");
  }
});

closeModal.addEventListener("click", () => { sessionsModal.style.display = "none"; });
window.addEventListener("click", (event) => { if (event.target === sessionsModal) { sessionsModal.style.display = "none"; } });
window.addEventListener("beforeunload", () => { audioUrls.forEach(url => URL.revokeObjectURL(url)); });

// Stato iniziale
selectSession(null);
updatePlaybackControls();