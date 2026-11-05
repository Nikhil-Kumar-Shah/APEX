"""Interactive Chat Interface widget for Google Colab and JupyterLab notebooks."""

import logging
from typing import Any, Dict, List, Optional
from pathlib import Path

logger = logging.getLogger("runtime.ui.chat")


class ChatUI:
    """Notebook-embedded conversational AI interface."""

    def __init__(self, api_manager: Optional[Any] = None, model_manager: Optional[Any] = None):
        self.api_manager = api_manager
        self.model_manager = model_manager
        self.messages: List[Dict[str, str]] = []
        self.is_generating = False
        self.widget_container: Optional[Any] = None

    def render(self) -> Any:
        """Renders the chat interface within the notebook cell."""
        try:
            import ipywidgets as widgets
            from IPython.display import HTML, display
        except ImportError:
            print("ChatUI: ipywidgets not available. Use the web interface at the public URL.")
            return "Headless ChatUI Instance"

        # Web interface launch card
        pub_url = self.api_manager.state.public_url if self.api_manager and self.api_manager.state else "http://127.0.0.1:8000"
        chat_url = f"{pub_url}/chat" if pub_url else "/chat"

        model_name = "APEX Model"
        if self.model_manager and hasattr(self.model_manager, "active_model_id") and self.model_manager.active_model_id:
            model_name = self.model_manager.active_model_id.split("/")[-1]

        header_html = widgets.HTML(f"""
        <div style="background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center;">
            <div>
                <b style="color: #58a6ff; font-size: 14px;">🌌 APEX Chat Assistant</b>
                <span style="background: #21262d; border: 1px solid #30363d; padding: 2px 8px; border-radius: 10px; font-size: 11px; margin-left: 8px; color: #c9d1d9;">Model: {model_name}</span>
            </div>
            <div>
                <a href="{chat_url}" target="_blank" style="background: #238636; color: white; padding: 6px 12px; border-radius: 6px; text-decoration: none; font-size: 12px; font-weight: bold;">
                    Open Web Chat ↗
                </a>
            </div>
        </div>
        """)

        messages_box = widgets.Output(
            layout=widgets.Layout(
                height="320px",
                overflow_y="auto",
                background_color="#0d1117",
                border="1px solid #30363d",
                border_radius="6px",
                padding="12px",
                margin="0 0 10px 0",
            )
        )

        input_text = widgets.Textarea(
            placeholder="Type your message here... (Click Send)",
            layout=widgets.Layout(flex="1", height="44px"),
        )

        send_btn = widgets.Button(
            description="Send",
            button_style="success",
            icon="paper-plane",
            layout=widgets.Layout(width="90px", height="44px"),
        )

        clear_btn = widgets.Button(
            description="Clear",
            button_style="",
            icon="trash",
            layout=widgets.Layout(width="80px", height="44px"),
        )

        file_upload = widgets.FileUpload(
            accept=".txt,.csv,.json,.pdf,.docx",
            multiple=False,
            description="Attach",
            layout=widgets.Layout(width="90px", height="44px"),
        )

        status_label = widgets.HTML(value="")

        def _redraw_messages():
            with messages_box:
                messages_box.clear_output()
                if not self.messages:
                    display(HTML("<div style='color: #8b949e; font-size: 13px; text-align: center; margin-top: 130px;'>No messages yet. Send a prompt to start chatting.</div>"))
                    return

                for m in self.messages:
                    role = m["role"]
                    content = m["content"]
                    if role == "user":
                        display(HTML(f"""
                        <div style="display: flex; justify-content: flex-end; margin-bottom: 8px;">
                            <div style="background: #1f2937; border: 1px solid #374151; color: #f3f4f6; padding: 8px 12px; border-radius: 8px; max-width: 80%; font-size: 13px;">
                                <div style="font-size: 10px; color: #9ca3af; margin-bottom: 2px;">YOU</div>
                                {content}
                            </div>
                        </div>
                        """))
                    else:
                        display(HTML(f"""
                        <div style="display: flex; justify-content: flex-start; margin-bottom: 8px;">
                            <div style="background: #161b22; border: 1px solid #30363d; color: #c9d1d9; padding: 8px 12px; border-radius: 8px; max-width: 85%; font-size: 13px;">
                                <div style="font-size: 10px; color: #58a6ff; font-weight: bold; margin-bottom: 2px;">APEX ASSISTANT</div>
                                {content}
                            </div>
                        </div>
                        """))

        def _on_clear_click(_):
            self.messages = []
            _redraw_messages()

        def _on_send_click(_):
            user_text = input_text.value.strip()
            if not user_text and not file_upload.value:
                return

            attached_text = ""
            if file_upload.value:
                try:
                    uploaded = file_upload.value
                    # Extract text content if possible
                    file_item = list(uploaded.values())[0] if isinstance(uploaded, dict) else uploaded[0]
                    content_bytes = file_item.get("content", b"")
                    filename = file_item.get("name", "attachment")
                    try:
                        decoded = content_bytes.decode("utf-8", errors="ignore")
                        attached_text = f"\n[Attached: {filename}]\n{decoded[:4000]}\n"
                    except Exception:
                        pass
                except Exception:
                    pass

            full_prompt = (attached_text + user_text) if attached_text else user_text
            self.messages.append({"role": "user", "content": user_text or "[Attached File]"})
            input_text.value = ""
            _redraw_messages()

            send_btn.disabled = True
            status_label.value = "<span style='color: #58a6ff; font-size: 12px;'>Generating response...</span>"

            # Execute model generation
            active_engine = getattr(self.model_manager, "active_engine", None) if self.model_manager else None
            response_text = ""
            if active_engine and getattr(active_engine, "is_loaded", False):
                try:
                    for token in active_engine.generate_stream(self.messages, {"max_new_tokens": 512, "temperature": 0.7}):
                        response_text += token
                except Exception as err:
                    response_text = f"Error generating response: {err}"
            else:
                response_text = "No model is currently loaded in the APEX runtime. Start a model from the Launchpad."

            self.messages.append({"role": "assistant", "content": response_text})
            _redraw_messages()
            send_btn.disabled = False
            status_label.value = ""

        send_btn.on_click(_on_send_click)
        clear_btn.on_click(_on_clear_click)

        composer_row = widgets.HBox([file_upload, input_text, send_btn, clear_btn])

        container = widgets.VBox(
            [header_html, messages_box, composer_row, status_label],
            layout=widgets.Layout(
                background_color="#0d1117",
                border="1px solid #30363d",
                border_radius="10px",
                padding="14px",
                max_width="850px",
            ),
        )

        self.widget_container = container
        display(container)
        _redraw_messages()
        return container

