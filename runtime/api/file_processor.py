"""Document and file processing subsystem for APEX AI Communication Interface."""

import json
import logging
import os
import re
import zipfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import xml.etree.ElementTree as ET

logger = logging.getLogger("runtime.api.files")

# Maximum permitted file size: 10 MB
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

# Supported extensions
ALLOWED_TEXT_EXTENSIONS = {".txt", ".md", ".log", ".json", ".csv", ".tsv", ".py", ".js", ".html", ".css", ".xml"}
ALLOWED_DOC_EXTENSIONS = {".pdf", ".docx"}
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
ALL_ALLOWED_EXTENSIONS = ALLOWED_TEXT_EXTENSIONS | ALLOWED_DOC_EXTENSIONS | ALLOWED_IMAGE_EXTENSIONS


class FileValidationError(Exception):
    """Raised when an uploaded file fails validation checks."""
    pass


class FileProcessor:
    """Validates, sanitizes, and extracts contextual text from uploaded documents."""

    def __init__(self, upload_dir: Path):
        self.upload_dir = upload_dir
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def validate_file(self, filename: str, file_size: int) -> None:
        """Enforces security rules, extension whitelists, and size limits."""
        if not filename or not isinstance(filename, str):
            raise FileValidationError("Filename must be a non-empty string.")

        # 1. Path traversal prevention
        clean_name = Path(filename).name
        if clean_name != filename or ".." in filename or "/" in filename or "\\" in filename:
            raise FileValidationError(f"Invalid or unsafe filename: '{filename}'")

        # 2. File size enforcement
        if file_size > MAX_FILE_SIZE_BYTES:
            raise FileValidationError(
                f"File '{filename}' exceeds maximum size limit of {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB."
            )

        if file_size <= 0:
            raise FileValidationError(f"File '{filename}' is empty (0 bytes).")

        # 3. Extension check
        ext = Path(filename).suffix.lower()
        if ext not in ALL_ALLOWED_EXTENSIONS:
            raise FileValidationError(
                f"Unsupported file format '{ext}'. Supported formats: {', '.join(sorted(ALL_ALLOWED_EXTENSIONS))}"
            )

    def save_upload(self, filename: str, content: bytes) -> Path:
        """Safely saves upload bytes into the workspace upload directory."""
        self.validate_file(filename, len(content))
        clean_name = Path(filename).name
        target_path = self.upload_dir / clean_name

        # Avoid collisions by prefixing if already exists
        if target_path.exists():
            import uuid
            prefix = uuid.uuid4().hex[:6]
            clean_name = f"{prefix}_{clean_name}"
            target_path = self.upload_dir / clean_name

        with open(target_path, "wb") as f:
            f.write(content)

        return target_path

    def extract_text(self, file_path: Path) -> str:
        """Extracts text content from supported file types."""
        if not file_path.exists() or not file_path.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")

        ext = file_path.suffix.lower()

        if ext in ALLOWED_TEXT_EXTENSIONS:
            return self._extract_plain_text(file_path, ext)
        elif ext == ".docx":
            return self._extract_docx(file_path)
        elif ext == ".pdf":
            return self._extract_pdf(file_path)
        elif ext in ALLOWED_IMAGE_EXTENSIONS:
            return self._extract_image_info(file_path)
        else:
            return f"[Unsupported document type: {ext}]"

    def _extract_plain_text(self, file_path: Path, ext: str) -> str:
        """Reads plain text files with robust encoding fallback."""
        raw_bytes = file_path.read_bytes()
        try:
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = raw_bytes.decode("latin-1")
            except Exception:
                text = raw_bytes.decode("utf-8", errors="replace")

        if ext == ".json":
            try:
                parsed = json.loads(text)
                return json.dumps(parsed, indent=2)
            except Exception:
                pass

        return text

    def _extract_docx(self, file_path: Path) -> str:
        """Extracts text paragraphs from a .docx file using standard library zipfile and XML."""
        try:
            with zipfile.ZipFile(file_path, "r") as docx_zip:
                xml_content = docx_zip.read("word/document.xml")
                root = ET.fromstring(xml_content)
                # WordprocessingML namespace
                namespaces = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                paragraphs = []
                for p in root.findall(".//w:p", namespaces):
                    texts = [node.text for node in p.findall(".//w:t", namespaces) if node.text]
                    if texts:
                        paragraphs.append("".join(texts))
                return "\n\n".join(paragraphs)
        except Exception as e:
            logger.warning(f"DOCX text extraction error: {e}")
            return f"[Error extracting text from DOCX: {e}]"

    def _extract_pdf(self, file_path: Path) -> str:
        """Extracts text from PDF streams using pure-Python parsing."""
        raw = file_path.read_bytes()
        extracted_chunks = []

        # Find text blocks delimited by BT ... ET in uncompressed streams
        # or search for text objects (Tj, TJ)
        text_pattern = re.compile(rb"\((.*?)\)\s*Tj", re.DOTALL)
        for match in text_pattern.finditer(raw):
            try:
                chunk = match.group(1).decode("utf-8", errors="ignore")
                if chunk.strip():
                    extracted_chunks.append(chunk)
            except Exception:
                pass

        if not extracted_chunks:
            # Fallback regex for text strings in PDF objects
            fallback_pattern = re.compile(rb"\[(.*?)\]\s*TJ", re.DOTALL)
            for match in fallback_pattern.finditer(raw):
                try:
                    inner = match.group(1)
                    sub_chunks = re.findall(rb"\((.*?)\)", inner)
                    for sc in sub_chunks:
                        s = sc.decode("utf-8", errors="ignore")
                        if s.strip():
                            extracted_chunks.append(s)
                except Exception:
                    pass

        if extracted_chunks:
            return " ".join(extracted_chunks)

        # If PDF is binary encoded/compressed, report metadata cleanly
        size_kb = len(raw) / 1024
        return f"[PDF Document: {file_path.name} ({size_kb:.1f} KB). Binary compressed stream extracted.]"

    def _extract_image_info(self, file_path: Path) -> str:
        """Extracts image metadata and returns capability-aware description."""
        size_kb = file_path.stat().st_size / 1024
        return (
            f"[Attached Image: {file_path.name} ({size_kb:.1f} KB)]\n"
            f"Note: Current model operates in language-mode. Ensure a multimodal/vision model is loaded to analyze image pixels."
        )

    def prepare_context(self, file_path: Path, max_chars: int = 16000) -> Tuple[str, bool]:
        """Extracts text and applies context window bounding with notification."""
        raw_text = self.extract_text(file_path)
        truncated = False
        if len(raw_text) > max_chars:
            raw_text = raw_text[:max_chars] + "\n\n[... Document truncated to fit model context limit ...]"
            truncated = True
        return raw_text, truncated

