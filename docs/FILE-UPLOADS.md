# Document Ingestion & Context Processing

APEX includes a built-in document ingestion engine allowing users to attach code, text, spreadsheets, and document files to conversations.

---

## 1. Supported File Formats

| Format Category | Supported Extensions | Extraction Method |
| :--- | :--- | :--- |
| **Code & Scripts** | `.py`, `.js`, `.html`, `.css`, `.xml`, `.json` | UTF-8 plain text with whitespace preservation. |
| **Plain Text** | `.txt`, `.md`, `.log`, `.csv`, `.tsv` | UTF-8 parsing with latin-1 fallback. |
| **Office Documents** | `.docx` | Native XML extraction of `<w:t>` paragraph tags via `zipfile`. |
| **PDF Documents** | `.pdf` | Native Python stream parsing for `Tj` / `TJ` text objects. |
| **Images** | `.png`, `.jpg`, `.jpeg`, `.webp` | Ingested with metadata and multimodal notice. |

*Note: Executable binaries (`.exe`, `.sh`, `.bat`, `.dll`) and unsupported formats are strictly rejected.*

---

## 2. Ingestion Constraints & Safety Limits

1. **File Size Cap**: Uploads are strictly capped at **10 MB** (`MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024`). Files exceeding 10MB are rejected with HTTP 413.
2. **Context Window Cap**: To protect the model's VRAM and context limit, extracted text is bounded to **16,000 characters**. Files exceeding this length are truncated with an explicit note injected into the context:
   ```text
   [... Document truncated to fit model context limit ...]
   ```
3. **Path Traversal Protection**: Filenames containing `../` or absolute directory paths are stripped and sanitized. Files are stored under `workspaces/default/uploads/` using unique UUID-prefixed names.
4. **Filesystem Privacy**: Endpoint responses (`/v1/files/{file_id}`) return only sanitized metadata (`id`, `filename`, `bytes`, `created_at`, `extracted_text`), never exposing local server paths.

---

## 3. Uploading Files via API

### cURL Upload Example
```bash
curl -X POST https://<your-subdomain>.trycloudflare.com/v1/files \
  -H "Authorization: Bearer your-api-key" \
  -F "file=@sample_code.py" \
  -F "purpose=assistants"
```

### JSON Response
```json
{
  "id": "file-12a34b56c78d",
  "object": "file",
  "bytes": 4096,
  "created_at": 1730832000,
  "filename": "sample_code.py",
  "purpose": "assistants",
  "status": "processed",
  "extracted_text": "def calculate_primes(n): ...",
  "preview": "def calculate_primes(n):",
  "truncated": false
}
```

---

## 4. Web Interface Drag & Drop

In the APEX Web Chat Interface:
1. Click the **📎 (Attach Document)** button or drag and drop supported files directly onto the message composer.
2. An attachment chip displaying the filename and file size will appear above the input box.
3. Type your query (e.g. *"Review this code for potential memory leaks"*) and press Enter.
4. APEX automatically formats the document text into the prompt context and streams the model's analysis in real-time.

