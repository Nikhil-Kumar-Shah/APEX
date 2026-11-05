"""Environment, Hardware, Git, and Codebase diagnostics."""

import os
import sys
import shutil
import platform
import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("bootstrap.diagnostics")


class DiagnosticsManager:
    """Runs repository self-diagnostics, hardware checks, and version reporting."""

    def __init__(self, target_dir: Path):
        self.target_dir = target_dir

    def run_diagnostics(self) -> Dict[str, Any]:
        """Executes all diagnostic checks.

        Returns:
            Dict[str, Any]: Comprehensive diagnostic report.
        """
        logger.info("Running APEX Environment & Hardware Diagnostics...", extra={"prefix": "SYSTEM"})
        
        system_info = self._report_system_environment()
        storage_info = self._report_memory_and_storage()
        gpu_info = self._report_hardware_accelerator()
        git_info = self._report_git_status()
        dep_info = self._report_dependencies()
        self._check_legacy_patterns()
        
        return {
            "system": system_info,
            "storage": storage_info,
            "gpu": gpu_info,
            "git": git_info,
            "dependencies": dep_info,
        }

    def _report_system_environment(self) -> Dict[str, Any]:
        """Logs Python, OS, platform, and Colab environment status."""
        is_colab = "google.colab" in sys.modules
        info = {
            "python_version": sys.version.split()[0],
            "os_name": platform.system(),
            "os_release": platform.release(),
            "architecture": platform.machine(),
            "is_colab": is_colab,
        }
        logger.info(f"Python Version: {info['python_version']}", extra={"prefix": "SYSTEM"})
        logger.info(f"Platform      : {info['os_name']} {info['os_release']} ({info['architecture']})", extra={"prefix": "SYSTEM"})
        logger.info(f"Google Colab  : {'Yes' if is_colab else 'No'}", extra={"prefix": "SYSTEM"})
        return info

    def _report_memory_and_storage(self) -> Dict[str, Any]:
        """Logs RAM and Disk space metrics."""
        disk_total, disk_used, disk_free = 0.0, 0.0, 0.0
        try:
            total_b, used_b, free_b = shutil.disk_usage(self.target_dir)
            disk_total = total_b / (1024**3)
            disk_used = used_b / (1024**3)
            disk_free = free_b / (1024**3)
        except OSError:
            pass

        ram_total, ram_avail = 0.0, 0.0
        try:
            import psutil
            vm = psutil.virtual_memory()
            ram_total = vm.total / (1024**3)
            ram_avail = vm.available / (1024**3)
        except ImportError:
            if os.path.exists("/proc/meminfo"):
                try:
                    with open("/proc/meminfo", "r") as f:
                        for line in f:
                            if line.startswith("MemTotal:"):
                                ram_total = int(line.split()[1]) * 1024 / (1024**3)
                            elif line.startswith("MemAvailable:"):
                                ram_avail = int(line.split()[1]) * 1024 / (1024**3)
                except Exception:
                    pass

        logger.info(f"Disk Storage  : {disk_free:.1f} GB free / {disk_total:.1f} GB total", extra={"prefix": "SYSTEM"})
        if ram_total > 0:
            logger.info(f"System RAM    : {ram_avail:.1f} GB available / {ram_total:.1f} GB total", extra={"prefix": "SYSTEM"})

        return {
            "disk_free_gb": disk_free,
            "disk_total_gb": disk_total,
            "ram_available_gb": ram_avail,
            "ram_total_gb": ram_total,
        }

    def _report_hardware_accelerator(self) -> Dict[str, Any]:
        """Inspects and logs PyTorch and CUDA GPU availability dynamically."""
        gpu_data = {
            "torch_installed": False,
            "cuda_available": False,
            "device_name": None,
            "device_count": 0,
            "vram_total_gb": 0.0,
            "cuda_version": None,
        }
        try:
            import torch
            gpu_data["torch_installed"] = True
            gpu_data["cuda_available"] = torch.cuda.is_available()
            gpu_data["cuda_version"] = getattr(torch.version, "cuda", None)

            if gpu_data["cuda_available"]:
                count = torch.cuda.device_count()
                gpu_data["device_count"] = count
                props = torch.cuda.get_device_properties(0)
                gpu_data["device_name"] = props.name
                gpu_data["vram_total_gb"] = props.total_memory / (1024**3)
                logger.info(f"GPU Accelerator: {props.name} ({gpu_data['vram_total_gb']:.1f} GB VRAM)", extra={"prefix": "GPU"})
                logger.info(f"CUDA Runtime   : v{gpu_data['cuda_version']}", extra={"prefix": "GPU"})
            else:
                logger.warning("No CUDA device detected. Runtime running in CPU mode.", extra={"prefix": "GPU"})
        except ImportError:
            logger.warning("PyTorch not installed. Hardware acceleration unavailable.", extra={"prefix": "GPU"})
        except Exception as e:
            logger.warning(f"GPU detection error: {e}", extra={"prefix": "GPU"})

        return gpu_data

    def _report_dependencies(self) -> Dict[str, str]:
        """Checks and reports versions of core runtime dependencies."""
        deps = [
            "fastapi", "uvicorn", "pydantic", "huggingface_hub",
            "colorama", "torch", "transformers", "requests", "httpx"
        ]
        results = {}
        for dep in deps:
            try:
                import importlib.metadata
                ver = importlib.metadata.version(dep)
                results[dep] = ver
            except Exception:
                results[dep] = "not installed"
        logger.info(f"Core Packages : {', '.join(f'{k}=={v}' for k, v in results.items() if v != 'not installed')}", extra={"prefix": "SYSTEM"})
        return results

    def _report_git_status(self) -> Dict[str, Any]:
        """Logs current branch, commit, and tags."""
        git_info = {"branch": "unknown", "commit": "unknown", "tags": []}
        try:
            branch = subprocess.run(
                ["git", "-C", str(self.target_dir), "branch", "--show-current"], 
                capture_output=True, text=True, timeout=5
            ).stdout.strip()
            
            commit = subprocess.run(
                ["git", "-C", str(self.target_dir), "rev-parse", "HEAD"], 
                capture_output=True, text=True, timeout=5
            ).stdout.strip()
            
            tags = subprocess.run(
                ["git", "-C", str(self.target_dir), "tag"], 
                capture_output=True, text=True, timeout=5
            ).stdout.strip().split()
            
            git_info["branch"] = branch
            git_info["commit"] = commit[:8] if commit else "unknown"
            git_info["tags"] = tags

            logger.info(f"Repository Path: {self.target_dir.resolve()}", extra={"prefix": "SYSTEM"})
            logger.info(f"Current Branch : {branch}", extra={"prefix": "SYSTEM"})
            logger.info(f"Current Commit : {git_info['commit']}", extra={"prefix": "SYSTEM"})
            logger.info(f"Git Tags       : {tags if tags else 'None'}", extra={"prefix": "SYSTEM"})
        except Exception as e:
            logger.warning(f"Git Diagnostics failed: {e}", extra={"prefix": "WARNING"})
        return git_info

    def _check_legacy_patterns(self) -> None:
        """Scans codebase for old architecture patterns."""
        legacy_detected = False
        try:
            for p in self.target_dir.rglob("*"):
                if p.is_file() and p.suffix in [".py", ".md", ".json"] and ".git" not in p.parts and "__pycache__" not in p.parts:
                    try:
                        content = p.read_text(encoding="utf-8")
                        if "v1.0.0" in content and "version_manager.py" in p.name:
                            logger.warning(f"Found legacy tag ref 'v1.0.0' in: {p.relative_to(self.target_dir)}", extra={"prefix": "WARNING"})
                            legacy_detected = True
                        if "configs" in content and "repository_manager.py" in p.name:
                            logger.warning(f"Found legacy hardcoded folder 'configs' in: {p.relative_to(self.target_dir)}", extra={"prefix": "WARNING"})
                            legacy_detected = True
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"Self-diagnostics scan failed: {e}", extra={"prefix": "WARNING"})
            
        if not legacy_detected:
            logger.info("Self-diagnostics completed. No active legacy patterns found.", extra={"prefix": "SUCCESS"})
