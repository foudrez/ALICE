import os
import pyaudio
import audioop
import wave

def listen(config, whisper_model, active_threshold, input_device=None):
    if not config['stt'].get('use_microphone', True):
        return input("\nYou: ")

    CHUNK, FORMAT, CHANNELS, RATE = 1024, pyaudio.paInt16, 1, 16000
    THRESHOLD = active_threshold # Use the passed-in calibrated value
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
        
    result = whisper_model.transcribe(temp_filename, fp16=False)
    text = result["text"].strip()
    if os.path.exists(temp_filename): os.remove(temp_filename)
    return text