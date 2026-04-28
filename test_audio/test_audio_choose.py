import pyaudio 
import sounddevice as sd
import wave
import soundfile as sf
import os


print("=== ALICE AUDIO DIAGNOSTICS ===")

# --- 1. TEST MICROPHONE (PyAudio) ---
p = pyaudio.PyAudio()
print("\n--- 🎤 AVAILABLE MICROPHONES ---")
for i in range(p.get_device_count()):
    dev = p.get_device_info_by_index(i)
    if dev['maxInputChannels'] > 0:
        print(f"[{i}] {dev['name']}")

mic_idx_input = input("\nEnter Mic ID to test (or press Enter for default): ")
mic_idx = int(mic_idx_input) if mic_idx_input.strip() else None

CHUNK, FORMAT, CHANNELS, RATE = 1024, pyaudio.paInt16, 1, 16000
print("\n[🎙️ Recording for 3 seconds... SAY SOMETHING!]")

stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, 
                frames_per_buffer=CHUNK, input_device_index=mic_idx)
frames = [stream.read(CHUNK) for _ in range(0, int(RATE / CHUNK * 3))]
stream.stop_stream()
stream.close()
p.terminate()

temp_wav = "test_audio.wav"
with wave.open(temp_wav, 'wb') as wf:
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    
data, fs = sf.read(temp_wav)

sd.play(data,fs, device=mic_idx)
sd.wait()
