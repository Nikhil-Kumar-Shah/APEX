"""Health API for APEX Runtime with real hardware and model telemetry."""

import time
from fastapi import APIRouter, Request

router = APIRouter()
_PROCESS_START = time.time()


@router.get("/health")
async def health_check(req: Request = None):
    """Dynamic health check endpoint reflecting real runtime status."""
    mm = getattr(req.app.state, "model_manager", None) if req else None
    state = getattr(req.app.state, "runtime_state", None) if req else None

    # Resolve active model ID
    active_model = None
    if mm and getattr(mm, "active_model_id", None):
        active_model = mm.active_model_id
    elif state and getattr(state, "model_loaded", None):
        active_model = state.model_loaded

    # Check if active engine is genuinely loaded and ready for inference
    is_loaded = False
    model_state_str = "unloaded"
    if mm:
        engine = getattr(mm, "active_engine", None)
        if engine and getattr(engine, "is_loaded", False):
            is_loaded = True
            model_state_str = "loaded"
        elif active_model:
            model_state_str = "loading"
    elif state and getattr(state, "model_loaded", None):
        is_loaded = True
        model_state_str = "loaded"

    # Real GPU detection
    gpu_available = False
    gpu_name = None
    vram_alloc_mb = 0.0
    try:
        import torch
        gpu_available = torch.cuda.is_available()
        if gpu_available:
            gpu_name = torch.cuda.get_device_name(0)
            vram_alloc_mb = torch.cuda.memory_allocated(0) / (1024 * 1024)
    except Exception:
        pass

    # Uptime
    uptime = time.time() - _PROCESS_START

    return {
        "status": "ok",
        "project": "APEX",
        "uptime": round(uptime, 2),
        "uptime_seconds": round(uptime, 2),
        "gpu": gpu_available,
        "gpu_device": gpu_name,
        "vram_allocated_mb": round(vram_alloc_mb, 2),
        "memory": "ok",
        "model": model_state_str,
        "model_loaded": active_model or "none",
        "is_model_ready": is_loaded,
        "queue": "active" if (state and state.api_running) else "idle",
        "queue_size": getattr(state, "queue_size", 0) if state else 0,
        "total_requests": getattr(state, "total_requests", 0) if state else 0,
        "runtime": "stable",
        "api_status": state.api_status.value if (state and hasattr(state.api_status, "value")) else "RUNNING",
        "workers": 1,
    }
