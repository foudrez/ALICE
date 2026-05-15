import asyncio
import logging
import yaml

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
            
        # 2. Initialize Core Kernel
        self.bus = EventBus()
        self.hw_profile = hardware.get_optimal_execution_mode()
        self.memory = MemoryManager()
        
        # 3. Initialize Brain (Local vs Remote Fallback)
        if self.hw_profile['can_run_local_llm']:
            from modules.brain.local_llm import LocalBrain
            # Assuming LocalBrain takes (bus, memory), adjust if you require (bus, memory, config)
            self.llm = LocalBrain(self.bus, self.memory, self.config) 
        else:
            from modules.brain.remote_llm import RemoteBrain
            self.llm = RemoteBrain(self.bus, self.memory)

        # 4. Initialize Voice (Kokoro vs Edge-TTS Fallback)
        # We check config to see if Kokoro is explicitly requested, and if hardware supports it
        if self.hw_profile['can_run_local_tts'] and self.config.get('voice', {}).get('engine', 'kokoro') == 'kokoro':
            from modules.voice.kokoro_tts import TTSEngine
            self.tts = TTSEngine(self.bus)
        else:
            from modules.voice.fallback_tts import FallbackTTSEngine
            self.tts = FallbackTTSEngine(self.bus)

        # 5. Initialize Senses (Eyes & Ears)
        self.stt = STTEngine(self.bus)
        self.eyes = VisionEngine(self.bus)
        self.camera = CameraEngine(self.bus)
        
        # 6. Initialize Cognition (SEAL Background Processor)
        self.seal = SealEngine(self.bus, self.memory.l2_memory, self.llm)

        # 7. Initialize Limbs (IoT & Web)
        if self.config['active_modules'].get('enable_home_assistant', False):
            self.iot = HomeAssistantMCP(self.bus)
            
        if self.config['active_modules'].get('enable_web_search', False):
            self.web_agent = WebSearchAgent(self.bus)

        # 8. Initialize Gaming Agents (Tiered control)
        self.limbs = MotorAgent(self.bus)      # Zero-latency motor inputs (osu!)
        self.nav_agent = NavigationAgent(self.bus) # High-level pathfinding (Minecraft)
        self.api_agent = APIAgent(self.bus)    # State-translation (Turn-based games)

        # 9. Initialize Interfaces
        self.avatar_server = AvatarWebSocketServer(self.bus)
        
        if self.config['active_modules'].get('enable_local_mic', False):
            self.ui = LocalMicSpeaker(self.bus)
            
        if self.config['active_modules'].get('enable_discord', False):
            self.discord_interface = AliceDiscordBot(self.bus)

    async def run(self):
        logging.info("=== Booting Project ALICE ===")
        await self.bus.start()
        
        # Start Avatar WebSocket Server
        asyncio.create_task(self.avatar_server.start_server())
        
        # Start physical microphone loop (if enabled)
        if hasattr(self, 'ui'):
            await self.ui.start_listening()
            
        # Start Discord Bot (if enabled)
        if hasattr(self, 'discord_interface'):
            asyncio.create_task(self.discord_interface.start_bot())
            
        # --------------------------------------------------------
        # UPDATED WEBUI LAUNCH LOGIC:
        # --------------------------------------------------------
        logging.info("[WebUI] Starting Gradio Control Center...")
        
        # 1. Capture the main event loop
        main_loop = asyncio.get_running_loop() 
        
        # 2. Pass it to Gradio so it knows where to send button clicks
        launch_webui(self.bus, main_loop)      

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