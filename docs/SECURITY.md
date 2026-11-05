# APEX Security Policy & Architecture

Security principles, authentication mechanisms, and vulnerability reporting procedures.

---

## 1. Security Architecture Principles

1. **Principle of Least Privilege**: Public discovery endpoints (`/health`, `/chat`, `/`, `/version`) do not expose internal secrets, file paths, or state. Computational endpoints (`/v1/*`, `/runtime`) require Bearer token validation when authentication is enabled.
2. **Zero Arbitrary Execution**: Uploaded files and documents are processed purely in-memory as text or data tokens. Uploaded code files (`.py`, `.js`, etc.) are never executed on the host system.
3. **Defense Against Traversal**: All file access operations sanitize input filenames via basename isolation and regex normalization, strictly blocking `../` directory traversal attempts.
4. **Denial of Service Mitigation**:
   - File uploads capped at 10 MB.
   - Document context capped at 16,000 characters.
   - Long conversation turns managed via a sliding window guard (system prompt + 16 turns).
5. **Strict HTML Entity Escaping**: The Web Interface strictly encodes `&`, `<`, `>`, `"`, and `'` before rendering to prevent Cross-Site Scripting (XSS) and attribute breakout attacks.

---

## 2. API Key Authentication

When `enable_auth: true` is configured in `configs/apex.config.json` or enabled in the Launchpad:

- API requests must provide the key via HTTP header:
  ```http
  Authorization: Bearer <your-api-key>
  ```
- APEX validates tokens using `secrets.compare_digest` to eliminate side-channel timing attack vectors.
- If no key is configured by the user, APEX generates a 32-byte cryptographically secure random token (`APEX_<urlsafe_token>`).

---

## 3. Reporting a Vulnerability

If you discover a security vulnerability in APEX, please report it responsibly:

- **Email**: Send vulnerability reports to `security@apex-project.org` or open a private security advisory on GitHub.
- **Please Include**:
  - Detailed description of the vulnerability.
  - Minimal reproducible example or proof-of-concept request.
  - Expected vs. actual behavior.
- **Response Timeline**: The maintainers will acknowledge receipt within 48 hours and provide a remediation plan. Please do not publish security exploits publicly until patches have been merged.

