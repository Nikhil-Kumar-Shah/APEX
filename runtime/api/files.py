"""Files API for APEX Runtime — Real document ingestion & context processing."""

import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from runtime.api.file_processor import FileProcessor, FileValidationError

router = APIRouter()

# In-memory registry for uploaded file metadata mapping (file_id -> info)
_FILE_REGISTRY: Dict[str, Dict[str, Any]] = {}


def _get_processor(req: Request) -> FileProcessor:
    """Resolves workspace upload directory and FileProcessor instance."""
    base_dir = Path.cwd() / "workspaces" / "default" / "uploads"
    base_dir.mkdir(parents=True, exist_ok=True)
    return FileProcessor(base_dir)


@router.post("/v1/files")
async def upload_file(
    req: Request,
    file: UploadFile = File(...),
    purpose: str = Form("assistants"),
):
    """Uploads, validates, and processes a document for conversational context."""
    processor = _get_processor(req)
    try:
        content = await file.read()
        file_id = f"file-{uuid.uuid4().hex[:12]}"
        safe_filename = file.filename or "unnamed_upload.txt"

        saved_path = processor.save_upload(safe_filename, content)
        extracted_text, truncated = processor.prepare_context(saved_path)

        file_info = {
            "id": file_id,
            "object": "file",
            "bytes": len(content),
            "created_at": int(time.time()),
            "filename": safe_filename,
            "purpose": purpose,
            "status": "processed",
            "path": str(saved_path),
            "extracted_text": extracted_text,
            "preview": extracted_text[:300].strip(),
            "truncated": truncated,
        }
        _FILE_REGISTRY[file_id] = file_info

        return JSONResponse(
            status_code=200,
            content={
                "id": file_info["id"],
                "object": file_info["object"],
                "bytes": file_info["bytes"],
                "created_at": file_info["created_at"],
                "filename": file_info["filename"],
                "purpose": file_info["purpose"],
                "status": file_info["status"],
                "extracted_text": file_info["extracted_text"],
                "preview": file_info["preview"],
                "truncated": file_info["truncated"],
            },
        )
    except FileValidationError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File processing error: {e}")


@router.get("/v1/files")
async def list_files():
    """Lists all files uploaded in the active workspace."""
    results = []
    for f in _FILE_REGISTRY.values():
        results.append(
            {
                "id": f["id"],
                "object": "file",
                "bytes": f["bytes"],
                "created_at": f["created_at"],
                "filename": f["filename"],
                "purpose": f["purpose"],
                "status": f["status"],
            }
        )
    return {"object": "list", "data": results}


@router.get("/v1/files/{file_id}")
async def retrieve_file(file_id: str):
    """Retrieves metadata and extracted context for a specific file (sanitized, no internal paths)."""
    if file_id not in _FILE_REGISTRY:
        raise HTTPException(status_code=404, detail=f"File '{file_id}' not found.")
    info = _FILE_REGISTRY[file_id]
    return {
        "id": info["id"],
        "object": info["object"],
        "bytes": info["bytes"],
        "created_at": info["created_at"],
        "filename": info["filename"],
        "purpose": info["purpose"],
        "status": info["status"],
        "extracted_text": info.get("extracted_text", ""),
        "preview": info.get("preview", ""),
        "truncated": info.get("truncated", False),
    }


@router.delete("/v1/files/{file_id}")
async def delete_file(file_id: str):
    """Deletes an uploaded file from disk and registry."""
    if file_id not in _FILE_REGISTRY:
        raise HTTPException(status_code=404, detail=f"File '{file_id}' not found.")
    info = _FILE_REGISTRY.pop(file_id)
    target_path = Path(info.get("path", ""))
    if target_path.is_file():
        try:
            target_path.unlink()
        except OSError:
            pass
    return {"id": file_id, "object": "file", "deleted": True}
