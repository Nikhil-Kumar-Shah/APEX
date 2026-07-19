"""Unit tests for workspace management, persistent memory, and repository indexing."""

import json
import pytest
from pathlib import Path

from runtime.memory import (
    ConversationNotFoundError,
    MemoryManager,
    SessionRestoreFailedError,
    WorkspaceNotFoundError,
)


@pytest.fixture
def memory_root(tmp_path: Path):
    """Fixture supplying temporary directory paths for testing memory storage."""
    storage_dir = tmp_path / "storage"
    cache_dir = tmp_path / "cache"
    storage_dir.mkdir()
    cache_dir.mkdir()
    return storage_dir, cache_dir


def test_workspace_management(memory_root):
    """Tests workspace creation, listing, switching, and manifests validation."""
    storage, cache = memory_root
    mgr = MemoryManager(storage, cache)

    # By default, should load 'default' workspace
    assert mgr.workspace_mgr.active_workspace_id == "default"
    assert mgr.workspace_mgr.active_workspace_path.exists()

    # Create workspace
    mgr.workspace_mgr.create_workspace("project-alpha", "Project Alpha Workspace")
    workspaces = mgr.workspace_mgr.list_workspaces()
    assert len(workspaces) == 2
    
    # Switch
    mgr.switch_workspace("project-alpha")
    assert mgr.workspace_mgr.active_workspace_id == "project-alpha"
    assert mgr.convo_mgr.workspace_path == mgr.workspace_mgr.active_workspace_path

    # Try loading invalid workspace
    with pytest.raises(WorkspaceNotFoundError):
        mgr.switch_workspace("nonexistent")


def test_conversation_memory(memory_root):
    """Tests saving, appending messages to, listing, and deleting conversations."""
    storage, cache = memory_root
    mgr = MemoryManager(storage, cache)

    # Create conversation
    convo = mgr.convo_mgr.create_conversation("Initial Chat")
    convo_id = convo["conversation_id"]

    assert convo["title"] == "Initial Chat"
    assert len(mgr.convo_mgr.list_conversations()) == 1

    # Append messages
    mgr.convo_mgr.append_message(convo_id, "user", "What is code?")
    mgr.convo_mgr.append_message(convo_id, "assistant", "Code is instructions.")

    # Reload
    reloaded = mgr.convo_mgr.load_conversation(convo_id)
    assert len(reloaded["messages"]) == 2
    assert reloaded["messages"][0]["role"] == "user"

    # Export text
    txt_export = mgr.convo_mgr.export_conversation(convo_id, format_type="txt")
    assert "Title: Initial Chat" in txt_export
    assert "USER: What is code?" in txt_export

    # Delete
    assert mgr.convo_mgr.delete_conversation(convo_id)
    with pytest.raises(ConversationNotFoundError):
        mgr.convo_mgr.load_conversation(convo_id)


def test_project_memory(memory_root):
    """Tests saving and listing project state files."""
    storage, cache = memory_root
    mgr = MemoryManager(storage, cache)

    state = {
        "active_model_id": "gpt-mock",
        "active_engine": "mock",
    }
    preferences = {"temperature": 0.2}

    mgr.project_mem.save_project("test-project", "Test Project", state, preferences)
    
    # Load
    project = mgr.project_mem.load_project("test-project")
    assert project is not None
    assert project["name"] == "Test Project"
    assert project["state"]["active_model_id"] == "gpt-mock"
    assert len(project["history"]) == 1

    # List
    projects = mgr.project_mem.list_projects()
    assert len(projects) == 1
    assert projects[0]["project_id"] == "test-project"


def test_repository_indexer(memory_root, tmp_path: Path):
    """Tests repository scanning, suffix detection, and AST symbol extraction."""
    storage, cache = memory_root
    mgr = MemoryManager(storage, cache)

    # Setup dummy codebase folder
    code_dir = tmp_path / "my_project"
    code_dir.mkdir()
    
    python_file = code_dir / "utils.py"
    python_file.write_text(
        "import os\n\n"
        "class Helper:\n"
        "    pass\n\n"
        "def run_helper():\n"
        "    pass\n",
        encoding="utf-8"
    )

    other_file = code_dir / "styles.css"
    other_file.write_text("body { color: red; }", encoding="utf-8")

    # Index
    index = mgr.repo_indexer.index_repository("my_repo", code_dir)
    assert index["total_files"] == 2
    assert "utils.py" in index["files"]
    
    # Check symbol parsing details
    utils_index = index["files"]["utils.py"]
    assert utils_index["language"] == "Python"
    assert "Helper" in utils_index["symbols"]["classes"]
    assert "run_helper" in utils_index["symbols"]["functions"]
    assert "os" in utils_index["symbols"]["imports"]

    assert index["files"]["styles.css"]["language"] == "Unknown"


def test_session_restoration(memory_root):
    """Tests session backup persistence and automatic restoration."""
    storage, cache = memory_root
    mgr = MemoryManager(storage, cache)

    # Save session
    mgr.save_session_state(active_model_id="mock-7b", active_project_id="test-p")
    assert storage / "session.json"

    # Instantiate new manager and restore
    new_mgr = MemoryManager(storage, cache)
    restored = new_mgr.restore_session_state()
    assert restored["active_model_id"] == "mock-7b"
    assert restored["active_project_id"] == "test-p"


def test_backup_and_restore(memory_root, tmp_path: Path):
    """Tests workspace folder zip backups and extraction recoveries."""
    storage, cache = memory_root
    mgr = MemoryManager(storage, cache)

    # Write a conversation in default workspace
    convo = mgr.convo_mgr.create_conversation("Backup Convo")
    convo_id = convo["conversation_id"]

    # Backup default workspace
    backup_folder = tmp_path / "backups"
    zip_path = mgr.backup_workspace("default", backup_folder)
    assert zip_path.is_file()

    # Delete conversation
    mgr.convo_mgr.delete_conversation(convo_id)
    assert len(mgr.convo_mgr.list_conversations()) == 0

    # Restore from backup
    mgr.restore_workspace_from_backup("default", zip_path)
    
    # Verify conversation is back
    assert len(mgr.convo_mgr.list_conversations()) == 1
    assert mgr.convo_mgr.list_conversations()[0]["conversation_id"] == convo_id


def test_memory_cleanup(memory_root):
    """Tests temporary file purges and old conversations pruning."""
    storage, cache = memory_root
    mgr = MemoryManager(storage, cache)

    # Write temp files
    temp_file = storage / "workspaces" / "default" / "conversations" / "temp.tmp"
    temp_file.write_text("temporary", encoding="utf-8")
    assert temp_file.is_file()

    # Purge
    deleted = mgr.cleanup_mgr.purge_temp_files(storage / "workspaces" / "default")
    assert deleted == 1
    assert not temp_file.exists()
