"""Metrics and logging for APEX API."""

import time
import logging

logger = logging.getLogger("apex.metrics")

def log_request_metrics(
    request_id: str, 
    start_time: float,
    prompt_tokens: int = 0,
    generated_tokens: int = 0,
    gpu_usage: float = 0.0,
    vram_usage: float = 0.0,
):
    latency = time.time() - start_time
    logger.info(
        f"Metrics [{request_id}]: Latency={latency:.3f}s | "
        f"Prompt Tokens={prompt_tokens} | Generated Tokens={generated_tokens} | "
        f"GPU Usage={gpu_usage}% | VRAM={vram_usage}MB"
    )
