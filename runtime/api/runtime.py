"""Runtime status API for APEX Runtime with verified metrics."""

import platform
from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/runtime")
async def runtime_status(req: Request = None):
    """Runtime status endpoint reporting real engine, device, and telemetry."""
    mm = getattr(req.app.state, "model_manager", None) if req else None
    state = getattr(req.app.state, "runtime_state", None) if req else None

    active_model = getattr(mm, "active_model_id", None) if mm else getattr(state, "model_loaded", None)
    active_engine = getattr(mm, "active_engine", None) if mm else None

    device = "cpu"
    vram_str = "0GB"
    engine_name = "transformers"

    if active_engine:
        device = getattr(active_engine, "device", "cpu")
        engine_name = getattr(active_engine, "config", {}).get("engine", "transformers")

    try:
        import torch
        if torch.cuda.is_available():
            alloc = torch.cuda.memory_allocated(0) / (1024**3)
            total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            vram_str = f"{alloc:.1f}/{total:.1f}GB"
            if not device or device == "cpu":
                device = "cuda:0"
    except Exception:
        pass

    ram_str = "unavailable"
    try:
        import psutil
        vm = psutil.virtual_memory()
        ram_str = f"{vm.used / (1024**3):.1f}/{vm.total / (1024**3):.1f}GB"
    except Exception:
        pass

    return {
        "loaded_model": active_model or "none",
        "vram": vram_str,
        "cpu": platform.processor() or "standard",
        "ram": ram_str,
        "tokenizer": "active" if (active_engine and getattr(active_engine, "tokenizer", None)) else "none",
        "engine": engine_name,
        "device": device,
        "precision": getattr(active_engine, "config", {}).get("precision", "float16") if active_engine else "float16",
        "queue": getattr(state, "queue_size", 0) if state else 0,
        "transport": getattr(state, "transport", "http") if hasattr(state, "transport") else "http",
        "api_version": "v1",
    }
