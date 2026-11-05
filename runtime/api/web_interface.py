"""Self-contained, responsive, professional AI Communication Interface for APEX."""

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
            --bg-primary: #0b0f19;
            --bg-secondary: #111827;
            --bg-tertiary: #1f2937;
            --bg-card: #162032;
            --border-color: #374151;
            --border-subtle: #1f2937;
            --text-primary: #f9fafb;
            --text-secondary: #9ca3af;
            --text-muted: #6b7280;
            --accent-red: #ef4444;
            --accent-red-hover: #dc2626;
            --accent-red-subtle: rgba(239, 68, 68, 0.12);
            --accent-blue: #38bdf8;
            --accent-green: #10b981;
            --accent-amber: #f59e0b;
            --user-bubble: #1e293b;
            --assistant-bubble: #131c2e;
            --code-bg: #070b12;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Inter, Helvetica, Arial, sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-primary);
            display: flex;
            height: 100vh;
            overflow: hidden;
        }

        /* ── Sidebar ── */
        .sidebar {
            width: 280px;
            background-color: var(--bg-secondary);
            border-right: 1px solid var(--border-color);
            display: flex;
            flex-direction: column;
            transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
            z-index: 100;
        }
        .sidebar-header {
            padding: 16px;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        .brand {
            font-size: 15px;
            font-weight: 800;
            letter-spacing: 0.5px;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .brand-badge {
            background: var(--accent-red);
            color: #ffffff;
            font-size: 10px;
            font-weight: 700;
            padding: 2px 6px;
            border-radius: 4px;
            text-transform: uppercase;
        }
        .new-chat-btn {
            background-color: var(--bg-tertiary);
            color: var(--text-primary);
            border: 1px solid var(--border-color);
            padding: 9px 14px;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            width: 100%;
            transition: all 0.15s ease;
        }
        .new-chat-btn:hover {
            background-color: var(--accent-red);
            border-color: var(--accent-red);
            color: #ffffff;
        }

        .convos-list {
            flex: 1;
            overflow-y: auto;
            padding: 10px 8px;
            display: flex;
            flex-direction: column;
            gap: 2px;
        }
        .convo-item {
            padding: 8px 10px;
            border-radius: 6px;
            font-size: 13px;
            color: var(--text-secondary);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 6px;
            transition: all 0.12s ease;
        }
        .convo-item:hover {
            background-color: var(--bg-tertiary);
            color: var(--text-primary);
        }
        .convo-item.active {
            background-color: var(--accent-red-subtle);
            color: var(--text-primary);
            border: 1px solid rgba(239, 68, 68, 0.35);
            font-weight: 600;
        }
        .convo-title {
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            flex: 1;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .convo-delete-btn {
            opacity: 0;
            background: none;
            border: none;
            color: var(--text-muted);
            cursor: pointer;
            font-size: 13px;
            padding: 3px 5px;
            border-radius: 4px;
            transition: all 0.15s;
        }
        .convo-item:hover .convo-delete-btn { opacity: 0.8; }
        .convo-delete-btn:hover { color: var(--accent-red); opacity: 1; background: rgba(239, 68, 68, 0.15); }

        .sidebar-footer {
            padding: 12px 14px;
            border-top: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            font-size: 11px;
            background: rgba(0,0,0,0.15);
        }
        .footer-action-btn {
            background: none;
            border: none;
            color: var(--text-muted);
            cursor: pointer;
            padding: 3px 6px;
            border-radius: 4px;
            transition: color 0.15s;
        }
        .footer-action-btn:hover { color: var(--text-primary); }
        .footer-action-btn.danger:hover { color: var(--accent-red); }

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
            padding: 0 16px;
        }
        .nav-left { display: flex; align-items: center; gap: 10px; }
        .menu-toggle { display: none; background: none; border: none; color: var(--text-primary); font-size: 18px; cursor: pointer; }

        .model-badge {
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 12px;
            color: var(--text-primary);
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .status-pill {
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 11px;
            font-weight: 600;
            padding: 4px 9px;
            border-radius: 6px;
            border: 1px solid transparent;
        }
        .status-pill.online {
            background: rgba(16, 185, 129, 0.1);
            color: var(--accent-green);
            border-color: rgba(16, 185, 129, 0.25);
        }
        .status-pill.loading {
            background: rgba(245, 158, 11, 0.1);
            color: var(--accent-amber);
            border-color: rgba(245, 158, 11, 0.25);
        }
        .status-pill.error {
            background: var(--accent-red-subtle);
            color: var(--accent-red);
            border-color: rgba(239, 68, 68, 0.25);
        }
        .status-dot { width: 6px; height: 6px; border-radius: 50%; }
        .status-pill.online .status-dot { background-color: var(--accent-green); }
        .status-pill.loading .status-dot { background-color: var(--accent-amber); animation: pulse 1.2s infinite; }
        .status-pill.error .status-dot { background-color: var(--accent-red); }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }

        .api-drawer-btn {
            background: var(--bg-tertiary);
            color: var(--text-primary);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 5px 11px;
            font-size: 12px;
            cursor: pointer;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 6px;
            transition: all 0.15s;
        }
        .api-drawer-btn:hover {
            border-color: var(--accent-red);
            color: #ffffff;
        }

        /* ── Messages Container ── */
        .messages-container {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 16px;
            scroll-behavior: smooth;
        }
        .message-row {
            display: flex;
            width: 100%;
            max-width: 840px;
            margin: 0 auto;
        }
        .message-row.user { justify-content: flex-end; }
        .message-row.assistant { justify-content: flex-start; }

        .message-bubble {
            max-width: 85%;
            padding: 12px 16px;
            border-radius: 8px;
            line-height: 1.6;
            font-size: 14px;
            position: relative;
            word-break: break-word;
        }
        .message-row.user .message-bubble {
            background-color: var(--user-bubble);
            border: 1px solid #334155;
            color: #f8fafc;
            border-bottom-right-radius: 2px;
        }
        .message-row.assistant .message-bubble {
            background-color: var(--assistant-bubble);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            border-bottom-left-radius: 2px;
            width: 100%;
            max-width: 100%;
        }

        .avatar-label {
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.5px;
            margin-bottom: 6px;
            color: var(--text-secondary);
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .message-row.assistant .avatar-label {
            color: var(--accent-red);
        }
        .attachment-tag {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            padding: 3px 8px;
            font-size: 11px;
            margin-top: 8px;
            color: var(--accent-blue);
        }

        /* ── Markdown & Code Styling ── */
        .message-bubble p { margin-bottom: 8px; }
        .message-bubble p:last-child { margin-bottom: 0; }
        .message-bubble ul, .message-bubble ol { margin: 6px 0 6px 22px; }
        .message-bubble li { margin-bottom: 3px; }
        .message-bubble blockquote {
            border-left: 3px solid var(--accent-red);
            padding-left: 10px;
            color: var(--text-secondary);
            margin: 6px 0;
        }
        .message-bubble table {
            border-collapse: collapse;
            width: 100%;
            margin: 8px 0;
            font-size: 13px;
        }
        .message-bubble th, .message-bubble td {
            border: 1px solid var(--border-color);
            padding: 6px 10px;
            text-align: left;
        }
        .message-bubble th {
            background: var(--bg-tertiary);
            font-weight: 600;
        }

        .code-block-wrapper {
            background: var(--code-bg);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            margin: 10px 0;
            overflow: hidden;
        }
        .code-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 5px 10px;
            background: #111827;
            border-bottom: 1px solid var(--border-color);
            font-size: 11px;
            font-family: monospace;
            color: var(--text-secondary);
        }
        .copy-code-btn {
            background: none;
            border: 1px solid var(--border-color);
            color: var(--text-secondary);
            border-radius: 4px;
            font-size: 11px;
            padding: 2px 7px;
            cursor: pointer;
            transition: all 0.15s;
        }
        .copy-code-btn:hover {
            color: var(--text-primary);
            border-color: var(--text-secondary);
        }
        .message-bubble pre {
            padding: 10px 12px;
            overflow-x: auto;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 12.5px;
            line-height: 1.5;
            color: #e2e8f0;
            margin: 0;
        }
        .message-bubble code {
            background: rgba(255,255,255,0.08);
            padding: 2px 5px;
            border-radius: 4px;
            font-family: monospace;
            font-size: 0.9em;
            color: #fca5a5;
        }
        .message-bubble pre code { background: none; padding: 0; color: inherit; }

        .streaming-cursor::after {
            content: "▍";
            color: var(--accent-red);
            animation: blink 0.8s infinite;
        }
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }

        /* ── Assistant Actions Toolbar ── */
        .assistant-actions {
            display: flex;
            gap: 6px;
            margin-top: 10px;
            padding-top: 6px;
            border-top: 1px solid rgba(255,255,255,0.06);
        }
        .msg-action-btn {
            background: none;
            border: none;
            color: var(--text-muted);
            font-size: 12px;
            cursor: pointer;
            padding: 3px 6px;
            border-radius: 4px;
            display: flex;
            align-items: center;
            gap: 4px;
            transition: color 0.15s;
        }
        .msg-action-btn:hover { color: var(--text-primary); }

        /* ── Empty Welcome State ── */
        .empty-state {
            margin: auto;
            text-align: center;
            max-width: 620px;
            padding: 20px;
        }
        .empty-state h2 { font-size: 22px; color: var(--text-primary); margin-bottom: 6px; }
        .empty-state p { font-size: 13.5px; color: var(--text-secondary); margin-bottom: 24px; line-height: 1.5; }
        .prompt-suggestions {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            text-align: left;
        }
        .prompt-card {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 12px;
            cursor: pointer;
            transition: all 0.15s ease;
        }
        .prompt-card:hover {
            border-color: var(--accent-red);
            background: var(--bg-tertiary);
            transform: translateY(-1px);
        }
        .prompt-card-title { font-size: 13px; font-weight: 600; color: #f9fafb; margin-bottom: 3px; }
        .prompt-card-desc { font-size: 12px; color: var(--text-muted); line-height: 1.4; }

        /* ── Message Composer ── */
        .composer-container {
            padding: 12px 20px 20px 20px;
            max-width: 840px;
            width: 100%;
            margin: 0 auto;
        }
        .composer-box {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 8px 12px;
            display: flex;
            flex-direction: column;
            gap: 6px;
            box-shadow: 0 4px 14px rgba(0,0,0,0.3);
            transition: border-color 0.15s;
        }
        .composer-box:focus-within { border-color: var(--accent-red); }

        .attachment-preview-bar {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
        }
        .preview-chip {
            background: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            border-radius: 5px;
            padding: 3px 8px;
            font-size: 11.5px;
            display: flex;
            align-items: center;
            gap: 6px;
            color: var(--accent-blue);
        }
        .chip-remove-btn {
            background: none;
            border: none;
            color: var(--text-muted);
            cursor: pointer;
            font-weight: bold;
        }
        .chip-remove-btn:hover { color: var(--accent-red); }

        .composer-input-row {
            display: flex;
            align-items: flex-end;
            gap: 8px;
        }
        textarea.message-input {
            flex: 1;
            background: none;
            border: none;
            color: var(--text-primary);
            font-size: 14px;
            resize: none;
            min-height: 38px;
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
            font-size: 16px;
            padding: 6px;
            border-radius: 5px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.15s;
        }
        .action-icon-btn:hover { color: var(--text-primary); background: var(--bg-tertiary); }

        .send-btn {
            background: var(--accent-red);
            color: #ffffff;
            border: none;
            border-radius: 6px;
            width: 32px;
            height: 32px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            font-size: 14px;
            transition: background-color 0.15s;
        }
        .send-btn:hover { background: var(--accent-red-hover); }
        .send-btn.stop-mode { background: #475569; }
        .send-btn.stop-mode:hover { background: #334155; }
        .send-btn:disabled { background: #334155; color: #64748b; cursor: not-allowed; }

        /* ── Developer Drawer ── */
        .drawer-overlay {
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.55);
            display: none;
            z-index: 200;
        }
        .drawer {
            position: fixed;
            top: 0; right: -440px; bottom: 0;
            width: 420px;
            background: var(--bg-secondary);
            border-left: 1px solid var(--border-color);
            transition: right 0.25s cubic-bezier(0.4, 0, 0.2, 1);
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
        .drawer-title { font-size: 15px; font-weight: 700; color: var(--text-primary); }
        .drawer-close-btn { background: none; border: none; color: var(--text-muted); font-size: 18px; cursor: pointer; }
        .drawer-close-btn:hover { color: var(--text-primary); }

        /* ── Mobile Responsive ── */
        @media (max-width: 768px) {
            .sidebar {
                position: fixed;
                top: 0; bottom: 0; left: -280px;
            }
            .sidebar.mobile-open { transform: translateX(280px); }
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
            <div class="brand">
                <span>🌌 APEX RUNTIME</span>
                <span class="brand-badge">AI</span>
            </div>
            <button class="new-chat-btn" onclick="startNewConversation()">+ New Conversation</button>
        </div>
        <div class="convos-list" id="convosList"></div>
        <div class="sidebar-footer">
            <button class="footer-action-btn" onclick="exportActiveChat('md')">Export (.md)</button>
            <button class="footer-action-btn" onclick="exportActiveChat('json')">Export (.json)</button>
            <button class="footer-action-btn danger" onclick="clearAllConversations()">Clear All</button>
        </div>
    </div>

    <!-- ── Main Viewport ── -->
    <div class="main-viewport">
        <!-- Top Navigation -->
        <div class="top-navbar">
            <div class="nav-left">
                <button class="menu-toggle" onclick="toggleSidebar()">☰</button>
                <div class="model-badge" id="modelPill">Loading Model...</div>
                <div class="status-pill online" id="apiStatusPill">
                    <div class="status-dot"></div>
                    <span id="apiStatusText">API Online</span>
                </div>
                <div class="status-pill loading" id="modelStatusPill">
                    <div class="status-dot"></div>
                    <span id="modelStatusText">Model Initializing</span>
                </div>
            </div>
            <div>
                <button class="api-drawer-btn" onclick="toggleDrawer(true)">⚙ API Integration</button>
            </div>
        </div>

        <!-- Messages Container -->
        <div class="messages-container" id="messagesContainer">
            <div class="empty-state" id="emptyState">
                <h2>Welcome to APEX</h2>
                <p>Universal AI communication interface powered by direct open-source inference.</p>
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
                    <button class="action-icon-btn" title="Attach Document (TXT, PDF, PY, JSON, CSV)" onclick="document.getElementById('fileInput').click()">📎</button>
                    <textarea class="message-input" id="messageInput" placeholder="Message the model... (Enter to send, Shift+Enter for newline)" rows="1" oninput="autoResize(this)" onkeydown="handleKeyDown(event)"></textarea>
                    <button class="send-btn" id="sendBtn" onclick="handleSendAction()">➔</button>
                </div>
            </div>
        </div>
    </div>

    <!-- ── Developer Drawer ── -->
    <div class="drawer-overlay" id="drawerOverlay" onclick="toggleDrawer(false)"></div>
    <div class="drawer" id="drawer">
        <div class="drawer-header">
            <div class="drawer-title">API Integration & Credentials</div>
            <button class="drawer-close-btn" onclick="toggleDrawer(false)">✕</button>
        </div>
        <div style="font-size: 13px; color: var(--text-secondary); line-height: 1.6;">
            <div><b>Active Model:</b> <span id="drawerModel" style="color:var(--text-primary); font-family:monospace;">—</span></div>
            <div style="margin-top:6px;"><b>Public Endpoint:</b> <span id="drawerEndpoint" style="color:var(--accent-blue); font-family:monospace;">—</span></div>
            <div style="margin-top:6px;"><b>OpenAI Base URL:</b> <span id="drawerBaseUrl" style="color:var(--accent-blue); font-family:monospace;">—</span></div>
            <div style="margin-top:6px;"><b>API Key Status:</b> <span id="authStatusBadge" style="color:var(--accent-green);">Configured</span></div>
            <div style="margin-top:8px;">
                <input id="drawerApiKeyInput" type="password" placeholder="Enter API Key (if authentication enabled)..." style="width:100%; background:var(--bg-card); border:1px solid var(--border-color); color:var(--text-primary); border-radius:6px; padding:7px 10px; font-size:12px; box-sizing:border-box;" onchange="saveApiKey(this.value)">
            </div>

            <div style="margin-top: 18px; font-weight: 700; color: var(--text-primary);">Python OpenAI Client:</div>
            <div class="code-block-wrapper">
                <div class="code-header">
                    <span>python</span>
                    <button class="copy-code-btn" onclick="copySnippet('pythonCodeSnippet')">Copy</button>
                </div>
                <pre id="pythonCodeSnippet"></pre>
            </div>

            <div style="margin-top: 14px; font-weight: 700; color: var(--text-primary);">cURL Request:</div>
            <div class="code-block-wrapper">
                <div class="code-header">
                    <span>bash</span>
                    <button class="copy-code-btn" onclick="copySnippet('curlCodeSnippet')">Copy</button>
                </div>
                <pre id="curlCodeSnippet"></pre>
            </div>
        </div>
    </div>

    <!-- ── Application Logic ── -->
    <script>
        // State
        let activeConversationId = null;
        let isStreaming = false;
        let abortController = null;
        let activeAttachments = [];
        let currentModelId = "Qwen/Qwen2.5-0.5B-Instruct";
        let isModelReady = false;
        let lastUserMessage = "";

        // Initialization
        window.addEventListener("DOMContentLoaded", async () => {
            await fetchRuntimeInfo();
            await loadConversationsList();
            setupDragAndDrop();
            // Periodic health polling
            setInterval(fetchRuntimeInfo, 4000);
        });

        async function fetchRuntimeInfo() {
            try {
                const res = await fetch("/health");
                if (res.ok) {
                    const data = await res.json();
                    currentModelId = data.model_loaded && data.model_loaded !== "none" ? data.model_loaded : currentModelId;
                    isModelReady = !!data.is_model_ready;

                    // Update UI Pills
                    const shortName = currentModelId.split("/").pop();
                    document.getElementById("modelPill").textContent = "Model: " + shortName;

                    const apiPill = document.getElementById("apiStatusPill");
                    apiPill.className = "status-pill online";
                    document.getElementById("apiStatusText").textContent = "API Online";

                    const modelPill = document.getElementById("modelStatusPill");
                    if (isModelReady) {
                        modelPill.className = "status-pill online";
                        document.getElementById("modelStatusText").textContent = "Model Ready";
                    } else if (data.model === "loading") {
                        modelPill.className = "status-pill loading";
                        document.getElementById("modelStatusText").textContent = "Loading Weights...";
                    } else {
                        modelPill.className = "status-pill error";
                        document.getElementById("modelStatusText").textContent = "Inference Unavailable";
                    }

                    updateDeveloperDrawer(currentModelId);
                } else {
                    setApiDisconnected();
                }
            } catch (err) {
                setApiDisconnected();
            }
        }

        function setApiDisconnected() {
            const apiPill = document.getElementById("apiStatusPill");
            apiPill.className = "status-pill error";
            document.getElementById("apiStatusText").textContent = "Disconnected";

            const modelPill = document.getElementById("modelStatusPill");
            modelPill.className = "status-pill error";
            document.getElementById("modelStatusText").textContent = "Offline";
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
                authBadge.style.color = currentKey ? "var(--accent-blue)" : "var(--accent-green)";
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

            const authHeaderLine = currentKey ? `  -H "Authorization: Bearer ${currentKey}" \\\\n` : "";
            const curlSnippet = `curl -X POST ${host}/v1/chat/completions \\\\
${authHeaderLine}  -H "Content-Type: application/json" \\\\
  -d '{"model": "${modelId}", "messages": [{"role": "user", "content": "Hello!"}]}'`;

            document.getElementById("pythonCodeSnippet").textContent = pySnippet;
            document.getElementById("curlCodeSnippet").textContent = curlSnippet;
        }

        function copySnippet(id) {
            const text = document.getElementById(id).textContent;
            navigator.clipboard.writeText(text);
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
                    <div class="convo-title">
                        <span>💬</span>
                        <span style="overflow:hidden; text-overflow:ellipsis;">${escapeHtml(c.title)}</span>
                    </div>
                    <button class="convo-delete-btn" title="Delete conversation" onclick="deleteConversation(event, '${c.conversation_id}')">✕</button>
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
                dropZone.addEventListener(evt, (e) => { e.preventDefault(); dropZone.style.borderColor = "var(--accent-red)"; });
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
            lastUserMessage = rawText;

            // Compose user prompt
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
            inputEl.style.height = "38px";
            activeAttachments = [];
            renderAttachmentChips();

            // Create Conversation if None Exists
            if (!activeConversationId) {
                try {
                    const titleText = rawText ? rawText.slice(0, 30) : "Chat";
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
                    if (res.status === 503) {
                        assistantBubble.innerHTML = `<span style="color:var(--accent-amber)">Model is currently loading or initializing. Please retry in a few moments.</span>`;
                        return;
                    }
                    const err = await res.json().catch(() => ({}));
                    assistantBubble.innerHTML = `<span style="color:var(--accent-red)">Inference Error: ${err.detail || "Model execution failed"}</span>`;
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
                        const trimmed = line.trim();
                        if (trimmed.startsWith("data: ")) {
                            const chunk = trimmed.slice(6).trim();
                            if (chunk === "[DONE]") break;
                            try {
                                const parsed = JSON.parse(chunk);
                                const delta = parsed.choices?.[0]?.delta;
                                if (delta && delta.content) {
                                    accumulatedTokens += delta.content;
                                    assistantBubble.innerHTML = renderMarkdown(accumulatedTokens);
                                    scrollToBottom();
                                }
                            } catch(e) {}
                        }
                    }
                }
            } catch (err) {
                if (err.name === "AbortError") {
                    assistantBubble.innerHTML += `<div style="font-size:11px; color:var(--text-muted); margin-top:6px;">[Generation stopped by user]</div>`;
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
            actions.className = "assistant-actions";

            const copyBtn = document.createElement("button");
            copyBtn.className = "msg-action-btn";
            copyBtn.innerHTML = "📋 Copy";
            copyBtn.onclick = () => {
                navigator.clipboard.writeText(contentDiv.innerText);
                copyBtn.innerHTML = "✓ Copied";
                setTimeout(() => copyBtn.innerHTML = "📋 Copy", 2000);
            };

            const regenBtn = document.createElement("button");
            regenBtn.className = "msg-action-btn";
            regenBtn.innerHTML = "🔄 Regenerate";
            regenBtn.onclick = () => {
                if (lastUserMessage) {
                    document.getElementById("messageInput").value = lastUserMessage;
                    handleSendAction();
                }
            };

            actions.appendChild(copyBtn);
            actions.appendChild(regenBtn);
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
                const language = lang || "code";
                return `<div class="code-block-wrapper"><div class="code-header"><span>${language}</span><button class="copy-code-btn" onclick="copyCode(this)">Copy</button></div><pre><code>${code}</code></pre></div>`;
            });

            // Inline code `...`
            html = html.replace(/`([^`]+)`/g, "<code>$1</code>");

            // Bold and italics
            html = html.replace(/\\*\\*([^\\*]+)\\*\\*/g, "<b>$1</b>");
            html = html.replace(/\\*([^\\*]+)\\*/g, "<i>$1</i>");

            // Blockquotes
            html = html.replace(/^>\\s*(.+)$/gm, "<blockquote>$1</blockquote>");

            // Paragraphs / line breaks
            html = html.replace(/\\n\\n/g, "</p><p>");
            html = html.replace(/\\n/g, "<br>");
            return "<p>" + html + "</p>";
        }

        function copyCode(btn) {
            const pre = btn.closest(".code-block-wrapper").querySelector("pre code");
            if (pre) {
                navigator.clipboard.writeText(pre.innerText);
                btn.textContent = "Copied!";
                setTimeout(() => btn.textContent = "Copy", 2000);
            }
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
