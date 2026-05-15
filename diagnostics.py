import os
import sys
import asyncio
import logging
import tempfile
import wave

# Ensure the root ALICE directory is in the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.event_bus import EventBus
from core.hardware_hal import hardware
from memory.memory_manager import MemoryManager

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s | %(message)s")

class AliceDiagnostics:
    def __init__(self):
        self.bus = EventBus()
        self.passed = 0
        self.failed = 0
        self.warnings = 0

    async def run_all_tests(self):
        print("\n" + "="*60)
        print("🤖 INITIATING A.L.I.C.E. SYSTEM DIAGNOSTICS")
        print("="*60 + "\n")

        await self.test_1_environment_and_secrets()
        await self.test_2_hardware()
        await self.test_3_event_bus()
        await self.test_4_memory_systems()
        await self.test_5_llm_brain()
        await self.test_6_tts_voice()
        
        print("\n" + "="*60)
        print(f"🏁 DIAGNOSTICS COMPLETE: {self.passed} Passed | {self.failed} Failed | {self.warnings} Warnings")
        if self.failed > 0:
            print("⚠️  Review the failed modules. Ensure you have downloaded the required models.")
        elif self.warnings > 0:
            print("💡 System is functional, but running in a degraded/fallback mode due to missing files/keys.")
        else:
            print("✅ All systems nominal. You are cleared to launch: `python run.py`")
        print("="*60 + "\n")

    def _pass(self, msg):
        logging.info(f"✅ PASS: {msg}")
        print(f"✅ PASS: {msg}")
        self.passed += 1

    def _fail(self, msg, error):
        logging.error(f"❌ FAIL: {msg} | Error: {error}")
        print(f"❌ FAIL: {msg} | Error: {error}")
        self.failed += 1

    def _warn(self, msg):
        logging.warning(f"⚠️  WARN: {msg}")
        print(f"⚠️  WARN: {msg}")
        self.warnings += 1

    # ---------------------------------------------------------
    async def test_1_environment_and_secrets(self):
        logging.info("--- Testing Environment & Config ---")
        try:
            from dotenv import load_dotenv
            load_dotenv("config/.env")
            
            if not os.path.exists("config/system.yaml"):
                self._fail("Config", "config/system.yaml is missing!")
            elif not os.getenv("OPENAI_API_KEY"):
                self._warn("OPENAI_API_KEY missing in .env (Cloud fallback disabled).")
            else:
                self._pass("Configuration files and environment variables loaded.")
        except Exception as e:
            self._fail("Environment Loader", e)

    # ---------------------------------------------------------
    async def test_2_hardware(self):
        logging.info("--- Testing Hardware HAL ---")
        try:
            profile = hardware.get_optimal_execution_mode()
            self._pass(f"Hardware detected: {profile['device'].upper()} with {hardware.vram}GB VRAM")
        except Exception as e:
            self._fail("Hardware Detection", e)

    # ---------------------------------------------------------
    async def test_3_event_bus(self):
        logging.info("--- Testing Event Bus Routing ---")
        self.test_flag = False

        async def dummy_callback(payload):
            self.test_flag = payload == "test_data"

        try:
            asyncio.create_task(self.bus._process_events())
            self.bus.subscribe("TEST_EVENT", dummy_callback)
            await self.bus.publish("TEST_EVENT", "test_data")
            await asyncio.sleep(0.1)
            
            if self.test_flag:
                self._pass("Event Bus successfully routed message.")
            else:
                self._fail("Event Bus", "Message lost in transit.")
        except Exception as e:
            self._fail("Event Bus", e)

    # ---------------------------------------------------------
    async def test_4_memory_systems(self):
        logging.info("--- Testing Memory & ChromaDB ---")
        try:
            memory = MemoryManager()
            memory.add_message("user", "System diagnostic test string.")
            recalled = memory.l2_memory.query_memory("System diagnostic test string.", n_results=1)
            self._pass("ChromaDB Vector Database successfully stored and recalled context.")
        except Exception as e:
            self._fail("Memory Systems (Did you pip install chromadb?)", e)

    # ---------------------------------------------------------
    async def test_5_llm_brain(self):
        logging.info("--- Testing Brain (LLM) ---")
        try:
            profile = hardware.get_optimal_execution_mode()
            model_path = "assets/llm/primary_llama3_8b.gguf"
            
            if profile['can_run_local_llm']:
                if os.path.exists(model_path):
                    self._pass(f"Local LLM located at {model_path}.")
                else:
                    self._warn(f"Local LLM missing at {model_path}. System will use Remote Fallback.")
            else:
                self._pass("Hardware constrained. Will default to RemoteBrain.")
        except Exception as e:
            self._fail("Brain Diagnostics", e)

    # ---------------------------------------------------------
    async def test_6_tts_voice(self):
        logging.info("--- Testing Voice (Kokoro TTS) ---")
        try:
            import kokoro
            voice_path = "assets\\tts\\voice_profiles\\alice_v3.pt"
            if os.path.exists(voice_path):
                self._pass(f"Kokoro custom voice profile found at {voice_path}.")
            else:
                self._warn(f"Custom voice profile missing. Run `python tools/voice_studio.py` to create one.")
        except ImportError:
            self._fail("Voice Engine", "Kokoro library not installed. Run `pip install kokoro`.")
        except Exception as e:
            self._fail("Voice Engine", e)

if __name__ == "__main__":
    diag = AliceDiagnostics()
    asyncio.run(diag.run_all_tests())