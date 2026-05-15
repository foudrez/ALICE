import asyncio
import logging
import wave
import tempfile
import os
import io
import numpy as np
import pyaudio
from core.event_bus import EventBus

class LocalMicSpeaker:
    def __init__(self, bus: EventBus):
        self.bus = bus
        
        # Audio Configuration
        self.CHUNK = 1024
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 16000 # 16kHz is optimal for Whisper STT
        
        # VAD (Voice Activity Detection) Parameters
        self.SILENCE_LIMIT = 1.5  # Seconds of silence before cutting the recording
        self.VOLUME_THRESHOLD = 500  # Adjust this if your mic is too sensitive/quiet
        
        self.audio = pyaudio.PyAudio()
        
        # Listen for when ALICE wants to speak
        self.bus.subscribe("AUDIO_READY_TO_PLAY", self._play_audio)

    async def start_listening(self):
        """Starts the microphone listener in a background thread."""
        loop = asyncio.get_running_loop()
        # Run the blocking mic loop in an executor so it doesn't freeze the brain
        asyncio.create_task(asyncio.to_thread(self._mic_loop, loop))

    def _mic_loop(self, main_loop):
        """Continuous loop that monitors mic input for speech."""
        stream = self.audio.open(format=self.FORMAT, channels=self.CHANNELS,
                                 rate=self.RATE, input=True, frames_per_buffer=self.CHUNK)
        
        logging.info("[Mic] Hardware active. Waiting for you to speak...")
        
        audio_buffer = []
        is_recording = False
        silent_chunks = 0
        silence_threshold_chunks = int((self.RATE / self.CHUNK) * self.SILENCE_LIMIT)
        
        try:
            while True:
                # Read audio chunk
                data = stream.read(self.CHUNK, exception_on_overflow=False)
                
                # Calculate volume (Root Mean Square)
                audio_data = np.frombuffer(data, dtype=np.int16)
                volume = np.sqrt(np.mean(audio_data.astype(np.float32)**2))
                
                if volume > self.VOLUME_THRESHOLD:
                    if not is_recording:
                        logging.info("[Mic] Detecting speech...")
                        is_recording = True
                    audio_buffer.append(data)
                    silent_chunks = 0  # Reset silence counter
                
                elif is_recording:
                    audio_buffer.append(data)
                    silent_chunks += 1
                    
                    # If user stops speaking for 1.5 seconds, process the audio
                    if silent_chunks > silence_threshold_chunks:
                        logging.info("[Mic] Speech complete. Sending to STT...")
                        is_recording = False
                        self._save_and_publish(audio_buffer, main_loop)
                        audio_buffer = []
                        silent_chunks = 0
        except Exception as e:
            logging.error(f"[Mic] Loop crashed: {e}")
        finally:
            stream.stop_stream()
            stream.close()

    def _save_and_publish(self, audio_buffer, main_loop):
        """Saves the raw audio to a temp file and fires it to the EventBus."""
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, "alice_user_input.wav")
        
        with wave.open(file_path, 'wb') as wf:
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(self.audio.get_sample_size(self.FORMAT))
            wf.setframerate(self.RATE)
            wf.writeframes(b''.join(audio_buffer))
            
        # Safely publish the event back to the main async loop
        asyncio.run_coroutine_threadsafe(
            self.bus.publish("RAW_AUDIO_CAPTURED", file_path), 
            main_loop
        )

    async def _play_audio(self, audio_bytes: bytes):
        """Plays the generated AI voice through the physical speakers."""
        logging.info("[Speaker] Playing ALICE's voice...")
        loop = asyncio.get_running_loop()
        
        def play():
            # Load bytes into a wave object
            f = io.BytesIO(audio_bytes)
            try:
                wf = wave.open(f, 'rb')
                stream = self.audio.open(format=self.audio.get_format_from_width(wf.getsampwidth()),
                                         channels=wf.getnchannels(),
                                         rate=wf.getframerate(),
                                         output=True)
                
                data = wf.readframes(1024)
                while data:
                    stream.write(data)
                    data = wf.readframes(1024)
                    
                stream.stop_stream()
                stream.close()
            except Exception as e:
                logging.error(f"[Speaker] Failed to play audio: {e}")

        # Run playback in a thread to prevent blocking
        await loop.run_in_executor(None, play)