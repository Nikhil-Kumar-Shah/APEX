"""Health and system metrics monitoring for the runtime."""

import os
import shutil
import time
from pathlib import Path
from typing import Any, Dict, Optional

# Track start time for uptime calculations
START_TIME = time.time()


class HealthMonitor:
    """Monitors system resources, GPU availability, and model memory overhead."""

    def __init__(self, cache_dir: Path, model_manager: Optional[Any] = None):
        """Initializes the HealthMonitor.

        Args:
            cache_dir: The local model cache directory.
            model_manager: Reference to the active ModelManager instance.
        """
        self.cache_dir = cache_dir
        self.model_manager = model_manager

    def get_uptime_seconds(self) -> float:
        """Calculates system runtime uptime in seconds.

        Returns:
            float: Elapsed seconds.
        """
        return time.time() - START_TIME

    def get_disk_status(self) -> Dict[str, float]:
        """Retrieves disk space usage metrics for the cache volume.

        Returns:
            Dict[str, float]: Total, used, and free space in Gigabytes.
        """
        try:
            total, used, free = shutil.disk_usage(self.cache_dir)
            return {
                "total_gb": total / (1024**3),
                "used_gb": used / (1024**3),
                "free_gb": free / (1024**3),
            }
        except OSError:
            return {"total_gb": 0.0, "used_gb": 0.0, "free_gb": 0.0}

    def get_ram_status(self) -> Dict[str, float]:
        """Calculates system random-access memory (RAM) allocation.

        Returns:
            Dict[str, float]: Total and available RAM in Gigabytes.
        """
        # Dynamic check if psutil is available
        try:
            import psutil

            virtual_mem = psutil.virtual_memory()
            return {
                "total_gb": virtual_mem.total / (1024**3),
                "available_gb": virtual_mem.available / (1024**3),
                "percent_used": virtual_mem.percent,
            }
        except ImportError:
            # Fallback if psutil is absent
            # Linux-based Colab environment check
            if os.path.exists("/proc/meminfo"):
                try:
                    with open("/proc/meminfo", "r") as f:
                        lines = f.readlines()
                    mem_info = {}
                    for line in lines:
                        parts = line.split(":")
                        if len(parts) == 2:
                            mem_info[parts[0].strip()] = int(parts[1].replace("kB", "").strip())
                    total = mem_info.get("MemTotal", 0) * 1024
                    free = mem_info.get("MemAvailable", 0) * 1024
                    return {
                        "total_gb": total / (1024**3),
                        "available_gb": free / (1024**3),
                        "percent_used": ((total - free) / total) * 100 if total > 0 else 0.0,
                    }
                except Exception:
                    pass
            return {"total_gb": 0.0, "available_gb": 0.0, "percent_used": 0.0}

    def get_gpu_status(self) -> Dict[str, Any]:
        """Detects presence and memory metrics of active CUDA GPUs.

        Returns:
            Dict[str, Any]: GPU details.
        """
        gpu_info = {"available": False, "device_name": None, "vram_allocated_mb": 0.0, "vram_reserved_mb": 0.0}
        try:
            import torch

            gpu_info["available"] = torch.cuda.is_available()
            if gpu_info["available"]:
                gpu_info["device_name"] = torch.cuda.get_device_name(0)
                gpu_info["vram_allocated_mb"] = torch.cuda.memory_allocated(0) / (1024 * 1024)
                gpu_info["vram_reserved_mb"] = torch.cuda.memory_reserved(0) / (1024 * 1024)
        except ImportError:
            pass
        return gpu_info

    def generate_report(self) -> Dict[str, Any]:
        """Generates a complete status and diagnostic report.

        Returns:
            Dict[str, Any]: Uptime, disk, RAM, GPU, and engine metrics.
        """
        report = {
            "uptime_seconds": self.get_uptime_seconds(),
            "disk": self.get_disk_status(),
            "ram": self.get_ram_status(),
            "gpu": self.get_gpu_status(),
            "model_manager": {
                "active_model_id": None,
                "is_loaded": False,
                "cache_size_gb": 0.0,
            },
        }

        if self.model_manager:
            report["model_manager"] = self.model_manager.get_status()

        return report
