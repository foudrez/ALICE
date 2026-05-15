import asyncio
import logging
import io
import wave
import torch
import numpy as np
from kokoro import KPipeline
from core.event_bus import EventBus
import yaml

class TTSEngine:
    def __init__(self, bus: EventBus):
        self.bus = bus
        
        # Load settings
        with open("config/system.yaml", 'r') as file:
            config = yaml.safe_load(file)['voice']
            
        self.language = config.get('language', 'a')
        self.speed = config.get('speed', 1.0)
        self.profile_path = config.get('active_profile')
        
        logging.info("[Voice] Booting Kokoro-82M TTS Engine...")
        
        # Initialize pipeline (Downloads model to ~/.cache/huggingface on first run)
        self.pipeline = KPipeline(lang_code=self.language)
        
        # Load ALICE's custom cloned voice profile
        try:
            self.voice_tensor = torch.load(self.profile_path, weights_only=True)
            logging.info(f"[Voice] Loaded custom voice profile: {self.profile_path}")
        except FileNotFoundError:
            logging.warning(f"[Voice] Custom profile {self.profile_path} not found. Falling back to default 'af_bella'.")
            self.voice_tensor = self.pipeline.voices['af_bella']

        self.bus.subscribe("SENTENCE_READY_FOR_TTS", self._synthesize_speech)

    async def _synthesize_speech(self, text: str):
        if not text.strip():
            return
            
        logging.info(f"[Voice] Synthesizing: '{text}'")
        
        loop = asyncio.get_running_loop()
        
        def run_kokoro():
            # Generate the raw audio array
            generator = self.pipeline(text, voice=self.voice_tensor, speed=self.speed)
            audio_chunks = []
            
            for _, _, audio in generator:
                audio_chunks.append(audio)
                
            if not audio_chunks:
                return None
                
            # Concatenate chunks and convert to 16-bit PCM WAV bytes
            final_audio = np.concatenate(audio_chunks)
            
            # Normalize and convert to int16
            final_audio = (final_audio * 32767).astype(np.int16)
            
            # Write to a bytes buffer
            buffer = io.BytesIO()
            with wave.open(buffer, 'wb') as wf:
                wf.setnchannels(1) # Mono
                wf.setsampwidth(2) # 16-bit
                wf.setframerate(24000) # Kokoro native sample rate
                wf.writeframes(final_audio.tobytes())
                
            return buffer.getvalue()

        # Run inference in a thread so it doesn't block the async loop
        audio_bytes = await loop.run_in_executor(None, run_kokoro)
        
        if audio_bytes:
            # Stream out to Discord and physical speakers
            await self.bus.publish("AUDIO_READY_TO_PLAY", audio_bytes)
            
            # Tell the visual avatar to move its mouth
            await self.bus.publish("AVATAR_LIPSYNC", text)