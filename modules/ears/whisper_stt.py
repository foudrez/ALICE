import asyncio
import logging
from faster_whisper import WhisperModel
from core.event_bus import EventBus
from core.hardware_hal import hardware

class STTEngine:
    def __init__(self, bus: EventBus):
        self.bus = bus
        self.device = hardware.device if hardware.device in ["cuda", "cpu"] else "cpu" # MPS support varies for whisper
        self.compute_type = "float16" if self.device == "cuda" else "int8"
        
        logging.info(f"[Ears] Loading Faster-Whisper on {self.device}...")
        # Using base.en for speed; upgrade to small.en or large-v3 based on hardware
        self.model = WhisperModel("small.en", device=self.device, compute_type=self.compute_type)
        
        # Subscribe to raw audio events (simulated hardware mic stream)
        self.bus.subscribe("RAW_AUDIO_CAPTURED", self._process_audio)
        
    def execute_transcription(self, audio_data):
    # Assuming you pass whatever audio data you need to your model here
        segments, info =self.model.transcribe(audio_data) 
        return "".join([segment.text for segment in segments]).strip()

    async def _process_audio(self, audio_file_path: str):
        """Processes an audio chunk when VAD detects the user stopped speaking."""
        logging.info("[Ears] Processing speech chunk...")
        
        # Run Whisper in a separate thread so it doesn't block the async event loop
        loop = asyncio.get_running_loop()
        
        transcription = await asyncio.to_thread(self.execute_transcription, audio_file_path)
        
        if transcription:
            logging.info(f"[Ears] Heard: {transcription}")
            await self.bus.publish("USER_SPOKE", transcription)