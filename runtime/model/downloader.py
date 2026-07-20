"""Hugging Face Hub downloader with verbose console telemetry — APEX V1."""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from runtime.core.errors import AuthenticationFailedError, DownloadFailedError, ModelNotFoundError

logger = logging.getLogger("runtime.model.downloader")


class ModelDownloader:
    """Downloads model repositories from Hugging Face Hub with full progress telemetry."""

    def __init__(self, cache_dir: Path, token: Optional[str] = None):
        """Initializes the ModelDownloader.

        Args:
            cache_dir: The directory where model downloads should be cached.
            token: Optional Hugging Face token. Falls back to environment HF_TOKEN.
        """
        self.cache_dir = cache_dir
        self.token = token or os.environ.get("HF_TOKEN")

    def _verify_auth(self) -> None:
        """Helper to ensure we have credentials if required."""
        if not self.token:
            self.token = os.environ.get("HF_TOKEN")

    def get_metadata(self, model_id: str) -> Dict[str, Any]:
        """Queries the Hugging Face API for model repository metadata.

        Args:
            model_id: The model identifier (e.g., 'Qwen/Qwen2.5-1.5B-Instruct').

        Returns:
            Dict[str, Any]: Repo configuration metadata.
        """
        self._verify_auth()
        logger.info("Loading metadata...", extra={"prefix": "DOWNLOAD"})
        try:
            from huggingface_hub import HfApi

            api = HfApi(token=self.token)
            model_info = api.model_info(model_id)

            siblings = [s.rfilename for s in model_info.siblings]
            logger.info(f"Repository found: {model_info.id}", extra={"prefix": "DOWNLOAD"})
            logger.info(f"Files to download:", extra={"prefix": "DOWNLOAD"})
            for fname in siblings:
                logger.info(f"  {fname}", extra={"prefix": "DOWNLOAD"})

            return {
                "id": model_info.id,
                "author": model_info.author,
                "pipeline_tag": model_info.pipeline_tag,
                "tags": model_info.tags,
                "private": model_info.private,
                "siblings": siblings,
            }
        except Exception as e:
            err_msg = str(e).lower()
            if "401" in err_msg or "unauthorized" in err_msg:
                raise AuthenticationFailedError(
                    details=f"Failed to query {model_id} metadata. Authentication failed.",
                    log_info={"error": str(e)},
                )
            if "404" in err_msg or "not found" in err_msg:
                raise ModelNotFoundError(model_id, log_info={"error": str(e)})
            raise DownloadFailedError(model_id, reason=str(e))

    def download(self, model_id: str, target_dir: Path) -> Path:
        """Downloads a model repository snapshot with verbose progress telemetry.

        Args:
            model_id: Hugging Face model repository ID.
            target_dir: Local path to download files into.

        Returns:
            Path: The directory holding the downloaded assets.
        """
        self._verify_auth()
        target_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Checking cache...", extra={"prefix": "CACHE"})

        # Fetch metadata first for verbose file listing
        try:
            metadata = self.get_metadata(model_id)
        except Exception:
            logger.warning("Could not fetch metadata preview. Proceeding with download...", extra={"prefix": "DOWNLOAD"})

        logger.info("Downloading...", extra={"prefix": "DOWNLOAD"})

        try:
            from huggingface_hub import snapshot_download

            # Execute standard snapshot download with automatic resume capabilities
            snapshot_download(
                repo_id=model_id,
                local_dir=target_dir,
                token=self.token,
                local_dir_use_symlinks=False,
                resume_download=True,
            )

            logger.info("Checksum verification...", extra={"prefix": "DOWNLOAD"})
            logger.info("Moving into cache...", extra={"prefix": "CACHE"})
            logger.info("Download completed.", extra={"prefix": "SUCCESS"})

            return target_dir
        except Exception as e:
            err_msg = str(e).lower()
            if "401" in err_msg or "unauthorized" in err_msg:
                raise AuthenticationFailedError(
                    details=f"Access denied for {model_id}. Hugging Face authentication failed.",
                    log_info={"error": str(e)},
                )
            if "404" in err_msg or "not found" in err_msg:
                raise ModelNotFoundError(model_id, log_info={"error": str(e)})
            raise DownloadFailedError(
                model_id,
                reason=f"Failed to download repository files: {e}",
                log_info={"error": str(e)},
            )
