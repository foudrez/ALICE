import pyaudio 
import sounddevice as sd
import wave
import soundfile as sf
import os

from tools.load_config import load_config
cfg = load_config()
from voice_process.tts import speak

print("\n--- 🔊 AVAILABLE SPEAKERS ---")
print(sd.query_devices())


temp_wav = "test_audio.wav"
#spk_idx_input = input("\nEnter Speaker ID to test (or press Enter for default): ")
#spk_idx = int(spk_idx_input) if spk_idx_input.strip() else None
speaker_id = cfg['tts'].get('output_device_index')
print("\n[🔊 Testing TTS Output...]")
ai_response = "This is a test of ALICE's text-to-speech system. If you can hear this, it works!"
result = speak(ai_response, cfg)
print("\n[🔊 Playing back your recording...]")
data, fs = sf.read(temp_wav)
sd.play(data, fs, device='CABLE Input (VB-Audio Virtual C, MME')
sd.wait()