# Security Policy

## Overview

APEX is designed to be deployed in developer-controlled environments and may expose its API publicly via tunnels (ngrok, Cloudflare Tunnel). This document describes the security model, authentication system, threat considerations, and the responsible disclosure process.

**If you have found a security vulnerability, please do NOT open a public GitHub issue. See [Reporting a Vulnerability](#reporting-a-vulnerability) below.**

---

## Supported Versions

Security patches are applied to actively maintained versions only.

| Version | Supported | Notes |
|---|---|---|
| `1.2.x` | ✅ Active | Current stable release |
| `1.0.x` | ⚠️ Best-effort | Critical fixes only |
| `< 1.0` | ❌ Unsupported | No patches issued |

---

## Security Architecture

### Authentication

APEX supports multiple authentication modes, configurable in `apex.config.json`:

| Mode | Description | Recommended For |
|---|---|---|
| **Disabled** | No authentication. All requests accepted. | Local development only |
| **API Key** | Static API key sent as `Authorization: Bearer <key>` | Shared tunnel deployments |
| **Developer Mode** | Auth disabled, verbose logging enabled | Local debugging |

To enable API key authentication:

```json
{
  "api": {
    "enable_auth": true,
    "api_key": "your-strong-secret-key-here"
  }
}
```

**Never commit your API key to a repository.** Use environment variables or a secrets manager.

### Transport Security

APEX does not implement TLS natively. **Always use a TLS-terminating proxy** when exposing the API publicly:

- **Cloudflare Tunnel** — Recommended. Provides automatic HTTPS without port forwarding.
- **ngrok** — Supported. Provides temporary HTTPS URLs.
- **nginx / Caddy** — For production deployments with a fixed domain.

**Never expose `http://` directly to the internet.**

### Secret Handling

APEX applies the following principles for secret management:

- API keys and tokens are never logged, even at DEBUG level.
- The `security.py` exception handler strips Python tracebacks from all API error responses.
- Configuration files containing credentials should not be committed. Add `configs/` to `.gitignore` for deployments with live credentials.

### Error Handling

All API errors are returned in the OpenAI error format — no Python tracebacks, no internal paths, and no system information are exposed:

```json
{
  "error": {
    "message": "Authentication failed. Provide a valid Bearer token.",
    "type": "authentication_error",
    "code": "invalid_api_key",
    "details": {
      "resolution": "Pass a valid API key as 'Authorization: Bearer <key>'"
    }
  }
}
```

---

## Threat Model

Understanding what APEX is and is not designed to protect against:

| Threat | APEX Mitigation | Notes |
|---|---|---|
| Unauthenticated API access | API key auth (configurable) | Must be explicitly enabled |
| Credential leakage in logs | Secrets never logged | By design |
| Python traceback leakage | Secure exception handler | Always active |
| HTTPS / man-in-the-middle | Use Cloudflare/ngrok tunnel | Not APEX's responsibility |
| Prompt injection | Not mitigated | Model-level concern |
| Model extraction | Not mitigated | Inference-level concern |
| Denial of service | Request queue with limits | Rate limiting planned for v1.3 |
| Path traversal in file uploads | File API not implemented | Planned with sandboxing |

---

## Reporting a Vulnerability

We take the security of APEX seriously. If you discover a security vulnerability — including but not limited to:

- Authentication bypass
- API key or credential exposure
- Directory traversal or path injection
- Remote code execution
- Denial of service vulnerabilities
- Information disclosure via error messages

Please **do not open a public GitHub issue**.

### Disclosure Process

1. **Contact the maintainer privately** via the contact form at [https://www.nikhilkshah.me/contact](https://www.nikhilkshah.me/contact).

2. **Include the following information:**
   - A clear description of the vulnerability.
   - Step-by-step reproduction instructions.
   - Your assessment of the potential impact.
   - The APEX version and environment (OS, Python version, deployment method).
   - Any suggested mitigations, if applicable.

3. **Response timeline:**
   - Initial acknowledgement: within **48 hours**.
   - Severity assessment: within **5 business days**.
   - Patch or mitigation: within **14 days** for critical issues, **30 days** for moderate issues.

4. **Coordinated disclosure:** We will coordinate a public disclosure date with you and credit your finding in the security advisory and CHANGELOG.

---

## Security Checklist for Deployment

Before exposing APEX to a network:

- [ ] Enable `enable_auth: true` in your config
- [ ] Set a strong, random `api_key` (minimum 32 characters)
- [ ] Use Cloudflare Tunnel or ngrok for HTTPS — never plain HTTP
- [ ] Ensure `configs/apex.config.json` is excluded from any public repository
- [ ] Do not commit API keys, HuggingFace tokens, or ngrok auth tokens
- [ ] Rotate your API key if you believe it has been exposed
- [ ] Review request logs for unexpected access patterns

---

## Acknowledgements

We gratefully acknowledge security researchers who responsibly disclose vulnerabilities. Contributors will be credited in the relevant GitHub Security Advisory.
