"""Memory and workspace error definitions."""

from runtime.core.errors import RuntimeErrorBase


class WorkspaceNotFoundError(RuntimeErrorBase):
    """Raised when the specified workspace directory cannot be found."""

    def __init__(self, workspace_name: str):
        super().__init__(
            message=f"Workspace not found: '{workspace_name}'",
            cause="The specified workspace path is missing, unmounted, or was deleted.",
            recovery="Verify that Google Drive is mounted, check workspace spelling, or initialize a new workspace.",
        )


class ConversationNotFoundError(RuntimeErrorBase):
    """Raised when a specific conversation ID cannot be resolved."""

    def __init__(self, conversation_id: str):
        super().__init__(
            message=f"Conversation not found: '{conversation_id}'",
            cause="The requested conversation JSON file does not exist in the active workspace memory folder.",
            recovery="Check conversation list for valid IDs, or create a new conversation thread.",
        )


class RepositoryUnavailableError(RuntimeErrorBase):
    """Raised when repository scanning fails."""

    def __init__(self, repo_path: str, details: str = ""):
        super().__init__(
            message=f"Repository at '{repo_path}' is unavailable: {details}",
            cause="Folder permissions, structural changes, or lock files are preventing directory reads.",
            recovery="Ensure path is writeable and directory exists.",
        )


class ConfigurationMismatchError(RuntimeErrorBase):
    """Raised when config structures fail compatibility tests."""

    def __init__(self, details: str = ""):
        super().__init__(
            message="Configuration mismatch detected.",
            cause=f"The imported configuration parameters are incompatible with the current environment: {details}",
            recovery="Double check source/target versions and check config schemas.",
        )


class MemoryVersionMismatchError(RuntimeErrorBase):
    """Raised when storage versions do not match."""

    def __init__(self, current_ver: str, target_ver: str):
        super().__init__(
            message=f"Memory storage version mismatch: runtime expects '{target_ver}', storage is '{current_ver}'",
            cause="The persistent files are from a different version of the runtime and need migration.",
            recovery="Execute the import/migration script to upgrade storage configurations.",
        )


class StorageUnavailableError(RuntimeErrorBase):
    """Raised when Google Drive or local storage media is unmounted."""

    def __init__(self, target: str):
        super().__init__(
            message=f"Storage medium unavailable: '{target}'",
            cause="The storage drive was disconnected or permission access was revoked.",
            recovery="Mount Google Drive or re-authenticate connection.",
        )


class ImportFailedError(RuntimeErrorBase):
    """Raised when importing configurations fails."""

    def __init__(self, source: str, reason: str):
        super().__init__(
            message=f"Import failed from source: '{source}'",
            cause=f"Corruption or parsing issues in import files: {reason}",
            recovery="Ensure the imported file is a valid JSON configuration exported from this runtime.",
        )


class ExportFailedError(RuntimeErrorBase):
    """Raised when exporting configurations fails."""

    def __init__(self, target: str, reason: str):
        super().__init__(
            message=f"Export failed to destination: '{target}'",
            cause=f"File system access limits or space exhaustion: {reason}",
            recovery="Check that the destination path is writable and retry.",
        )


class SessionRestoreFailedError(RuntimeErrorBase):
    """Raised when session restoration fails."""

    def __init__(self, session_id: str, reason: str):
        super().__init__(
            message=f"Failed to restore session: '{session_id}'",
            cause=f"The session backup file was corrupted or refers to missing models/projects: {reason}",
            recovery="Start a clean session or restore from a different backup.",
        )
