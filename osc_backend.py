import time
import threading
import whisper
import base64
import types
import os
import re
import keyboard
from pythonosc import udp_client

# ALICE Modules
from tools.load_config import load_config
from tools.detect_cuda import COMPUTE_DEVICE
from memory.memory_manager import MemoryManager
from LLM_process.llm import generate_response
from voice_process.stt import listen
from voice_process.tts import speak
from tools.language_detector import get_language
from tools.audio_output import output_audio
from tools.home_assistant import execute_ha_command

print("Initializing ALICE OSC Backend...")

# Setup Config & Memory
cfg = load_config()
if 'tts' not in cfg: cfg['tts'] = {}
cfg['tts']['audio_mode'] = 'vb'
mem = MemoryManager(
    history_limit=cfg['memory'].get('max_history', 10),
    db_path=cfg.get('memory', {}).get('db_path', 'alice_memory.db'),
    config=cfg,
)

# OSC Setup
OSC_IP = "127.0.0.1"
OSC_PORT = 9000
client = udp_client.SimpleUDPClient(OSC_IP, OSC_PORT)
print(f"OSC Client established targeting {OSC_IP}:{OSC_PORT}")

# STT Setup
whisper_model = None
if cfg['stt'].get('engine', 'whisper') == 'whisper':
    print("Loading Whisper Model...")
    whisper_model = whisper.load_model(cfg['stt'].get('whisper_model', 'base'), device=COMPUTE_DEVICE, download_root="./models")
active_threshold = 500

alice_is_speaking = False
stop_generation_event = threading.Event()

def run_alice_cycle(user_text, session_id="local"):
    global alice_is_speaking
    alice_is_speaking = True
    stop_generation_event.clear()
    
    print(f"\nUser: {user_text}")
    client.send_message("/avatar/status", "Thinking...")

    is_streaming = cfg.get('enable_streaming', True)
    memory_context = mem.get_context_for_prompt(query_text=user_text)
    
    # Notice we do not pass image_data here as OSC backend screen capture is omitted for simplicity unless added later
    ai_response_generator = generate_response(user_text, cfg, mem.get_history(session_id), stream_output=is_streaming, past_memory_text=memory_context, image_data=None)
    
    full_response = ""

    def process_sentence(sentence):
        nonlocal full_response
        
        commands = re.findall(r'\[CMD:\s*(.*?)\]', sentence)
        animations = re.findall(r'\[ANIM:\s*(.*?)\]', sentence)
        
        clean_sentence = re.sub(r'\[CMD:.*?\]', '', sentence)
        clean_sentence = re.sub(r'\[ANIM:.*?\]', '', clean_sentence)
        clean_sentence = re.sub(r'<think>.*?</think>', '', clean_sentence, flags=re.DOTALL | re.IGNORECASE)
        clean_sentence = re.sub(r'<[^>]+>', '', clean_sentence).strip()
        
        for anim in animations:
            print(f"[System] OSC Queuing Animation: {anim}")
            client.send_message("/avatar/animation", anim.strip())
            
        for cmd in commands:
            execute_ha_command(cmd, cfg)
            
        if not clean_sentence:
            return
            
        full_response += clean_sentence + " "
        target_lang = cfg['tts'].get('default_lang', 'en')
        if cfg['tts'].get('auto_detect_language', True):
            target_lang = get_language(clean_sentence, default_lang=target_lang)
            
        print(f"ALICE: {clean_sentence}")
        client.send_message("/avatar/speech", clean_sentence)
        client.send_message("/avatar/status", "Speaking...")
        
        # Audio playback blocks until finished
        result = speak(clean_sentence, cfg, lang=target_lang)
        full_audio_buffer = b""
        if isinstance(result, types.GeneratorType):
            for chunk_bytes in result:
                full_audio_buffer += chunk_bytes
        else:
            full_audio_buffer = result
            
        if stop_generation_event.is_set():
            return
            
        output_audio(full_audio_buffer, cfg)

    try:
        if is_streaming:
            for sentence in ai_response_generator:
                if stop_generation_event.is_set():
                    break
                process_sentence(sentence)
        else:
            if not stop_generation_event.is_set():
                process_sentence(ai_response_generator)
                
        mem.process_turn("User", user_text, cfg, session_id=session_id)
        mem.process_turn("ALICE", full_response.strip(), cfg, session_id=session_id)
        client.send_message("/avatar/status", "Ready")
    except Exception as e:
        print(f"\n[OSC Cycle Error] {e}")
        client.send_message("/avatar/status", "Error")
    finally:
        alice_is_speaking = False
        print("\nReady for input. Press F8 to talk.")

    return full_response.strip()

def ptt_worker():
    global alice_is_speaking
    if alice_is_speaking:
        print("Interrupting ALICE...")
        stop_generation_event.set()
        return

    print("\nListening... (Speak now)")
    client.send_message("/avatar/status", "Listening...")
    user_text = listen(cfg, whisper_model, active_threshold, input_device=cfg['stt'].get('input_device_index'))
    if user_text and user_text != "[IDLE_TICK]":
        threading.Thread(target=run_alice_cycle, args=(user_text,)).start()
    else:
        client.send_message("/avatar/status", "Ready")
        print("\nReady for input. Press F8 to talk.")

def main():
    hotkey = 'f8'
    print(f"Registering global hotkey: {hotkey}")
    keyboard.add_hotkey(hotkey, ptt_worker, suppress=True)
    
    print("\n" + "="*50)
    print("ALICE OSC Backend is Running!")
    print(f"Press '{hotkey.upper()}' to push-to-talk.")
    print("Press CTRL+C to exit.")
    print("="*50 + "\n")
    client.send_message("/avatar/status", "Ready")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting...")

if __name__ == '__main__':
    main()
