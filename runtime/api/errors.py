"""Error handling for APEX Universal OpenAI Compatible Runtime API."""

from fastapi.responses import JSONResponse

def openai_error_response(message: str, error_type: str = "invalid_request_error", code: str = None, status_code: int = 400, details: dict = None) -> JSONResponse:
    error_dict = {
        "message": message,
        "type": error_type,
        "code": code
    }
    if details:
        error_dict["details"] = details
        
    return JSONResponse(
        status_code=status_code,
        content={"error": error_dict}
    )
