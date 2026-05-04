import os
import pyaudio
import audioop
import wave
import base64
import requests

def listen(config, whisper_model, active_threshold, input_device=None):
    if not config['stt'].get('use_microphone', True):
        return input("\nYou: ")

    CHUNK, FORMAT, CHANNELS, RATE = 1024, pyaudio.paInt16, 1, 16000
    THRESHOLD = active_threshold 
    SILENCE_LIMIT = config['stt'].get('silence_timeout', 2)
    IDLE_TIMEOUT = config['stt'].get('idle_timeout', 15)
    
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, 
                    frames_per_buffer=CHUNK, input_device_index=input_device)
    
    print("\n[🎙️ ALICE is listening...]")
    frames, audio_started, silent_chunks, idle_chunks = [], False, 0, 0

    while True:
        data = stream.read(CHUNK, exception_on_overflow=False)
        rms = audioop.rms(data, 2)
        
        if rms > THRESHOLD:
            audio_started, silent_chunks, idle_chunks = True, 0, 0
            frames.append(data)
        elif audio_started:
            frames.append(data)
            silent_chunks += 1
            if silent_chunks > (RATE / CHUNK * SILENCE_LIMIT): break
        else:
            idle_chunks += 1
            if idle_chunks > (RATE / CHUNK * IDLE_TIMEOUT):
                stream.stop_stream(); stream.close(); p.terminate()
                return "[IDLE_TICK]"
                
    stream.stop_stream(); stream.close(); p.terminate()
    
    temp_filename = "temp_mic.wav"
    with wave.open(temp_filename, 'wb') as wf:
        wf.setnchannels(CHANNELS); wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE); wf.writeframes(b''.join(frames))
        
    # --- ROUTE TO GEMMA4 E2B OR WHISPER ---
    stt_engine = config['stt'].get('engine', 'whisper').lower()
    
    if stt_engine == 'gemma':
        # Encode audio to base64
        with open(temp_filename, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode('utf-8')
            
        url = "http://localhost:11434/api/generate"
        payload = {
            "model": "gemma4:e2b",
            "prompt": "Transcribe the following audio accurately. Output ONLY the transcription text and nothing else.",
            "images": [audio_b64], # Ollama parses multimodal files through this array
            "stream": False
        }
        try:
            response = requests.post(url, json=payload)
            text = response.json().get('response', '').strip()
        except Exception as e:
            print(f"[Error] Gemma STT Failed: {e}")
            text = ""
    else:
        # Fallback to Whisper
        if whisper_model:
            result = whisper_model.transcribe(temp_filename, fp16=False)
            text = result["text"].strip()
        else:
            print("[Error] Whisper model not loaded!")
            text = ""
            
    if os.path.exists(temp_filename): os.remove(temp_filename)
    return text