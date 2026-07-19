"""Performance metrics logger and benchmark analytics."""

import time
from typing import Any, Dict, List


class BenchmarkTracker:
    """Logs generation speeds, memory consumption, loading durations, and compares stats."""

    def __init__(self):
        self.runs: List[Dict[str, Any]] = []

    def record_run(
        self,
        model_id: str,
        engine: str,
        load_time: float,
        ttft: float,
        tokens_count: int,
        generation_time: float,
        vram_allocated_mb: float = 0.0,
    ) -> Dict[str, Any]:
        """Appends a new performance execution record.

        Args:
            model_id: Name/ID of the model.
            engine: Inference engine.
            load_time: Time taken to load the model (seconds).
            ttft: Time to first token (seconds).
            tokens_count: Number of generated tokens.
            generation_time: Elapsed time for token generation (seconds).
            vram_allocated_mb: GPU VRAM allocated.

        Returns:
            Dict[str, Any]: Compiled run stats.
        """
        tokens_per_second = tokens_count / generation_time if generation_time > 0 else 0.0
        total_latency = ttft + generation_time

        run = {
            "timestamp": time.time(),
            "model_id": model_id,
            "engine": engine,
            "load_time_sec": load_time,
            "ttft_sec": ttft,
            "tokens_count": tokens_count,
            "tokens_per_second": tokens_per_second,
            "generation_time_sec": generation_time,
            "total_latency_sec": total_latency,
            "vram_allocated_mb": vram_allocated_mb,
        }
        self.runs.append(run)
        return run

    def get_summary(self) -> Dict[str, Any]:
        """Averages execution values over all runs for diagnostics.

        Returns:
            Dict[str, Any]: Averages of tokens/sec, loading, and TTFT.
        """
        if not self.runs:
            return {
                "total_runs": 0,
                "average_tokens_per_second": 0.0,
                "average_ttft_sec": 0.0,
                "average_load_time_sec": 0.0,
            }

        total_runs = len(self.runs)
        avg_tokens_per_sec = sum(r["tokens_per_second"] for r in self.runs) / total_runs
        avg_ttft = sum(r["ttft_sec"] for r in self.runs) / total_runs
        avg_load = sum(r["load_time_sec"] for r in self.runs) / total_runs

        return {
            "total_runs": total_runs,
            "average_tokens_per_second": avg_tokens_per_sec,
            "average_ttft_sec": avg_ttft,
            "average_load_time_sec": avg_load,
            "runs": self.runs,
        }

    def clear(self) -> None:
        """Clears benchmark statistics."""
        self.runs.clear()
