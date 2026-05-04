import threading
import queue
import time
import whisper

from tools.load_config import load_config
from tools.detect_cuda import COMPUTE_DEVICE
from tools.auto_threehold import calibrate_mic
from memory.memory_manager import MemoryManager
from voice_process.stt import listen
from voice_process.tts import speak
from LLM_process.llm import generate_response
from tools.audio_output import output_audio
from tools.language_detector import get_language

# --- THE NEURAL QUEUE ---
# This acts as ALICE's short-term auditory buffer
thought_queue = queue.Queue()

# Prevents ALICE from listening to her own voice and causing an infinite feedback loop
alice_is_speaking = False 


def ear_thread(cfg, whisper_model, active_threshold, mic_id):
    """Runs constantly in the background, gathering transcripts into the buffer."""
    global alice_is_speaking
    print("\n[👂 Active Listening Mode: ON]")
    
    while True:
        # 1. Automatic Echo Cancellation: Stop listening if ALICE is currently talking
        if alice_is_speaking:
            time.sleep(0.5)
            continue
            
        # 2. Listen to the environment
        text = listen(cfg, whisper_model, active_threshold, input_device=mic_id)
        if text and text != "[IDLE_TICK]":
            print(f"\n[Subtitles]: {text}")
            thought_queue.put(text)

def brain_thread(cfg, mem):
    """Waits for gathered thoughts, extracts the main idea, and streams a reply."""
    global alice_is_speaking
    
    while True:
        # 1. Wait indefinitely until the ears hear at least one thing
        first_thought = thought_queue.get() 
        
        # 2. Gather any additional thoughts that piled up while waiting
        rambling_buffer = [first_thought]
        while not thought_queue.empty():
            rambling_buffer.append(thought_queue.get())
            
        combined_text = " ".join(rambling_buffer)
        
        # 3. --- MAIN IDEA EXTRACTION PROMPT ---
        # We wrap the user's raw text in a psychological trick to force the LLM to summarize and react
        analysis_prompt = (
            f"[System Override]: The user has been talking in the background. "
            f"Transcript: '{combined_text}'. "
            f"Task: Extract the main idea of what they are talking about, and write a natural, conversational response to chime in."
        )
        
        # 4. Lock the ears so she doesn't hear herself
        alice_is_speaking = True
        print("ALICE: ", end="", flush=True)
        
        # 5. Generate and stream the audio
        is_streaming = cfg.get('enable_streaming', True)
        ai_generator = generate_response(analysis_prompt, cfg, mem.get_history(), stream_output=is_streaming)
        
        full_response = ""
        for sentence in ai_generator:
            print(sentence + " ", end="", flush=True)
            full_response += sentence + " "
            
            target_lang = cfg['tts'].get('default_lang', 'en')
            if cfg['tts'].get('auto_detect_language', True):
                target_lang = get_language(sentence, default_lang=target_lang)
                
            result = speak(sentence, cfg, lang=target_lang)
            output_audio(result, cfg)
            
        print()
        
        # 6. Save the clean context to memory (not the hidden prompt)
        mem.add_to_history("User", combined_text)
        mem.add_to_history("ALICE", full_response.strip())
        
        # 7. Unlock the ears to start listening again
        alice_is_speaking = False
        
        # Mark all items in the buffer as processed
        for _ in range(len(rambling_buffer)):
            thought_queue.task_done()

# -------------------------------------- MAIN ENTRY POINT --------------------------------------------------------------    
if __name__ == "__main__":
    cfg = load_config()
    if 'tts' not in cfg: cfg['tts'] = {}
    cfg['tts']['audio_mode'] = 'normal'
    mem = MemoryManager(history_limit=cfg['memory'].get('max_history', 10))
    
    # Lazy-Load Whisper/Gemma STT
    whisper_model = None
    if cfg['stt'].get('engine', 'whisper') == 'whisper':
        whisper_model = whisper.load_model(cfg['stt']['whisper_model'], device=COMPUTE_DEVICE, download_root="./models")
    else:
        print("[System] Bypassing Whisper. Using Gemma4 E2B for STT.")
    
    mic_id = cfg['stt'].get('input_device_index')
    active_threshold = calibrate_mic(input_device=mic_id) if cfg['stt'].get('auto_calibrate') else 500
    
    print("ALICE Modular System Active.")
    
    # --- START ASYNCHRONOUS THREADS ---
    threading.Thread(target=ear_thread, args=(cfg, whisper_model, active_threshold, mic_id), daemon=True).start()
    threading.Thread(target=brain_thread, args=(cfg, mem), daemon=True).start()
    
    # Keep the main orchestrator alive while the threads do the work
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[System] Shutting down ALICE...")