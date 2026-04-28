import threading
import sounddevice as sd
import soundfile as sf
import io
import types

def get_device_id(name_fragment):
    """Finds a device ID based on a partial name string."""
    if name_fragment is None:
        return None
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        if name_fragment.lower() in dev['name'].lower() and dev['max_output_channels'] > 0:
            return i
    return None

def play_on_device(audio_data, samplerate, device_id):
    """Plays audio data on a specific device and waits for completion."""
    try:
        sd.play(audio_data, samplerate, device=device_id)
        sd.wait()
    except Exception as e:
        print(f"[Audio Error] Could not play on device {device_id}: {e}")

def output_audio(result, cfg):
    """
    Orchestrates audio playback based on 'normal' or 'vb' mode.
    Supports both batch bytes and streaming generators.
    """
    mode = cfg['tts'].get('audio_mode', 'normal').lower()
    vb_name = cfg['tts'].get('vb_cable_name', "CABLE Output")
    
    # Identify targets
    default_id = cfg['tts'].get('output_device_index') # Specified or None (Default)
    vb_id = get_device_id(vb_name) if mode == 'vb' else None

    def process_block(chunk_bytes):
        data, fs = sf.read(io.BytesIO(chunk_bytes))
        
        if mode == 'vb' and vb_id is not None:
            # Multi-threaded playback to avoid echo/delay
            t1 = threading.Thread(target=play_on_device, args=(data, fs, default_id))
            t2 = threading.Thread(target=play_on_device, args=(data, fs, vb_id))
            t1.start()
            t2.start()
            t1.join() # Wait for both to finish
            t2.join()
        else:
            # Normal single-device playback
            play_on_device(data, fs, default_id)

    # Handle Generator (Streaming) vs Bytes (Batch)
    if isinstance(result, types.GeneratorType):
        for chunk in result:
            process_block(chunk)
    else:
        process_block(result)