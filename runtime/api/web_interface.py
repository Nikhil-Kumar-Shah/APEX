"""Self-contained, responsive AI Communication Interface for APEX."""

def get_web_interface_html() -> str:
    """Returns the complete, production-grade single-page AI Chat Application."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>APEX — AI Communication Interface</title>
    <style>
        :root {
            --bg-primary: #0d1117;
            --bg-secondary: #161b22;
            --bg-tertiary: #21262d;
            --border-color: #30363d;
            --text-primary: #f0f6fc;
            --text-secondary: #8b949e;
            --accent-blue: #58a6ff;
            --accent-green: #238636;
            --accent-green-hover: #2ea043;
            --accent-red: #f85149;
            --user-bubble: #1f2937;
            --code-bg: #090d13;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-primary);
            display: flex;
            height: 100vh;
            overflow: hidden;
        }

        /* ── Sidebar ── */
        .sidebar {
            width: 270px;
            background-color: var(--bg-secondary);
            border-right: 1px solid var(--border-color);
            display: flex;
            flex-direction: column;
            transition: transform 0.3s ease;
            z-index: 100;
        }
        .sidebar-header {
            padding: 16px;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .brand {
            font-size: 16px;
            font-weight: 700;
            color: var(--accent-blue);
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .new-chat-btn {
            background-color: var(--accent-green);
            color: #ffffff;
            border: none;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 6px;
            width: 100%;
            margin-top: 10px;
        }
        .new-chat-btn:hover { background-color: var(--accent-green-hover); }

        .convos-list {
            flex: 1;
            overflow-y: auto;
            padding: 12px 8px;
        }
        .convo-item {
            padding: 9px 12px;
            border-radius: 6px;
            font-size: 13px;
            color: var(--text-secondary);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 4px;
            text-overflow: ellipsis;
            white-space: nowrap;
            overflow: hidden;
        }
        .convo-item:hover { background-color: var(--bg-tertiary); color: var(--text-primary); }
        .convo-item.active { background-color: #1f6feb26; color: var(--accent-blue); border: 1px solid #388bfd4d; }
        .convo-delete-btn {
            opacity: 0;
            background: none;
            border: none;
            color: var(--accent-red);
            cursor: pointer;
            font-size: 12px;
            padding: 2px 4px;
        }
        .convo-item:hover .convo-delete-btn { opacity: 1; }

        .sidebar-footer {
            padding: 12px;
            border-top: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            font-size: 12px;
        }
        .footer-action-btn {
            background: none;
            border: none;
            color: var(--text-secondary);
            cursor: pointer;
            padding: 4px;
        }
        .footer-action-btn:hover { color: var(--text-primary); text-decoration: underline; }

        /* ── Main Viewport ── */
        .main-viewport {
            flex: 1;
            display: flex;
            flex-direction: column;
            position: relative;
            background-color: var(--bg-primary);
        }

        /* ── Top Navigation Bar ── */
        .top-navbar {
            height: 52px;
            border-bottom: 1px solid var(--border-color);
            background-color: var(--bg-secondary);
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 20px;
        }
        .nav-left { display: flex; align-items: center; gap: 12px; }
        .menu-toggle { display: none; background: none; border: none; color: var(--text-primary); font-size: 20px; cursor: pointer; }
        .model-badge {
            background-color: #21262d;
            border: 1px solid var(--border-color);
            padding: 4px 10px;
            border-radius: 14px;
            font-size: 12px;
            color: #c9d1d9;
            font-weight: 600;
        }
        .status-pill {
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 12px;
            font-weight: 600;
            color: #3fb950;
        }
        .status-dot { width: 8px; height: 8px; border-radius: 50%; background-color: #3fb950; }
        .api-drawer-btn {
            background: var(--bg-tertiary);
            color: var(--text-primary);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 6px 12px;
            font-size: 12px;
            cursor: pointer;
            font-weight: 600;
        }
        .api-drawer-btn:hover { background: #30363d; }

        /* ── Messages Container ── */
        .messages-container {
            flex: 1;
            overflow-y: auto;
            padding: 24px 20px;
            display: flex;
            flex-direction: column;
            gap: 18px;
            scroll-behavior: smooth;
        }
        .message-row {
            display: flex;
            width: 100%;
            max-width: 820px;
            margin: 0 auto;
        }
        .message-row.user { justify-content: flex-end; }
        .message-row.assistant { justify-content: flex-start; }

        .message-bubble {
            max-width: 85%;
            padding: 12px 16px;
            border-radius: 8px;
            line-height: 1.55;
            font-size: 14px;
            position: relative;
            word-break: break-word;
        }
        .message-row.user .message-bubble {
            background-color: var(--user-bubble);
            border: 1px solid #374151;
            color: #f3f4f6;
        }
        .message-row.assistant .message-bubble {
            background-color: var(--bg-secondary);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            width: 100%;
            max-width: 100%;
        }

        .avatar-label {
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 6px;
            color: var(--accent-blue);
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .attachment-tag {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: #21262d;
            border: 1px solid #30363d;
            border-radius: 4px;
            padding: 3px 8px;
            font-size: 11px;
            margin-top: 8px;
            color: #79c0ff;
        }

        /* ── Markdown & Code Styling ── */
        .message-bubble pre {
            background: var(--code-bg);
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 12px;
            overflow-x: auto;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 12px;
            margin: 8px 0;
            position: relative;
            color: #79c0ff;
        }
        .copy-code-btn {
            position: absolute;
            top: 6px;
            right: 6px;
            background: #21262d;
            border: 1px solid #30363d;
            color: #c9d1d9;
            border-radius: 4px;
            font-size: 11px;
            padding: 3px 8px;
            cursor: pointer;
        }
        .copy-code-btn:hover { background: #30363d; }
        .message-bubble code {
            background: #21262d;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: monospace;
            font-size: 0.9em;
            color: #ff7b72;
        }
        .message-bubble pre code { background: none; padding: 0; color: inherit; }
        .message-bubble p { margin-bottom: 8px; }
        .message-bubble p:last-child { margin-bottom: 0; }
        .message-bubble ul, .message-bubble ol { margin: 8px 0 8px 20px; }

        .streaming-cursor::after {
            content: "▍";
            color: var(--accent-blue);
            animation: blink 0.9s infinite;
        }
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }

        /* ── Empty Welcome State ── */
        .empty-state {
            margin: auto;
            text-align: center;
            max-width: 600px;
            padding: 20px;
        }
        .empty-state h2 { font-size: 24px; color: var(--accent-blue); margin-bottom: 8px; }
        .empty-state p { font-size: 14px; color: var(--text-secondary); margin-bottom: 24px; }
        .prompt-suggestions {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            text-align: left;
        }
        .prompt-card {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 12px 14px;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        .prompt-card:hover { border-color: var(--accent-blue); background: var(--bg-tertiary); }
        .prompt-card-title { font-size: 13px; font-weight: 600; color: #f0f6fc; margin-bottom: 4px; }
        .prompt-card-desc { font-size: 12px; color: var(--text-secondary); }

        /* ── Message Composer ── */
        .composer-container {
            padding: 12px 20px 20px 20px;
            max-width: 820px;
            width: 100%;
            margin: 0 auto;
        }
        .composer-box {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 10px 14px;
            display: flex;
            flex-direction: column;
            gap: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }
        .composer-box:focus-within { border-color: var(--accent-blue); }

        .attachment-preview-bar {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }
        .preview-chip {
            background: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 4px 10px;
            font-size: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
            color: #79c0ff;
        }
        .chip-remove-btn {
            background: none;
            border: none;
            color: var(--text-secondary);
            cursor: pointer;
            font-weight: bold;
        }
        .chip-remove-btn:hover { color: var(--accent-red); }

        .composer-input-row {
            display: flex;
            align-items: flex-end;
            gap: 10px;
        }
        textarea.message-input {
            flex: 1;
            background: none;
            border: none;
            color: var(--text-primary);
            font-size: 14px;
            resize: none;
            min-height: 40px;
            max-height: 180px;
            outline: none;
            font-family: inherit;
            line-height: 1.5;
        }
        .action-icon-btn {
            background: none;
            border: none;
            color: var(--text-secondary);
            cursor: pointer;
            font-size: 18px;
            padding: 6px;
            border-radius: 6px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .action-icon-btn:hover { color: var(--text-primary); background: var(--bg-tertiary); }

        .send-btn {
            background: var(--accent-green);
            color: #ffffff;
            border: none;
            border-radius: 6px;
            width: 34px;
            height: 34px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            font-size: 15px;
            transition: background-color 0.2s;
        }
        .send-btn:hover { background: var(--accent-green-hover); }
        .send-btn.stop-mode { background: var(--accent-red); }
        .send-btn.stop-mode:hover { background: #da3633; }
        .send-btn:disabled { background: #343942; color: #8b949e; cursor: not-allowed; }

        /* ── Developer Drawer ── */
        .drawer-overlay {
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.5);
            display: none;
            z-index: 200;
        }
        .drawer {
            position: fixed;
            top: 0; right: -420px; bottom: 0;
            width: 400px;
            background: var(--bg-secondary);
            border-left: 1px solid var(--border-color);
            transition: right 0.3s ease;
            z-index: 201;
            display: flex;
            flex-direction: column;
            padding: 20px;
            overflow-y: auto;
        }
        .drawer.open { right: 0; }
        .drawer-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 12px;
            margin-bottom: 16px;
        }
        .drawer-title { font-size: 16px; font-weight: 700; color: var(--accent-blue); }
        .drawer-close-btn { background: none; border: none; color: var(--text-secondary); font-size: 18px; cursor: pointer; }

        /* ── Mobile Responsive ── */
        @media (max-width: 768px) {
            .sidebar {
                position: fixed;
                top: 0; bottom: 0; left: -270px;
            }
            .sidebar.mobile-open { transform: translateX(270px); }
            .menu-toggle { display: block; }
            .prompt-suggestions { grid-template-columns: 1fr; }
            .drawer { width: 100%; right: -100%; }
        }
    </style>
</head>
<body>

    <!-- ── Sidebar ── -->
    <div class="sidebar" id="sidebar">
        <div class="sidebar-header">
            <div class="brand">🌌 APEX AI</div>
        </div>
        <div style="padding: 0 12px;">
            <button class="new-chat-btn" onclick="startNewConversation()">+ New Conversation</button>
        </div>
        <div class="convos-list" id="convosList"></div>
        <div class="sidebar-footer">
            <button class="footer-action-btn" onclick="exportActiveChat('md')">Export (.md)</button>
            <button class="footer-action-btn" onclick="exportActiveChat('json')">Export (.json)</button>
            <button class="footer-action-btn" onclick="clearAllConversations()">Clear All</button>
        </div>
    </div>

    <!-- ── Main Viewport ── -->
    <div class="main-viewport">
        <!-- Top Navigation -->
        <div class="top-navbar">
            <div class="nav-left">
                <button class="menu-toggle" onclick="toggleSidebar()">☰</button>
                <div class="model-badge" id="modelPill">Loading Model...</div>
                <div class="status-pill">
                    <div class="status-dot"></div>
                    <span id="connLabel">CONNECTED</span>
                </div>
            </div>
            <div>
                <button class="api-drawer-btn" onclick="toggleDrawer(true)">⚙ API Integration</button>
            </div>
        </div>

        <!-- Messages Container -->
        <div class="messages-container" id="messagesContainer">
            <div class="empty-state" id="emptyState">
                <h2>APEX Assistant</h2>
                <p>Adaptive Platform for Unified AI Configuration & Direct Model Inference</p>
                <div class="prompt-suggestions">
                    <div class="prompt-card" onclick="selectSuggestion('Explain quantum computing simply with an analogy.')">
                        <div class="prompt-card-title">💡 Clear Explanations</div>
                        <div class="prompt-card-desc">Explain quantum computing simply with an analogy.</div>
                    </div>
                    <div class="prompt-card" onclick="selectSuggestion('Write a clean Python script to parse and summarize CSV data.')">
                        <div class="prompt-card-title">🐍 Python Code</div>
                        <div class="prompt-card-desc">Write a clean Python script to parse and summarize CSV data.</div>
                    </div>
                    <div class="prompt-card" onclick="selectSuggestion('What is the difference between float16 and bfloat16 tensors?')">
                        <div class="prompt-card-title">🔬 Machine Learning</div>
                        <div class="prompt-card-desc">What is the difference between float16 and bfloat16 tensors?</div>
                    </div>
                    <div class="prompt-card" onclick="selectSuggestion('How can I call this APEX instance using the OpenAI Python SDK?')">
                        <div class="prompt-card-title">🌐 API Access</div>
                        <div class="prompt-card-desc">How can I call this APEX instance using the OpenAI Python SDK?</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Message Composer -->
        <div class="composer-container">
            <div class="composer-box" id="composerBox">
                <div class="attachment-preview-bar" id="previewBar" style="display:none;"></div>
                <div class="composer-input-row">
                    <input type="file" id="fileInput" multiple style="display: none;" onchange="handleFileSelect(event)">
                    <button class="action-icon-btn" title="Attach Document (TXT, PDF, DOCX, CSV, JSON)" onclick="document.getElementById('fileInput').click()">📎</button>
                    <textarea class="message-input" id="messageInput" placeholder="Ask anything or attach a document... (Enter to send, Shift+Enter for newline)" rows="1" oninput="autoResize(this)" onkeydown="handleKeyDown(event)"></textarea>
                    <button class="send-btn" id="sendBtn" onclick="handleSendAction()">➔</button>
                </div>
            </div>
        </div>
    </div>

    <!-- ── Developer Drawer ── -->
    <div class="drawer-overlay" id="drawerOverlay" onclick="toggleDrawer(false)"></div>
    <div class="drawer" id="drawer">
        <div class="drawer-header">
            <div class="drawer-title">API Integration & Access</div>
            <button class="drawer-close-btn" onclick="toggleDrawer(false)">✕</button>
        </div>
        <div style="font-size: 13px; color: var(--text-secondary); line-height: 1.6;">
            <div><b>Active Model:</b> <span id="drawerModel" style="color:var(--text-primary); font-family:monospace;">—</span></div>
            <div style="margin-top:6px;"><b>Public Endpoint:</b> <span id="drawerEndpoint" style="color:var(--accent-blue); font-family:monospace;">—</span></div>
            <div style="margin-top:6px;"><b>OpenAI Base URL:</b> <span id="drawerBaseUrl" style="color:var(--accent-blue); font-family:monospace;">—</span></div>
            <div style="margin-top:6px;"><b>API Key:</b> <span id="authStatusBadge" style="color:#3fb950;">Configured</span></div>
            <div style="margin-top:8px;">
                <input id="drawerApiKeyInput" type="password" placeholder="Enter API Key (if enabled)..." style="width:100%; background:#161b22; border:1px solid #30363d; color:#c9d1d9; border-radius:6px; padding:6px 10px; font-size:12px; box-sizing:border-box;" onchange="saveApiKey(this.value)">
            </div>

            <div style="margin-top: 16px; font-weight: 700; color: var(--text-primary);">Python OpenAI Client:</div>
            <pre style="margin-top: 8px;" id="pythonCodeSnippet"></pre>

            <div style="margin-top: 16px; font-weight: 700; color: var(--text-primary);">cURL Request:</div>
            <pre style="margin-top: 8px;" id="curlCodeSnippet"></pre>
        </div>
    </div>

    <!-- ── Application Logic ── -->
    <script>
        // State
        let activeConversationId = null;
        let isStreaming = false;
        let abortController = null;
        let activeAttachments = []; // { id, filename, bytes, text }
        let currentModelId = "Qwen/Qwen2.5-0.5B";

        // Initialization
        window.addEventListener("DOMContentLoaded", async () => {
            await fetchRuntimeInfo();
            await loadConversationsList();
            setupDragAndDrop();
        });

        async function fetchRuntimeInfo() {
            try {
                const res = await fetch("/health");
                if (res.ok) {
                    const data = await res.json();
                    currentModelId = data.model_loaded || "Qwen/Qwen2.5-0.5B";
                    document.getElementById("modelPill").textContent = "Model: " + currentModelId.split("/").pop();
                    updateDeveloperDrawer(currentModelId);
                }
            } catch (err) {
                console.warn("Health check error:", err);
            }
        }

        function getAuthHeaders(extra = {}) {
            const headers = { ...extra };
            const key = localStorage.getItem("apex_api_key");
            if (key) {
                headers["Authorization"] = "Bearer " + key.trim();
            }
            return headers;
        }

        function saveApiKey(key) {
            if (key && key.trim()) {
                localStorage.setItem("apex_api_key", key.trim());
            } else {
                localStorage.removeItem("apex_api_key");
            }
            updateDeveloperDrawer(currentModelId);
        }

        function updateDeveloperDrawer(modelId) {
            const host = window.location.origin;
            const currentKey = localStorage.getItem("apex_api_key") || "";
            const keyInput = document.getElementById("drawerApiKeyInput");
            if (keyInput && !keyInput.value) {
                keyInput.value = currentKey;
            }

            const authBadge = document.getElementById("authStatusBadge");
            if (authBadge) {
                authBadge.textContent = currentKey ? "Active (Bearer Token)" : "Direct / Header Optional";
                authBadge.style.color = currentKey ? "#58a6ff" : "#3fb950";
            }

            document.getElementById("drawerModel").textContent = modelId;
            document.getElementById("drawerEndpoint").textContent = host + "/v1/chat/completions";
            document.getElementById("drawerBaseUrl").textContent = host + "/v1";

            const pySnippet = `from openai import OpenAI

client = OpenAI(
    base_url="${host}/v1",
    api_key="${currentKey || 'YOUR_APEX_KEY'}"
)

response = client.chat.completions.create(
    model="${modelId}",
    messages=[{"role": "user", "content": "Hello APEX!"}],
    stream=True
)

for chunk in response:
    print(chunk.choices[0].delta.content or "", end="")`;

            const authHeaderLine = currentKey ? `  -H "Authorization: Bearer ${currentKey}" \\\n` : "";
            const curlSnippet = `curl -X POST ${host}/v1/chat/completions \\
${authHeaderLine}  -H "Content-Type: application/json" \\
  -d '{"model": "${modelId}", "messages": [{"role": "user", "content": "Hello!"}]}'`;

            document.getElementById("pythonCodeSnippet").textContent = pySnippet;
            document.getElementById("curlCodeSnippet").textContent = curlSnippet;
        }

        // Conversations Navigation
        async function loadConversationsList() {
            try {
                const res = await fetch("/v1/conversations", { headers: getAuthHeaders() });
                if (res.ok) {
                    const payload = await res.json();
                    renderSidebarConversations(payload.data || []);
                } else if (res.status === 401) {
                    promptForApiKey();
                }
            } catch (err) {
                console.warn("Failed to load conversations:", err);
            }
        }

        function promptForApiKey() {
            const entered = prompt("APEX Authentication Required. Please enter your API Key:");
            if (entered) {
                saveApiKey(entered);
                loadConversationsList();
            }
        }

        function renderSidebarConversations(convos) {
            const listEl = document.getElementById("convosList");
            listEl.innerHTML = "";
            convos.forEach(c => {
                const item = document.createElement("div");
                item.className = "convo-item" + (c.conversation_id === activeConversationId ? " active" : "");
                item.innerHTML = `
                    <span style="overflow:hidden; text-overflow:ellipsis;">💬 ${escapeHtml(c.title)}</span>
                    <button class="convo-delete-btn" onclick="deleteConversation(event, '${c.conversation_id}')">🗑</button>
                `;
                item.onclick = (e) => {
                    if (!e.target.classList.contains("convo-delete-btn")) {
                        selectConversation(c.conversation_id);
                    }
                };
                listEl.appendChild(item);
            });
        }

        async function startNewConversation() {
            activeConversationId = null;
            document.getElementById("messagesContainer").innerHTML = "";
            document.getElementById("messagesContainer").appendChild(document.getElementById("emptyState"));
            document.getElementById("emptyState").style.display = "block";
            activeAttachments = [];
            renderAttachmentChips();
            await loadConversationsList();
        }

        async function selectConversation(convoId) {
            try {
                const res = await fetch("/v1/conversations/" + convoId, { headers: getAuthHeaders() });
                if (!res.ok) return;
                const data = await res.json();
                activeConversationId = convoId;
                document.getElementById("emptyState").style.display = "none";
                const container = document.getElementById("messagesContainer");
                container.innerHTML = "";
                data.messages.forEach(m => {
                    appendMessageBubble(m.role, m.content);
                });
                await loadConversationsList();
            } catch (err) {
                console.error("Error loading conversation:", err);
            }
        }

        async function deleteConversation(e, convoId) {
            e.stopPropagation();
            if (!confirm("Delete this conversation?")) return;
            try {
                await fetch("/v1/conversations/" + convoId, { method: "DELETE", headers: getAuthHeaders() });
                if (activeConversationId === convoId) {
                    startNewConversation();
                } else {
                    loadConversationsList();
                }
            } catch (err) {
                console.error("Delete failed:", err);
            }
        }

        // File Ingestion
        async function handleFileSelect(e) {
            const files = e.target.files;
            if (!files || files.length === 0) return;
            for (let i = 0; i < files.length; i++) {
                await uploadSingleFile(files[i]);
            }
            e.target.value = "";
        }

        async function uploadSingleFile(file) {
            if (file.size > 10 * 1024 * 1024) {
                alert("File '" + file.name + "' exceeds 10MB limit.");
                return;
            }
            const formData = new FormData();
            formData.append("file", file);

            try {
                const res = await fetch("/v1/files", { method: "POST", headers: getAuthHeaders(), body: formData });
                if (!res.ok) {
                    const err = await res.json().catch(() => ({}));
                    alert("Upload error: " + (err.detail || "Server rejected file"));
                    return;
                }
                const data = await res.json();
                activeAttachments.push({
                    id: data.id,
                    filename: data.filename,
                    bytes: data.bytes,
                    extracted_text: data.extracted_text,
                    truncated: data.truncated
                });
                renderAttachmentChips();
            } catch (err) {
                alert("Upload failed: " + err.message);
            }
        }

        function renderAttachmentChips() {
            const bar = document.getElementById("previewBar");
            if (activeAttachments.length === 0) {
                bar.style.display = "none";
                bar.innerHTML = "";
                return;
            }
            bar.style.display = "flex";
            bar.innerHTML = "";
            activeAttachments.forEach((att, idx) => {
                const sizeKb = (att.bytes / 1024).toFixed(1);
                const chip = document.createElement("div");
                chip.className = "preview-chip";
                chip.innerHTML = `
                    <span>📄 ${escapeHtml(att.filename)} (${sizeKb} KB)</span>
                    <button class="chip-remove-btn" onclick="removeAttachment(${idx})">×</button>
                `;
                bar.appendChild(chip);
            });
        }

        function removeAttachment(idx) {
            activeAttachments.splice(idx, 1);
            renderAttachmentChips();
        }

        function setupDragAndDrop() {
            const dropZone = document.getElementById("composerBox");
            ["dragenter", "dragover"].forEach(evt => {
                dropZone.addEventListener(evt, (e) => { e.preventDefault(); dropZone.style.borderColor = "var(--accent-blue)"; });
            });
            ["dragleave", "drop"].forEach(evt => {
                dropZone.addEventListener(evt, (e) => { e.preventDefault(); dropZone.style.borderColor = "var(--border-color)"; });
            });
            dropZone.addEventListener("drop", async (e) => {
                if (e.dataTransfer && e.dataTransfer.files) {
                    for (let i = 0; i < e.dataTransfer.files.length; i++) {
                        await uploadSingleFile(e.dataTransfer.files[i]);
                    }
                }
            });
        }

        // Messaging & Streaming
        function selectSuggestion(text) {
            document.getElementById("messageInput").value = text;
            handleSendAction();
        }

        function handleKeyDown(e) {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSendAction();
            }
        }

        function autoResize(textarea) {
            textarea.style.height = "auto";
            textarea.style.height = Math.min(textarea.scrollHeight, 180) + "px";
        }

        async function handleSendAction() {
            if (isStreaming) {
                if (abortController) abortController.abort();
                return;
            }

            const inputEl = document.getElementById("messageInput");
            const rawText = inputEl.value.trim();
            if (!rawText && activeAttachments.length === 0) return;

            // Hide empty state
            document.getElementById("emptyState").style.display = "none";

            // Compose user message
            let promptContent = rawText;
            let attachmentBadges = "";
            if (activeAttachments.length > 0) {
                let docContext = "";
                activeAttachments.forEach(att => {
                    docContext += `\\n[Document Content: ${att.filename}]\\n${att.extracted_text}\\n`;
                    attachmentBadges += `<div class="attachment-tag">📄 ${escapeHtml(att.filename)}</div>`;
                });
                promptContent = docContext + "\\nUser Inquiry:\\n" + (rawText || "Please review and summarize the attached document(s).");
            }

            // Append User Bubble
            appendMessageBubble("user", rawText || "Attached document(s)", attachmentBadges);
            inputEl.value = "";
            inputEl.style.height = "40px";
            const currentAttachments = [...activeAttachments];
            activeAttachments = [];
            renderAttachmentChips();

            // Create Conversation if None Exists
            if (!activeConversationId) {
                try {
                    const titleText = rawText ? rawText.slice(0, 30) : (currentAttachments[0]?.filename || "Chat");
                    const convoRes = await fetch("/v1/conversations", {
                        method: "POST",
                        headers: getAuthHeaders({ "Content-Type": "application/json" }),
                        body: JSON.stringify({ title: titleText })
                    });
                    if (convoRes.ok) {
                        const newConvo = await convoRes.json();
                        activeConversationId = newConvo.conversation_id;
                        loadConversationsList();
                    }
                } catch(e) {}
            }

            // Create Assistant Bubble (Streaming container)
            const assistantBubble = appendMessageBubble("assistant", "");
            assistantBubble.classList.add("streaming-cursor");

            setStreamingState(true);
            abortController = new AbortController();

            try {
                const res = await fetch("/v1/chat/completions", {
                    method: "POST",
                    headers: getAuthHeaders({ "Content-Type": "application/json" }),
                    body: JSON.stringify({
                        model: currentModelId,
                        messages: [{ role: "user", content: promptContent }],
                        stream: true,
                        conversation_id: activeConversationId
                    }),
                    signal: abortController.signal
                });

                if (!res.ok) {
                    if (res.status === 401) {
                        assistantBubble.innerHTML = `<span style="color:var(--accent-red)">Authentication required: Please configure your APEX API Key in the Developer Drawer or click Settings.</span>`;
                        promptForApiKey();
                        return;
                    }
                    const err = await res.json().catch(() => ({}));
                    assistantBubble.innerHTML = `<span style="color:var(--accent-red)">Error: ${err.detail || "Model inference failed"}</span>`;
                    return;
                }

                const reader = res.body.getReader();
                const decoder = new TextDecoder("utf-8");
                let buffer = "";
                let accumulatedTokens = "";

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split("\\n");
                    buffer = lines.pop();

                    for (const line of lines) {
                        if (line.startsWith("data: ")) {
                            const chunk = line.slice(6).trim();
                            if (chunk === "[DONE]") break;
                            try {
                                const parsed = JSON.parse(chunk);
                                const token = parsed.choices?.[0]?.delta?.content || "";
                                accumulatedTokens += token;
                                assistantBubble.innerHTML = renderMarkdown(accumulatedTokens);
                                scrollToBottom();
                            } catch(e) {}
                        }
                    }
                }
            } catch (err) {
                if (err.name === "AbortError") {
                    assistantBubble.innerHTML += `<div style="font-size:11px; color:var(--text-secondary); margin-top:6px;">[Generation stopped by user]</div>`;
                } else {
                    assistantBubble.innerHTML = `<span style="color:var(--accent-red)">Connection error: ${err.message}</span>`;
                }
            } finally {
                assistantBubble.classList.remove("streaming-cursor");
                setStreamingState(false);
                addMessageActions(assistantBubble);
                scrollToBottom();
            }
        }

        function setStreamingState(streaming) {
            isStreaming = streaming;
            const btn = document.getElementById("sendBtn");
            const input = document.getElementById("messageInput");
            if (streaming) {
                btn.textContent = "■";
                btn.className = "send-btn stop-mode";
                btn.title = "Stop Generation";
            } else {
                btn.textContent = "➔";
                btn.className = "send-btn";
                btn.title = "Send Message";
            }
        }

        function appendMessageBubble(role, content, badgeHtml = "") {
            const container = document.getElementById("messagesContainer");
            const row = document.createElement("div");
            row.className = "message-row " + role;

            const bubble = document.createElement("div");
            bubble.className = "message-bubble";

            const label = document.createElement("div");
            label.className = "avatar-label";
            label.textContent = role === "user" ? "You" : "APEX Assistant";

            bubble.appendChild(label);

            const contentDiv = document.createElement("div");
            contentDiv.innerHTML = renderMarkdown(content) + (badgeHtml || "");
            bubble.appendChild(contentDiv);

            row.appendChild(bubble);
            container.appendChild(row);
            scrollToBottom();
            return contentDiv;
        }

        function addMessageActions(contentDiv) {
            const actions = document.createElement("div");
            actions.style.marginTop = "10px";
            actions.style.display = "flex";
            actions.style.gap = "8px";

            const copyBtn = document.createElement("button");
            copyBtn.className = "copy-code-btn";
            copyBtn.style.position = "static";
            copyBtn.textContent = "📋 Copy Response";
            copyBtn.onclick = () => {
                navigator.clipboard.writeText(contentDiv.innerText);
                copyBtn.textContent = "✓ Copied!";
                setTimeout(() => copyBtn.textContent = "📋 Copy Response", 2000);
            };
            actions.appendChild(copyBtn);
            contentDiv.appendChild(actions);
        }

        // Markdown & Sanitization
        function escapeHtml(str) {
            return (str || "")
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#39;");
        }

        function renderMarkdown(text) {
            if (!text) return "";
            let html = escapeHtml(text);

            // Fenced code blocks ```lang ... ```
            html = html.replace(/```(\\w*)\\n([\\s\\S]*?)```/g, (match, lang, code) => {
                return `<pre><button class="copy-code-btn" onclick="copyCode(this)">Copy</button><code>${code}</code></pre>`;
            });

            // Inline code `...`
            html = html.replace(/`([^`]+)`/g, "<code>$1</code>");

            // Bold and italics
            html = html.replace(/\\*\\*([^\\*]+)\\*\\*/g, "<b>$1</b>");
            html = html.replace(/\\*([^\\*]+)\\*/g, "<i>$1</i>");

            // Paragraphs / line breaks
            html = html.replace(/\\n\\n/g, "</p><p>");
            html = html.replace(/\\n/g, "<br>");
            return "<p>" + html + "</p>";
        }

        function copyCode(btn) {
            const code = btn.nextElementSibling.innerText;
            navigator.clipboard.writeText(code);
            btn.textContent = "Copied!";
            setTimeout(() => btn.textContent = "Copy", 2000);
        }

        function scrollToBottom() {
            const c = document.getElementById("messagesContainer");
            c.scrollTop = c.scrollHeight;
        }

        // Drawer & Sidebar Toggles
        function toggleDrawer(open) {
            document.getElementById("drawer").classList.toggle("open", open);
            document.getElementById("drawerOverlay").style.display = open ? "block" : "none";
        }
        function toggleSidebar() {
            document.getElementById("sidebar").classList.toggle("mobile-open");
        }

        async function exportActiveChat(format) {
            if (!activeConversationId) {
                alert("Select or start a conversation first.");
                return;
            }
            try {
                const res = await fetch("/v1/conversations/" + activeConversationId, { headers: getAuthHeaders() });
                if (!res.ok) return;
                const convo = await res.json();
                let output = "";
                let filename = (convo.title || "conversation").replace(/[^a-zA-Z0-9_-]/g, "_");
                if (format === "json") {
                    output = JSON.stringify(convo, null, 2);
                    filename += ".json";
                } else {
                    output = "# " + convo.title + "\\n\\n";
                    convo.messages.forEach(m => {
                        output += "### " + m.role.toUpperCase() + "\\n" + m.content + "\\n\\n";
                    });
                    filename += ".md";
                }
                const blob = new Blob([output], { type: "text/plain;charset=utf-8" });
                const a = document.createElement("a");
                a.href = URL.createObjectURL(blob);
                a.download = filename;
                a.click();
            } catch(e) {
                alert("Export error: " + e.message);
            }
        }

        async function clearAllConversations() {
            if (!confirm("Clear all conversation history?")) return;
            try {
                const res = await fetch("/v1/conversations", { headers: getAuthHeaders() });
                if (res.ok) {
                    const data = await res.json();
                    for (const c of data.data) {
                        await fetch("/v1/conversations/" + c.conversation_id, { method: "DELETE", headers: getAuthHeaders() });
                    }
                }
                startNewConversation();
            } catch(e) {
                console.error("Clear error:", e);
            }
        }
    </script>
</body>
</html>
"""

