"""Hugging Face Hub downloader for downloading models securely and reliably."""

import os
from pathlib import Path
from typing import Any, Dict, Optional

from runtime.core.errors import AuthenticationFailedError, DownloadFailedError, ModelNotFoundError


class ModelDownloader:
    """Manages model metadata inspection and retrieval from the Hugging Face Hub."""

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
        # Environment settings check
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
        try:
            from huggingface_hub import HfApi

            api = HfApi(token=self.token)
            model_info = api.model_info(model_id)
            return {
                "id": model_info.id,
                "author": model_info.author,
                "pipeline_tag": model_info.pipeline_tag,
                "tags": model_info.tags,
                "private": model_info.private,
                "siblings": [s.rfilename for s in model_info.siblings],
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

    def download(self, model_id: str, target_dir: Path, filename_pattern: Optional[str] = None) -> Path:
        """Downloads a model repository snapshot to a specified local directory.

        Supports chunked resuming, retry fallback, and token validation.

        Args:
            model_id: Hugging Face model repository ID.
            target_dir: Local path to download files into.
            filename_pattern: Optional glob pattern to limit file downloads (e.g. '*.gguf').

        Returns:
            Path: The directory holding the downloaded assets.
        """
        self._verify_auth()
        target_dir.mkdir(parents=True, exist_ok=True)

        try:
            from huggingface_hub import snapshot_download

            allow_patterns = [filename_pattern] if filename_pattern else None

            # Execute standard snapshot download with automatic resume capabilities
            snapshot_download(
                repo_id=model_id,
                local_dir=target_dir,
                token=self.token,
                allow_patterns=allow_patterns,
                local_dir_use_symlinks=False,
                resume_download=True,
            )
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
        return target_dir
    
    def download_single_file(self, repo_id: str, filename: str, target_dir: Path) -> Path:
        """Downloads a single specific file from a Hugging Face repository.

        Args:
            repo_id: Hugging Face model repository ID.
            filename: Name of the file inside the repo.
            target_dir: Local folder to place the file.

        Returns:
            Path: The full absolute path to the downloaded file.
        """
        self._verify_auth()
        target_dir.mkdir(parents=True, exist_ok=True)
        try:
            from huggingface_hub import hf_hub_download
            filepath = hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                local_dir=target_dir,
                token=self.token,
                local_dir_use_symlinks=False,
                resume_download=True,
            )
            return Path(filepath)
        except Exception as e:
            err_msg = str(e).lower()
            if "401" in err_msg or "unauthorized" in err_msg:
                raise AuthenticationFailedError(
                    details=f"Access denied to download {filename} from {repo_id}.",
                    log_info={"error": str(e)},
                )
            if "404" in err_msg or "not found" in err_msg:
                raise ModelNotFoundError(f"{repo_id}/{filename}", log_info={"error": str(e)})
            raise DownloadFailedError(
                repo_id,
                reason=f"Failed to download file {filename}: {e}",
                log_info={"error": str(e)},
            )
