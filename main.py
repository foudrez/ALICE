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
    
    use_wakeword = cfg.get('stt', {}).get('use_wakeword', False)
    wakeword_threshold = cfg.get('stt', {}).get('wakeword_threshold', 0.5)
    
    if use_wakeword:
        import openwakeword
        from openwakeword.model import Model
        import glob
        import os
        
        if not os.path.exists(os.path.join(os.path.dirname(openwakeword.__file__), "resources", "models", "melspectrogram.onnx")):
            print("[System] Downloading openwakeword ONNX feature extractors...")
            openwakeword.utils.download_models()
        
        custom_models = glob.glob(os.path.join("tools", "wakeword", "*.onnx"))
        custom_models = [m for m in custom_models if not m.endswith("embedding_model.onnx") and not m.endswith("melspectrogram.onnx")]
        
        if not custom_models:
            print("[System] No custom .onnx wakeword models found in tools/wakeword/. Disabling Auto-Attention.")
            use_wakeword = False
        else:
            print(f"\n[System] Loading Custom Wakeword Models: {custom_models}")
            try:
                # Force ONNX inference framework to avoid tflite-runtime issues on Windows
                oww_model = Model(wakeword_models=custom_models, inference_framework="onnx")
            except Exception as e:
                print(f"[Error] Failed to load wakeword models: {e}")
                use_wakeword = False
            
    print("\n[👂 Active Listening Mode: ON]")
    
    while True:
        # 1. Automatic Echo Cancellation: Stop listening if ALICE is currently talking
        if alice_is_speaking:
            time.sleep(0.5)
            continue
            
        if use_wakeword:
            import pyaudio
            import numpy as np
            p = pyaudio.PyAudio()
            CHUNK = 1280
            stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=CHUNK, input_device_index=mic_id)
            
            triggered = False
            while not alice_is_speaking and not triggered:
                try:
                    data = stream.read(CHUNK, exception_on_overflow=False)
                except OSError:
                    continue
                audio_data = np.frombuffer(data, dtype=np.int16)
                oww_model.predict(audio_data)
                
                for mdl in oww_model.prediction_buffer.keys():
                    if oww_model.prediction_buffer[mdl][-1] > wakeword_threshold:
                        triggered = True
                        break
            
            stream.stop_stream()
            stream.close()
            p.terminate()
            
            if not triggered:
                continue
                
            print("\n[✨ Wakeword Detected! Listening...]")
            
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
        try:
            print("ALICE: ", end="", flush=True)
            
            # 5. Generate and stream the audio (with structured 4-layer memory context)
            is_streaming = cfg.get('enable_streaming', True)
            memory_context = mem.get_context_for_prompt(query_text=combined_text)
            ai_generator = generate_response(analysis_prompt, cfg, mem.get_history("local"), stream_output=is_streaming, past_memory_text=memory_context)
            
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
            
            # 6. Save to memory + trigger L2/L3/L4 processing
            mem.process_turn("User", combined_text, cfg, session_id="local")
            mem.process_turn("ALICE", full_response.strip(), cfg, session_id="local")
        except Exception as e:
            print(f"\n[Brain Thread Error] {e}")
        finally:
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
    mem = MemoryManager(
        history_limit=cfg['memory'].get('max_history', 10),
        db_path=cfg.get('memory', {}).get('db_path', 'alice_memory.db'),
        config=cfg,
    )
    
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
        # Consolidate memories before exit
        if cfg.get('memory', {}).get('l3_consolidate_on_exit', True):
            print("[🧠 Consolidating memories before shutdown...]")
            mem.consolidate(cfg)