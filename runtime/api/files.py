"""Files API for APEX Runtime."""

from fastapi import APIRouter
from runtime.api.errors import openai_error_response

router = APIRouter()

@router.post("/v1/files")
async def upload_file():
    return openai_error_response(
        message="The file upload functionality is temporarily disabled or not yet implemented.",
        error_type="not_implemented_error",
        code="endpoint_not_implemented",
        status_code=501,
        details={"resolution": "This endpoint will be activated once the secure file storage backend is fully integrated."}
    )

@router.get("/v1/files")
async def list_files():
    return openai_error_response(
        message="Listing uploaded files is not currently supported.",
        error_type="not_implemented_error",
        code="endpoint_not_implemented",
        status_code=501,
        details={"resolution": "This feature depends on the upcoming file management subsystem."}
    )

@router.delete("/v1/files/{file_id}")
async def delete_file(file_id: str):
    return openai_error_response(
        message=f"Cannot delete file '{file_id}' because the file management system is not active.",
        error_type="not_implemented_error",
        code="endpoint_not_implemented",
        status_code=501,
        details={"resolution": "This feature depends on the upcoming file management subsystem.", "file_id": file_id}
    )
