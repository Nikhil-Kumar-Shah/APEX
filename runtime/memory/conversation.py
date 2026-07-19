"""Persistent conversation history memory manager."""

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from runtime.utils.file import safe_read_json, safe_write_json
from runtime.memory.errors import ConversationNotFoundError


class ConversationMemoryManager:
    """Manages reading, writing, exporting, and purging chat logs."""

    def __init__(self, workspace_path: Path):
        """Initializes the ConversationMemoryManager.

        Args:
            workspace_path: Path of the active workspace.
        """
        self.workspace_path = workspace_path

    @property
    def conversations_dir(self) -> Path:
        """Gets the path of the conversations subdirectory."""
        path = self.workspace_path / "conversations"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _get_file_path(self, conversation_id: str) -> Path:
        return self.conversations_dir / f"{conversation_id}.json"

    def create_conversation(self, title: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Creates and persists a new conversation thread.

        Args:
            title: Human friendly conversation name.
            session_id: Active connection session mapping.

        Returns:
            Dict[str, Any]: Newly initialized conversation dictionary.
        """
        import uuid

        conversation_id = str(uuid.uuid4())
        convo = {
            "conversation_id": conversation_id,
            "title": title,
            "session_id": session_id,
            "created_at": time.time(),
            "updated_at": time.time(),
            "summary": "",
            "messages": [],
        }
        self.save_conversation(conversation_id, convo)
        return convo

    def load_conversation(self, conversation_id: str) -> Dict[str, Any]:
        """Loads a conversation from storage.

        Args:
            conversation_id: Unique identifier.

        Returns:
            Dict[str, Any]: Chat history dictionary.
        """
        filepath = self._get_file_path(conversation_id)
        data = safe_read_json(filepath)
        if not data:
            raise ConversationNotFoundError(conversation_id)
        return data

    def save_conversation(self, conversation_id: str, data: Dict[str, Any]) -> None:
        """Saves a conversation to file.

        Args:
            conversation_id: Unique identifier.
            data: Conversation state payload.
        """
        filepath = self._get_file_path(conversation_id)
        data["updated_at"] = time.time()
        success = safe_write_json(filepath, data)
        if not success:
            raise OSError(f"Could not persist conversation {conversation_id}.")

    def append_message(self, conversation_id: str, role: str, content: str) -> None:
        """Appends a single message to a conversation log.

        Args:
            conversation_id: Unique identifier.
            role: Message sender role ('user', 'assistant').
            content: Message string content.
        """
        convo = self.load_conversation(conversation_id)
        convo["messages"].append(
            {
                "role": role,
                "content": content,
                "timestamp": time.time(),
            }
        )
        self.save_conversation(conversation_id, convo)

    def delete_conversation(self, conversation_id: str) -> bool:
        """Deletes a conversation history file.

        Args:
            conversation_id: Unique identifier.

        Returns:
            bool: True if deleted successfully.
        """
        filepath = self._get_file_path(conversation_id)
        if filepath.is_file():
            filepath.unlink()
            return True
        return False

    def list_conversations(self) -> List[Dict[str, Any]]:
        """Lists metadata summaries for all stored conversations.

        Returns:
            List[Dict[str, Any]]: Conversation summary profiles.
        """
        convos = []
        if not self.conversations_dir.exists():
            return convos

        for child in self.conversations_dir.glob("*.json"):
            data = safe_read_json(child)
            if data:
                convos.append(
                    {
                        "conversation_id": data["conversation_id"],
                        "title": data["title"],
                        "created_at": data["created_at"],
                        "updated_at": data["updated_at"],
                        "message_count": len(data["messages"]),
                        "summary": data.get("summary", ""),
                    }
                )
        return convos

    def export_conversation(self, conversation_id: str, format_type: str = "json") -> str:
        """Exports conversation history to a structured format (JSON or Text).

        Args:
            conversation_id: Unique identifier.
            format_type: Output format ('json' or 'txt').

        Returns:
            str: Serialized conversation string.
        """
        convo = self.load_conversation(conversation_id)
        if format_type.lower() == "json":
            import json
            return json.dumps(convo, indent=4)
        
        # Format as readable script text
        lines = []
        lines.append(f"Title: {convo['title']}")
        lines.append(f"ID: {convo['conversation_id']}")
        lines.append("-" * 40)
        for msg in convo["messages"]:
            role = msg["role"].upper()
            content = msg["content"]
            lines.append(f"{role}: {content}\n")
        return "\n".join(lines)
