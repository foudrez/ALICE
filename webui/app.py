import gradio as gr
import asyncio
import sys
import os

# Allow imports from ALICE root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.event_bus import EventBus

class AliceDashboard:
    def __init__(self, bus: EventBus, main_loop: asyncio.AbstractEventLoop):
        self.bus = bus
        self.main_loop = main_loop
        self.chat_history = []

        # Hook into bus to update UI chat
        self.bus.subscribe("USER_SPOKE", self._add_user_msg)
        self.bus.subscribe("SENTENCE_READY_FOR_TTS", self._add_ai_msg)

    async def _add_user_msg(self, msg: str):
        # UPDATED: New Gradio Dictionary Format
        self.chat_history.append({"role": "user", "content": msg})

    async def _add_ai_msg(self, msg: str):
        # UPDATED: New Gradio Dictionary Format
        self.chat_history.append({"role": "assistant", "content": msg})

    def _send_manual_message(self, text: str):
        if not text.strip():
            return "", self.chat_history
            
        asyncio.run_coroutine_threadsafe(self.bus.publish("USER_SPOKE", text), self.main_loop)
        return "", self.chat_history

    def build_ui(self):
        with gr.Blocks(title="ALICE OS Dashboard") as interface:
            gr.Markdown("# 🧠 Project A.L.I.C.E. Control Center")
            
            with gr.Row():
                with gr.Column(scale=2):
                    # UPDATED: Added type="messages" to the Chatbot
                    chatbot = gr.Chatbot(label="Live Neural Feed", type="messages")
                    msg_box = gr.Textbox(label="Message ALICE directly", placeholder="Type a message...")
                    send_btn = gr.Button("Send")
                    
                    send_btn.click(self._send_manual_message, inputs=[msg_box], outputs=[msg_box, chatbot])
                    
                with gr.Column(scale=1):
                    gr.Markdown("### ⚙️ Subsystem Toggles")
                    gr.Checkbox(label="Microphone Listening", value=True)
                    gr.Checkbox(label="Discord Bot Active", value=True)
                    gr.Checkbox(label="Vision / Webcam Loop", value=False)
                    
                    gr.Markdown("### 📊 Hardware State")
                    gr.Textbox(label="VRAM Usage", value="18.2 GB / 24.0 GB", interactive=False)
                    
        return interface

def launch_webui(bus: EventBus, main_loop: asyncio.AbstractEventLoop):
    dashboard = AliceDashboard(bus, main_loop)
    ui = dashboard.build_ui()
    ui.launch(server_name="127.0.0.1", server_port=7860, prevent_thread_lock=True, theme="gruvbox")