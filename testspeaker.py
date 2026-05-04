import os
import sounddevice as sd
from tools.audio_output import output_audio
from tools.load_config import load_config

FILE_PATH = "voice_process/output/python_cli_output.wav"

def test_playback(target_mode):
    if not os.path.exists(FILE_PATH):
        print(f"[❌ Error] Could not find the file at: {FILE_PATH}")
        return

    print(f"[+] Loading '{FILE_PATH}' into memory...")
    with open(FILE_PATH, "rb") as f:
        wav_bytes = f.read()

    cfg = load_config()
    if 'tts' not in cfg:
        cfg['tts'] = {}
        
    cfg['tts']['audio_mode'] = target_mode

    print(f"\n--- 🔊 PLAYING IN {target_mode.upper()} MODE ---")
    
    if target_mode == 'vb':
        print(f"Destination: {cfg['tts'].get('vb_cable_name', 'CABLE Output')}")
        print("Check your VSeeFace or OBS audio meters now!")
    else:
        # --- NEW: Retrieve Exact Hardware Name ---
        target_id = cfg['tts'].get('output_device_index')
        
        # If no ID is set in config, find the Windows default output ID
        if target_id is None:
            target_id = sd.default.device[1] 
            
        try:
            device_name = sd.query_devices(target_id)['name']
            print(f"Destination: {device_name} (Device ID: {target_id})")
        except Exception as e:
            print(f"Destination: Unknown Device ID {target_id} ({e})")
            
        print("You should hear this out loud.")
        
    output_audio(wav_bytes, cfg)
    print("--- ✅ Playback Complete ---\n")

if __name__ == "__main__":
    print("=== ALICE Audio Routing Diagnostic ===")
    print("1. Test Normal Mode (Physical Speakers)")
    print("2. Test VB Mode (Virtual Cable)")
    print("3. Exit")
    
    choice = input("Select a test to run (1/2/3): ").strip()
    
    if choice == '1':
        test_playback('normal')
    elif choice == '2':
        test_playback('vb')
    elif choice == '3':
        print("Exiting.")
    else:
        print("Invalid selection.")