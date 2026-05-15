import asyncio
import logging
import yaml
import threading

# Core Kernel
from core.event_bus import EventBus
from core.hardware_hal import hardware

# Cognition & Memory
from memory.memory_manager import MemoryManager
from memory.seal_engine import SealEngine

# Senses (Ears & Eyes)
from modules.ears.whisper_stt import STTEngine
from modules.eyes.screen_parser import VisionEngine
from modules.eyes.camera_feed import CameraEngine

# Limbs (Gaming & IoT)
from subsystems.iot.home_assistant import HomeAssistantMCP
from subsystems.iot.web_search import WebSearchAgent
from subsystems.gaming.motor_agent import MotorAgent
from subsystems.gaming.nav_agent import NavigationAgent
from subsystems.gaming.api_agent import APIAgent

# Interfaces (Bodies & UI)
from interfaces.local_mic_speaker import LocalMicSpeaker
from interfaces.discord_bot import AliceDiscordBot
from interfaces.avatar_websocket import AvatarWebSocketServer

# WebUI Dashboard
from webui.app import launch_webui

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

class AliceOrchestrator:
    def __init__(self):
        # 1. Load System Configuration
        with open("config/system.yaml", 'r', encoding='utf-8') as file:
            self.config = yaml.safe_load(file)
        print(f"✅ Configuration loaded. Active Modules: {', '.join([k for k,v in self.config['active_modules'].items() if v])}")
        # 2. Initialize Core Kernel
        self.bus = EventBus()
        self.hw_profile = hardware.get_optimal_execution_mode()
        self.memory = MemoryManager()
        # 3. Initialize Brain (Local vs Remote Fallback)
        if self.hw_profile['can_run_local_llm'] or self.config.get('force_local_models', False):
            from modules.brain.local_llm import LocalBrain
            # Assuming LocalBrain takes (bus, memory), adjust if you require (bus, memory, config)
            self.llm = LocalBrain(self.bus, self.memory, self.config) 
            print("✅ Local LLM initialized successfully.")
        else:
            from modules.brain.remote_llm import RemoteBrain
            self.llm = RemoteBrain(self.bus, self.memory)
            print("⚠️  Hardware constraints detected. Remote LLM fallback initialized.")
        # 4. Initialize Voice (Kokoro vs Edge-TTS Fallback)
        # We check config to see if Kokoro is explicitly requested, and if hardware supports it
        if self.hw_profile['can_run_local_tts'] and self.config.get('voice', {}).get('engine', 'kokoro') == 'kokoro':
            from modules.voice.kokoro_tts import TTSEngine
            self.tts = TTSEngine(self.bus)
            print("✅ Kokoro TTS Engine initialized successfully.")
        else:
            from modules.voice.fallback_tts import FallbackTTSEngine
            self.tts = FallbackTTSEngine(self.bus)
            print("⚠️  Kokoro TTS unavailable. Fallback TTS initialized.")

        # 5. Initialize Senses (Eyes & Ears)
        self.stt = STTEngine(self.bus)
        print("✅ STT Engine initialized successfully.")
        self.eyes = VisionEngine(self.bus)
        print("✅ Vision Engine initialized successfully.")
        self.camera = CameraEngine(self.bus)
        print("✅ Camera Engine initialized successfully.")
        # 6. Initialize Cognition (SEAL Background Processor)
        self.seal = SealEngine(self.bus, self.memory.l2_memory, self.llm)
        print("✅ SEAL Engine initialized successfully.")
        # 7. Initialize Limbs (IoT & Web)
        if self.config['active_modules'].get('enable_home_assistant', False):
            self.iot = HomeAssistantMCP(self.bus)
            print("✅ Home Assistant MCP initialized successfully.")
            
        if self.config['active_modules'].get('enable_web_search', False):
            self.web_agent = WebSearchAgent(self.bus)
            print("✅ Web Search Agent initialized successfully.")
        # 8. Initialize Gaming Agents (Tiered control)
        self.limbs = MotorAgent(self.bus)      # Zero-latency motor inputs (osu!)
        print("✅ Motor Agent initialized successfully.")
        self.nav_agent = NavigationAgent(self.bus) # High-level pathfinding (Minecraft)
        print("✅ Navigation Agent initialized successfully.")
        self.api_agent = APIAgent(self.bus)    # State-translation (Turn-based games)
        print("✅ API Agent initialized successfully.")

        # 9. Initialize Interfaces
        self.avatar_server = AvatarWebSocketServer(self.bus)
        print("✅ Avatar WebSocket Server initialized successfully.")
        
        if self.config['active_modules'].get('enable_local_mic', False):
            self.ui = LocalMicSpeaker(self.bus)
            print("✅ Local Microphone Speaker initialized successfully.")
            
        if self.config['active_modules'].get('enable_discord', False):
            self.discord_interface = AliceDiscordBot(self.bus)
            print("✅ Discord Interface initialized successfully.")
    async def run(self):
        logging.info("=== Booting Project ALICE ===")
        
        # Start the central event router
        await self.bus.start()
        
        # Start Avatar WebSocket Server
        asyncio.create_task(self.avatar_server.start_server())
        
        # Start physical microphone loop (if enabled)
        if hasattr(self, 'ui'):
            await self.ui.start_listening()
            
        # Start Discord Bot (if enabled)
        if hasattr(self, 'discord_interface'):
            asyncio.create_task(self.discord_interface.start_bot())
            
        # Start Gradio Web UI Dashboard in a background thread
        logging.info("[WebUI] Starting Gradio Control Center...")
        
        main_loop = asyncio.get_running_loop() 
        ui_thread = threading.Thread(target=launch_webui, args=(self.bus, main_loop), daemon=True)
        ui_thread.start()

        logging.info("=== All Systems Online. Ready to converse. ===")
        
        # Keep the orchestrator alive infinitely
        while True:
            await asyncio.sleep(1)
            
if __name__ == "__main__":
    alice = AliceOrchestrator()
    try:
        asyncio.run(alice.run())
    except KeyboardInterrupt:
        logging.info("Shutting down ALICE...")