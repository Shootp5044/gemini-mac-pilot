// Mac Pilot — Google-style bar UI

const WS_URL = "ws://127.0.0.1:8765";
let ws = null;
let reconnectTimer = null;

// DOM
const bar = document.getElementById("bar");
const geminiIcon = document.getElementById("gemini-icon");
const input = document.getElementById("input");
const statusPill = document.getElementById("status-pill");
const statusDot = document.getElementById("status-dot");
const statusText = document.getElementById("status-text");
const waveformCanvas = document.getElementById("waveform");
const micBtn = document.getElementById("mic-btn");
const stopBtn = document.getElementById("stop-btn");
const sendBtn = document.getElementById("send-btn");
const detailPanel = document.getElementById("detail-panel");
const taskRow = document.getElementById("task-row");
const taskLabel = document.getElementById("task-label");
const stepsList = document.getElementById("steps-list");
const resultRow = document.getElementById("result-row");
const setupBanner = document.getElementById("setup-banner");
const connectGoogleBtn = document.getElementById("connect-google-btn");
const resultText = document.getElementById("result-text");

// ── Waveform ──
const ctx = waveformCanvas.getContext("2d");
let animating = false;
let wBars = new Array(16).fill(0);

function drawWaveform() {
    if (!animating) return;
    ctx.clearRect(0, 0, waveformCanvas.width, waveformCanvas.height);
    const bw = waveformCanvas.width / wBars.length;
    const cy = waveformCanvas.height / 2;
    for (let i = 0; i < wBars.length; i++) {
        wBars[i] += (Math.random() - 0.5) * 0.35;
        wBars[i] = Math.max(0.08, Math.min(1, wBars[i]));
        const h = wBars[i] * cy * 0.9;
        // Google gradient colors
        const colors = ["#4285f4", "#ea4335", "#fbbc05", "#34a853"];
        ctx.fillStyle = colors[i % 4];
        ctx.globalAlpha = 0.4 + wBars[i] * 0.6;
        ctx.beginPath();
        ctx.roundRect(i * bw + 1, cy - h, bw - 2, h * 2, 2);
        ctx.fill();
    }
    ctx.globalAlpha = 1;
    requestAnimationFrame(drawWaveform);
}

function startWaveform() {
    if (animating) return;
    animating = true;
    waveformCanvas.classList.add("active");
    wBars = wBars.map(() => Math.random() * 0.3 + 0.1);
    drawWaveform();
}

function stopWaveform() {
    animating = false;
    waveformCanvas.classList.remove("active");
}

// ── Status ──
function setStatus(status) {
    geminiIcon.className = "gemini-icon " + status;
    statusPill.className = "status-pill " + status;

    const labels = {
        idle: "Ready",
        listening: "Listening",
        processing: "Working",
        speaking: "Speaking"
    };
    statusText.textContent = labels[status] || status;

    if (status === "listening") {
        startWaveform();
        micBtn.classList.add("active");
        input.placeholder = "Listening...";
        input.disabled = false;
        stopBtn.style.display = "none";
        sendBtn.style.display = "flex";
    } else if (status === "processing" || status === "speaking") {
        stopWaveform();
        input.placeholder = status === "speaking" ? "Speaking..." : "Working on it...";
        input.disabled = true;
        stopBtn.style.display = "flex";
        sendBtn.style.display = "none";
        // Show skeleton placeholder while waiting for first step
        if (status === "processing" && stepsList.querySelectorAll(".step").length === 0) {
            if (!stepsList.querySelector(".step-skeleton")) {
                const skel = document.createElement("div");
                skel.className = "step-skeleton";
                stepsList.appendChild(skel);
                expand();
            }
        }
    } else if (status === "idle") {
        stopWaveform();
        micBtn.classList.remove("active");
        input.placeholder = "Type a command...";
        input.disabled = false;
        input.focus();
        stopBtn.style.display = "none";
        sendBtn.style.display = "flex";
        bar.classList.remove("active");
    }
}

// ── Send command ──
function sendCommand() {
    const text = input.value.trim();
    if (!text || !ws || ws.readyState !== 1) return;
    ws.send(JSON.stringify({ type: "command", text }));
    input.value = "";
    input.style.color = "";
    input.disabled = true;
    bar.classList.add("active");
}

input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); sendCommand(); }
});

// Reset provisional transcript styling when user types
input.addEventListener("input", () => {
    input.style.color = "";
});

sendBtn.addEventListener("click", sendCommand);

stopBtn.addEventListener("click", () => {
    if (!ws || ws.readyState !== 1) return;
    ws.send(JSON.stringify({ type: "cancel" }));
});

micBtn.addEventListener("click", () => {
    if (!ws || ws.readyState !== 1) return;
    ws.send(JSON.stringify({ type: "toggle_voice" }));
});

connectGoogleBtn.addEventListener("click", () => {
    if (!ws || ws.readyState !== 1) return;
    connectGoogleBtn.textContent = "Connecting...";
    connectGoogleBtn.classList.add("connecting");
    ws.send(JSON.stringify({ type: "connect_google" }));
});

// ── Panel ──
const MAX_VISIBLE_STEPS = 3;

function addStep(data) {
    // Remove loading skeleton when first real step arrives
    const skel = stepsList.querySelector(".step-skeleton");
    if (skel) skel.remove();

    expand();
    const el = document.createElement("div");
    el.className = "step running";
    el.id = `step-${data.step}`;
    el.innerHTML = `
        <div class="step-dot"></div>
        <span class="step-name">${esc(data.tool_name)}(${esc(data.tool_args)})</span>
        <span class="step-time">...</span>
    `;
    stepsList.appendChild(el);

    // Keep only last N steps visible with slide animation
    const steps = stepsList.querySelectorAll(".step");
    if (steps.length > MAX_VISIBLE_STEPS) {
        const old = steps[0];
        old.classList.add("step-exit");
        old.addEventListener("animationend", () => old.remove(), { once: true });
    }
}

function updateStep(data) {
    const el = document.getElementById(`step-${data.step}`);
    if (!el) return;
    el.className = `step ${data.status}`;
    if (data.elapsed > 0) el.querySelector(".step-time").textContent = `${data.elapsed.toFixed(1)}s`;
}

function fadeOutSteps(callback) {
    const steps = stepsList.querySelectorAll(".step");
    if (steps.length === 0) { callback(); return; }
    steps.forEach((s, i) => {
        s.style.transition = `opacity 0.2s ${i * 0.05}s, transform 0.2s ${i * 0.05}s`;
        s.style.opacity = "0";
        s.style.transform = "translateY(-4px)";
    });
    setTimeout(() => {
        stepsList.innerHTML = "";
        callback();
    }, 200 + steps.length * 50);
}

function renderMarkdown(text) {
    return esc(text)
        .replace(/^### (.+)$/gm, '<div class="md-h3">$1</div>')
        .replace(/^## (.+)$/gm, '<div class="md-h2">$1</div>')
        .replace(/^\* \*\*(.+?)\*\*(.*)$/gm, '<div class="md-li"><strong>$1</strong>$2</div>')
        .replace(/^\*   (.+)$/gm, '<div class="md-li">$1</div>')
        .replace(/^- (.+)$/gm, '<div class="md-li">$1</div>')
        .replace(/^\d+\.\s+(.+)$/gm, '<div class="md-li">$1</div>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" class="md-link">$1</a>')
        .replace(/\n\n/g, '<br><br>')
        .replace(/\n/g, '<br>');
}

function expand() {
    detailPanel.classList.add("open");
    bar.classList.add("active");
}

function collapse() {
    detailPanel.classList.remove("open");
    taskRow.classList.remove("active");
    resultRow.classList.remove("active");
    bar.classList.remove("active");
}

function esc(t) {
    const d = document.createElement("div");
    d.textContent = t;
    return d.innerHTML;
}

// ── WebSocket ──
function connect() {
    ws = new WebSocket(WS_URL);
    ws.onopen = () => {
        if (reconnectTimer) { clearInterval(reconnectTimer); reconnectTimer = null; }
    };
    ws.onmessage = (e) => handleMessage(JSON.parse(e.data));
    ws.onclose = () => {
        if (!reconnectTimer) reconnectTimer = setInterval(connect, 2000);
    };
    ws.onerror = () => ws.close();
}

function handleMessage(msg) {
    switch (msg.type) {
        case "init":
            setStatus(msg.status);
            // Show setup banner if Google Workspace not connected
            if (msg.setup && !msg.setup.gws_authenticated) {
                setupBanner.style.display = "block";
            } else {
                setupBanner.style.display = "none";
            }
            if (msg.steps && msg.steps.length > 0) {
                stepsList.innerHTML = "";
                msg.steps.forEach(s => { addStep(s); if (s.status !== "running") updateStep(s); });
            }
            if (msg.result) {
                resultText.textContent = msg.result;
                resultRow.classList.add("active");
                expand();
            }
            break;

        case "status":
            setStatus(msg.status);
            break;

        case "transcript":
            input.value = msg.text;
            input.style.color = "rgba(255,255,255,0.4)";
            resultRow.classList.remove("active");
            break;

        case "task":
            taskLabel.textContent = msg.task;
            taskRow.classList.add("active");
            stepsList.innerHTML = "";
            resultRow.classList.remove("active");
            expand();
            break;

        case "step":
            addStep(msg);
            break;

        case "step_update":
            updateStep(msg);
            break;

        case "result":
            // Clear steps and show result as the main content
            fadeOutSteps(() => {
                resultText.innerHTML = renderMarkdown(msg.result || "");
                const statsEl = document.getElementById("result-stats");
                if (msg.stats) {
                    const tools = msg.stats.tools.join(", ") || "none";
                    statsEl.innerHTML = `
                        <span class="stat"><span class="stat-icon">⏱</span>${msg.stats.time}s</span>
                        <span class="stat"><span class="stat-icon">◆</span>${msg.stats.steps} steps</span>
                        <span class="stat"><span class="stat-icon">⚡</span>${tools}</span>
                    `;
                } else {
                    statsEl.innerHTML = "";
                }
                resultRow.classList.add("active");
            });
            if (micBtn.classList.contains("active")) {
                setStatus("listening");
            } else {
                setStatus("idle");
            }
            setTimeout(() => {
                if (statusText.textContent === "Ready" || statusText.textContent === "Listening") {
                    collapse();
                }
            }, 8000);
            break;

        case "setup_update":
            if (msg.gws_authenticated) {
                connectGoogleBtn.textContent = "Connected";
                connectGoogleBtn.classList.remove("connecting");
                connectGoogleBtn.classList.add("connected");
                setTimeout(() => { setupBanner.style.display = "none"; }, 2000);
            }
            break;

        case "mic_toggle":
            if (msg.active) {
                micBtn.classList.add("active");
                setStatus("listening");
            } else {
                micBtn.classList.remove("active");
                setStatus("idle");
            }
            break;
    }
}

// ── Keyboard shortcuts ──
document.addEventListener("keydown", (e) => {
    // Cmd+K — focus input
    if (e.key === "k" && e.metaKey) {
        e.preventDefault();
        input.focus();
        return;
    }
    // "/" — focus input (only when not already typing in input)
    if (e.key === "/" && document.activeElement !== input) {
        e.preventDefault();
        input.focus();
        return;
    }
    // Escape — cancel current task
    if (e.key === "Escape") {
        if (ws && ws.readyState === 1) {
            ws.send(JSON.stringify({ type: "cancel" }));
        }
        return;
    }
});

connect();
input.focus();
