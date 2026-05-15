import gradio as gr
import asyncio
import sys
import os
import logging

# Allow imports from ALICE root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.event_bus import EventBus
from core.hardware_hal import hardware
from memory.memory_manager import MemoryManager

class AliceDashboard:
    def __init__(self, bus: EventBus, memory: MemoryManager, main_loop: asyncio.AbstractEventLoop):
        self.bus = bus
        self.memory = memory
        self.main_loop = main_loop
        self.subsystem_states = {}
        self.hardware_state = {
            "device": hardware.device,
            "vram": hardware.vram,
            "mode": "local" if hardware.vram >= 8.0 else "remote"
        }

        self.bus.subscribe("USER_SPOKE", self._on_user_spoke)
        self.bus.subscribe("SENTENCE_READY_FOR_TTS", self._on_ai_response)
        self.bus.subscribe("SUBSYSTEM_STATE_CHANGED", self._on_subsystem_change)

    async def _on_user_spoke(self, msg: str):
        self.memory.add_message("user", msg)

    async def _on_ai_response(self, msg: str):
        self.memory.add_message("assistant", msg)

    async def _on_subsystem_change(self, state: dict):
        self.subsystem_states.update(state)

    def _send_manual_message(self, text: str):
        if not text.strip():
            return "", self.memory.conversation_history
        try:
            asyncio.run_coroutine_threadsafe(
                self.bus.publish("USER_SPOKE", text),
                self.main_loop
            )
        except Exception as e:
            logging.error(f"Error sending message: {e}")
        return "", self.memory.conversation_history

    def _toggle_mic(self, value):
        asyncio.run_coroutine_threadsafe(
            self.bus.publish("SUBSYSTEM_MIC_TOGGLE", value),
            self.main_loop
        )
        return value

    def _toggle_discord(self, value):
        asyncio.run_coroutine_threadsafe(
            self.bus.publish("SUBSYSTEM_DISCORD_TOGGLE", value),
            self.main_loop
        )
        return value

    def _toggle_vision(self, value):
        asyncio.run_coroutine_threadsafe(
            self.bus.publish("SUBSYSTEM_VISION_TOGGLE", value),
            self.main_loop
        )
        return value

    def _get_hardware_status(self):
        device_map = {
            "cuda": "NVIDIA GPU",
            "mps": "Apple Silicon",
            "cpu": "CPU Only"
        }
        device_name = device_map.get(self.hardware_state["device"], self.hardware_state["device"])
        vram_display = f"{self.hardware_state['vram']} GB" if self.hardware_state["vram"] > 0 else "N/A"
        return f"Device: {device_name}\nVRAM: {vram_display}\nMode: {self.hardware_state['mode'].upper()}"

    def build_ui(self):
        with gr.Blocks(title="ALICE OS Dashboard", theme=gr.themes.Soft(primary_hue="blue")) as interface:
            gr.Markdown("# 🧠 Project A.L.I.C.E. Control Center")

            with gr.Row():
                with gr.Column(scale=2):
                    chatbot = gr.Chatbot(label="Live Neural Feed", type="messages")
                    msg_box = gr.Textbox(label="Message ALICE directly", placeholder="Type a message...")
                    send_btn = gr.Button("Send", variant="primary")

                    send_btn.click(
                        self._send_manual_message,
                        inputs=[msg_box],
                        outputs=[msg_box, chatbot]
                    )

                with gr.Column(scale=1):
                    gr.Markdown("### ⚙️ Subsystem Controls")
                    mic_toggle = gr.Checkbox(label="🎙️ Microphone", value=True)
                    discord_toggle = gr.Checkbox(label="💬 Discord Bot", value=True)
                    vision_toggle = gr.Checkbox(label="👁️ Vision", value=False)

                    mic_toggle.change(self._toggle_mic, inputs=[mic_toggle], outputs=[mic_toggle])
                    discord_toggle.change(self._toggle_discord, inputs=[discord_toggle], outputs=[discord_toggle])
                    vision_toggle.change(self._toggle_vision, inputs=[vision_toggle], outputs=[vision_toggle])

                    gr.Markdown("### 📊 Hardware State")
                    hw_status = gr.Textbox(
                        label="System Info",
                        value=self._get_hardware_status(),
                        interactive=False
                    )
                    chat_info = gr.Textbox(
                        label="Chat Stats",
                        value=f"Messages: {len(self.memory.conversation_history)}/{self.memory.max_history}",
                        interactive=False
                    )

        return interface

def launch_webui(bus: EventBus, memory: MemoryManager, main_loop: asyncio.AbstractEventLoop):
    dashboard = AliceDashboard(bus, memory, main_loop)
    ui = dashboard.build_ui()
    ui.launch(server_name="127.0.0.1", server_port=7860, prevent_thread_lock=True, theme=gr.themes.Soft())