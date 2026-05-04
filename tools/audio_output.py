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
    Orchestrates audio playback. 
    Prioritizes the exact integer ID defined in the system config.
    """
    mode = cfg['tts'].get('audio_mode', 'normal').lower()
    
    # 1. Safely pull the exact Integer ID from the new system block
    target_id = cfg.get('system', {}).get('output_device_index', None)
    
    # 2. Fallback Safety Net: If you forgot to set an ID, try to guess by name
    if mode == 'vb' and target_id is None:
        vb_name = cfg['tts'].get('vb_cable_name', "CABLE Input")
        target_id = get_device_id(vb_name)
        if target_id is None:
            print(f"[Audio Warning] VB-Cable '{vb_name}' not found. Falling back to default speakers.")

    def process_block(chunk_bytes):
        # Convert bytes to raw audio data
        data, fs = sf.read(io.BytesIO(chunk_bytes))
        
        # Play directly to the target (If target_id is None, sounddevice uses Windows Default)
        play_on_device(data, fs, target_id)

    # Handle Generator (Streaming) vs Bytes (Batch)
    if isinstance(result, types.GeneratorType):
        for chunk in result:
            process_block(chunk)
    else:
        process_block(result)