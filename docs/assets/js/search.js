/**
 * APEX Documentation — Client-side Search & Interactive Utilities
 * Zero external dependencies. Works on GitHub Pages and local file preview.
 */

(function () {
  'use strict';

  // Fallback search index for offline/file:// protocol execution
  const FALLBACK_SEARCH_INDEX = [
    {
      title: "Overview",
      url: "index.html",
      section: "What is APEX?",
      keywords: "overview architecture platform introduction colab runtime gpu model",
      snippet: "APEX is an open-source, notebook-first AI runtime platform that runs language models on user-controlled hardware and exposes them through an OpenAI-compatible API and web chat."
    },
    {
      title: "Overview",
      url: "index.html#architecture",
      section: "System Architecture",
      keywords: "architecture pipeline workflow colab tunnel cloudflare rest sse",
      snippet: "APEX connects runtime environments (Google Colab or Local) to loaded models, exposing them via Cloudflare Quick Tunnel as an OpenAI-compatible API and chat interface."
    },
    {
      title: "Overview",
      url: "index.html#capabilities",
      section: "Verified Capabilities",
      keywords: "capabilities features verified openai streaming chat models files token auth",
      snippet: "Verified capabilities include single-click notebook launch, streaming chat completions, document ingestion (.txt, .pdf, .docx, .csv, .json), and Cloudflare HTTPS tunneling."
    },
    {
      title: "Getting Started",
      url: "getting-started.html",
      section: "Quick Start Guide",
      keywords: "getting started launch colab notebook setup run step by step",
      snippet: "Start APEX in under 2 minutes: open the notebook in Google Colab, select a model, click START APEX, and open the web chat or copy your API credentials."
    },
    {
      title: "Getting Started",
      url: "getting-started.html#workflow",
      section: "Standard User Workflow",
      keywords: "workflow steps launchpad open chat api key bearer connection",
      snippet: "Step-by-step workflow covering model selection, hardware inspection, verified 10-step startup checklist, accessing the web interface, and safe shutdown."
    },
    {
      title: "Getting Started",
      url: "getting-started.html#hardware",
      section: "Hardware & GPU Reality",
      keywords: "hardware gpu vram colab t4 memory requirements oom cpu",
      snippet: "Honest breakdown of GPU requirements: 0.5B models require ~1.2 GB VRAM, 1.5B models require ~3.5 GB VRAM, and 7B models fit within Colab T4's 15 GB VRAM."
    },
    {
      title: "Configuration",
      url: "configuration.html",
      section: "Configuration Reference",
      keywords: "configuration settings apex.config.json options parameters port auth",
      snippet: "Reference guide for all active configuration parameters: Hugging Face model IDs and URLs, precision modes, authentication, ports, and generation limits."
    },
    {
      title: "Configuration",
      url: "configuration.html#model-id",
      section: "Model Selection & URLs",
      keywords: "model id url huggingface presets qwen llama gemma deepseek",
      snippet: "APEX accepts raw Hugging Face repository IDs (e.g. Qwen/Qwen2.5-1.5B) or full repository URLs, auto-normalizing branches and .git extensions."
    },
    {
      title: "Configuration",
      url: "configuration.html#precision",
      section: "Precision & VRAM Allocation",
      keywords: "precision float16 bfloat16 float32 auto vram fp16 bf16",
      snippet: "Precision controls model memory consumption. Auto defaults to float16 on CUDA GPUs, reducing VRAM usage by 50% compared to float32."
    },
    {
      title: "Configuration",
      url: "configuration.html#advanced",
      section: "Advanced Runtime Settings",
      keywords: "advanced settings port transport cloudflare local auth api key token",
      snippet: "Configure internal API ports, toggle Bearer authentication, select Cloudflare Quick Tunnel or local-only transport, and adjust max generation tokens."
    },
    {
      title: "API & Integration",
      url: "api.html",
      section: "OpenAI-Compatible REST API",
      keywords: "api integration openai rest endpoints chat completions models sdk python",
      snippet: "Connect Continue, Cline, Aider, Open WebUI, and standard OpenAI SDKs to APEX using the OpenAI-compatible /v1 endpoints."
    },
    {
      title: "API & Integration",
      url: "api.html#python-sdk",
      section: "Python OpenAI SDK Integration",
      keywords: "python sdk client openai example code chat completions streaming",
      snippet: "Use standard openai Python package with custom base_url and api_key to interact with your hosted APEX model."
    },
    {
      title: "API & Integration",
      url: "api.html#streaming",
      section: "Streaming Completions (SSE)",
      keywords: "streaming sse server sent events stream chunks tokens",
      snippet: "APEX implements real-time Server-Sent Events (SSE) streaming matching the exact OpenAI data: [DONE] protocol."
    },
    {
      title: "API & Integration",
      url: "api.html#files",
      section: "Document Ingestion (/v1/files)",
      keywords: "files upload ingestion documents context pdf docx txt csv",
      snippet: "Upload documents via POST /v1/files to extract sanitized text context and attach documents directly to conversational inference."
    },
    {
      title: "Troubleshooting",
      url: "troubleshooting.html",
      section: "Common Issues & Practical Fixes",
      keywords: "troubleshooting errors oom out of memory cuda timeout disconnect",
      snippet: "Practical diagnostic solutions for GPU out-of-memory errors, Hugging Face download failures, tunnel acquisition timeouts, and Colab session disconnects."
    },
    {
      title: "Troubleshooting",
      url: "troubleshooting.html#oom",
      section: "CUDA Out of Memory (OOM)",
      keywords: "oom vram cuda out of memory allocation exceed crash",
      snippet: "Resolve CUDA memory limits by switching precision from float32 to float16, selecting a smaller parameter model, or reducing context length."
    },
    {
      title: "Troubleshooting",
      url: "troubleshooting.html#auth",
      section: "Authentication & Key Errors",
      keywords: "authentication 401 403 api key token bearer unauthorized",
      snippet: "Fix unauthorized errors by ensuring Bearer token header is passed or checking Section 1 connection panel for the active auto-generated key."
    },
    {
      title: "Development",
      url: "development.html",
      section: "Contributor & Developer Guide",
      keywords: "development contributing tests pytest setup architecture security",
      snippet: "Guide for developers and contributors: repository structure, local environment setup, running the 124-test pytest suite, and security reporting."
    },
    {
      title: "Development",
      url: "development.html#testing",
      section: "Running the Test Suite",
      keywords: "testing pytest unit integration test suite run verify",
      snippet: "Execute python -m pytest -v to run all 124 automated unit and integration tests across runtime, API, lifecycle, and UI subsystems."
    },
    {
      title: "Development",
      url: "development.html#security",
      section: "Security & Disclosure Policy",
      keywords: "security vulnerability reporting disclosure contact policy",
      snippet: "Read the APEX security model: least-privilege endpoints, safe file parsing without path traversal, and private vulnerability disclosure procedures."
    }
  ];

  let searchIndex = FALLBACK_SEARCH_INDEX;
  let selectedIndex = -1;

  // Attempt to load search-index.json if on HTTP(S)
  if (window.location.protocol.startsWith('http')) {
    fetch('search-index.json')
      .then(function (res) {
        if (res.ok) return res.json();
        throw new Error('Index fetch status: ' + res.status);
      })
      .then(function (data) {
        if (Array.isArray(data) && data.length > 0) {
          searchIndex = data;
        }
      })
      .catch(function () {
        // Fallback silently remains active
      });
  }

  document.addEventListener('DOMContentLoaded', function () {
    const searchInput = document.getElementById('search-input');
    const searchResults = document.getElementById('search-results');
    const menuToggle = document.getElementById('menu-toggle');
    const sidebar = document.getElementById('sidebar');

    // ── Mobile Menu Toggle ──────────────────────────────────────────────────
    if (menuToggle && sidebar) {
      menuToggle.addEventListener('click', function () {
        sidebar.classList.toggle('open');
      });

      // Close sidebar when clicking outside on mobile
      document.addEventListener('click', function (e) {
        if (sidebar.classList.contains('open') &&
            !sidebar.contains(e.target) &&
            !menuToggle.contains(e.target)) {
          sidebar.classList.remove('open');
        }
      });
    }

    // ── Global Keyboard Shortcuts ───────────────────────────────────────────
    document.addEventListener('keydown', function (e) {
      if ((e.key === '/' || (e.ctrlKey && e.key === 'k')) && document.activeElement !== searchInput) {
        e.preventDefault();
        if (searchInput) {
          searchInput.focus();
          searchInput.select();
        }
      }
    });

    // ── Search Input Handler ────────────────────────────────────────────────
    if (searchInput && searchResults) {
      searchInput.addEventListener('input', function () {
        const query = searchInput.value.trim().toLowerCase();
        selectedIndex = -1;

        if (query.length < 2) {
          searchResults.classList.remove('active');
          searchResults.innerHTML = '';
          return;
        }

        const matches = searchIndex.filter(function (item) {
          const title = (item.title || '').toLowerCase();
          const section = (item.section || '').toLowerCase();
          const keywords = (item.keywords || '').toLowerCase();
          const snippet = (item.snippet || '').toLowerCase();

          return title.includes(query) ||
                 section.includes(query) ||
                 keywords.includes(query) ||
                 snippet.includes(query);
        });

        if (matches.length === 0) {
          searchResults.innerHTML = '<div class="search-empty">No documentation matches found.</div>';
          searchResults.classList.add('active');
          return;
        }

        let html = '';
        matches.slice(0, 8).forEach(function (m, idx) {
          html += '<a href="' + m.url + '" class="search-item" data-index="' + idx + '">';
          html += '<div class="search-item-title">' + escapeHtml(m.title) + ' &rsaquo; ' + escapeHtml(m.section) + '</div>';
          html += '<div class="search-item-snippet">' + escapeHtml(m.snippet) + '</div>';
          html += '</a>';
        });

        searchResults.innerHTML = html;
        searchResults.classList.add('active');
      });

      // Keyboard navigation in search dropdown
      searchInput.addEventListener('keydown', function (e) {
        const items = searchResults.querySelectorAll('.search-item');
        if (!searchResults.classList.contains('active') || items.length === 0) return;

        if (e.key === 'ArrowDown') {
          e.preventDefault();
          selectedIndex = (selectedIndex + 1) % items.length;
          updateSelected(items);
        } else if (e.key === 'ArrowUp') {
          e.preventDefault();
          selectedIndex = (selectedIndex - 1 + items.length) % items.length;
          updateSelected(items);
        } else if (e.key === 'Enter') {
          if (selectedIndex >= 0 && selectedIndex < items.length) {
            e.preventDefault();
            items[selectedIndex].click();
          }
        } else if (e.key === 'Escape') {
          searchResults.classList.remove('active');
          searchInput.blur();
        }
      });

      // Close search results when clicking outside
      document.addEventListener('click', function (e) {
        if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
          searchResults.classList.remove('active');
        }
      });
    }

    function updateSelected(items) {
      items.forEach(function (el, idx) {
        if (idx === selectedIndex) {
          el.classList.add('selected');
          el.scrollIntoView({ block: 'nearest' });
        } else {
          el.classList.remove('selected');
        }
      });
    }

    function escapeHtml(str) {
      return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }

    // ── Code Block Copy Buttons ─────────────────────────────────────────────
    document.querySelectorAll('pre').forEach(function (pre) {
      const code = pre.querySelector('code');
      if (!code) return;

      const wrapper = document.createElement('div');
      wrapper.className = 'code-block-wrapper';
      pre.parentNode.insertBefore(wrapper, pre);
      wrapper.appendChild(pre);

      const copyBtn = document.createElement('button');
      copyBtn.className = 'copy-btn';
      copyBtn.textContent = 'Copy';
      copyBtn.setAttribute('aria-label', 'Copy code to clipboard');
      wrapper.appendChild(copyBtn);

      copyBtn.addEventListener('click', function () {
        const textToCopy = code.innerText || code.textContent;
        navigator.clipboard.writeText(textToCopy).then(function () {
          copyBtn.textContent = 'Copied!';
          setTimeout(function () {
            copyBtn.textContent = 'Copy';
          }, 1800);
        }).catch(function () {
          copyBtn.textContent = 'Failed';
        });
      });
    });
  });
})();

