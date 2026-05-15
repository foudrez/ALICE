import asyncio
import logging
import edge_tts
from core.event_bus import EventBus

class FallbackTTSEngine:
    def __init__(self, bus: EventBus):
        self.bus = bus
        # 'en-US-AriaNeural' is a great, highly expressive female voice
        self.voice = "en-US-AriaNeural" 
        
        logging.info(f"[Voice] Initialized Edge-TTS Fallback ({self.voice})")
        self.bus.subscribe("SENTENCE_READY_FOR_TTS", self._synthesize_speech)

    async def _synthesize_speech(self, text: str):
        if not text.strip():
            return
            
        logging.info(f"[Voice] Synthesizing via Edge: '{text}'")
        communicate = edge_tts.Communicate(text, self.voice)
        
        audio_data = bytearray()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data.extend(chunk["data"])

        if audio_data:
            await self.bus.publish("AUDIO_READY_TO_PLAY", bytes(audio_data))
            await self.bus.publish("AVATAR_LIPSYNC", text)