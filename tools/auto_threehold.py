import pyaudio
import audioop

def calibrate_mic(input_device=None):
    print("\n[⚙️ Calibrating microphone... Please stay silent for 2 seconds]")
    
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000
    
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK, input_device_index=input_device)
    
    # Listen for 2 seconds
    num_reads = int((RATE / CHUNK) * 2)
    rms_values = []
    
    for _ in range(num_reads):
        data = stream.read(CHUNK, exception_on_overflow=False)
        rms = audioop.rms(data, 2)
        rms_values.append(rms)
        
    stream.stop_stream()
    stream.close()
    p.terminate()
    
    # Calculate average background noise
    avg_rms = sum(rms_values) / len(rms_values)
    
    # Set the threshold 50% higher than the background noise
    recommended_threshold = int(avg_rms * 1.5)
    
    # Enforce a minimum floor just in case the room is dead silent
    if recommended_threshold < 150:
        recommended_threshold = 150
        
    print(f"[✅ Calibration complete! Room noise: {int(avg_rms)} | Dynamic Threshold set to: {recommended_threshold}]")
    return recommended_threshold
