import os
import pyaudio
import audioop
import wave

# --- PURE WHISPER EARS (Custom Audio Recorder) ---
def listen(config, whisper_model,use_mic):
    if not use_mic:
        return input("\nYou: ")
        
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000 # Whisper's favorite sample rate
    THRESHOLD = 500 # Volume threshold (Increase if your room is noisy, decrease if mic is quiet)
    SILENCE_LIMIT = config['stt'].get('silence_timeout', 2)
    
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
    
    print("\n[🎙️ ALICE is listening... Speak now]")
    
    frames = []
    audio_started = False
    silent_chunks = 0
    
    # Custom recording loop
    while True:
        data = stream.read(CHUNK, exception_on_overflow=False)
        rms = audioop.rms(data, 2) # Calculate volume of this chunk
        
        if rms > THRESHOLD:
            audio_started = True
            silent_chunks = 0
            frames.append(data)
        elif audio_started:
            frames.append(data)
            silent_chunks += 1
            # If we've been silent for longer than the timeout, stop recording!
            if silent_chunks > (RATE / CHUNK * SILENCE_LIMIT):
                break
                
    print("[🔄 Processing offline speech...]")
    stream.stop_stream()
    stream.close()
    p.terminate()
    
    # Save to a temporary file for Whisper to read
    temp_filename = "temp_mic.wav"
    with wave.open(temp_filename, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
        
    # Transcribe using pure Whisper
    # fp16=False prevents warnings if running on CPU or older GPUs
    result = whisper_model.transcribe(temp_filename, fp16=False)
    text = result["text"].strip()
    
    # Clean up the temp file
    if os.path.exists(temp_filename):
        os.remove(temp_filename)
        
    print(f"You (Voice): {text}")
    return text