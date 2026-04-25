import whisper
import random
from tools.auto_threehold import calibrate_mic
from voice_process.stt import listen
from voice_process.tts import speak
from LLM_process.llm import generate_response
from memory.log_memory import log_event
from tools.auto_compress import compress_and_save_memory
from tools.detect_cuda import COMPUTE_DEVICE, IS_HALF_PRECISION
from tools.load_config import load_config
#--------------------------------------------------------------------------------------------


#1 Main Application Loop
if __name__ == "__main__":
    
     # Load settings
    cfg = load_config()
    # Initialize chat history and load Whisper model
    chat_history = []
    print("Loading Whisper model into memory...")
    model= cfg['stt']['whisper_model'] # Change to 'small' or 'tiny' if needed
    #load model config
    whisper_model = whisper.load_model(model, device=COMPUTE_DEVICE, download_root="./models")
    
    print("Whisper ready!")
#--------------------------------------------------------------------------------------------    
    # Get the TTS reference variables directly from the config file
    audio_ref = cfg['tts']['reference_audio_path']
    text_ref = cfg['tts']['reference_prompt_text']
    # Extract the devices from config (if set) to pass to the respective functions
    mic_id = cfg['stt'].get('input_device_index', None)
    speaker_id = cfg['tts'].get('output_device_index', None)

    active_threshold = 500
    if cfg['stt'].get('auto_calibrate', False) and cfg['stt'].get('use_microphone', False):
        active_threshold = calibrate_mic(input_device=mic_id) # <-- Pass mic ID here
        
#--------------------------------------------------------------------------------------------
       
    log_event("SYSTEM", "=== NEW CHAT SESSION STARTED ===")
    print("ALICE System Initialized. Type 'quit' to exit.")
#--------------------------------------------------------------------------------------------

    while True:
        user_text = listen(cfg, whisper_model, cfg['stt']['use_microphone'], dynamic_threshold=active_threshold, input_device=mic_id) # <-- Pass mic ID here
        if user_text == "[IDLE_TICK]":
            print("[🧠 Generating Context-Aware Idle Tick...]")
            
            # We send a secret "System Command" as the user input
            secret_idle_prompt = "continue the conversation as if the user has been idle for a while. Generate a short, snappy complaint from ALICE about how the user has been ignoring her. Make it sound natural and in-character for a tsundere"
            
            # Let the Brain generate the complaint!
            tick_response = generate_response(secret_idle_prompt, cfg)
            
            print(f"ALICE (Idle Tick): {tick_response}")
            log_event("ALICE (Tick)", tick_response)
            
            speak(
                target_text=tick_response,
                ref_audio_path=audio_ref,
                prompt_text=text_ref,
                output_device=speaker_id 
            )
            continue
        # If the mic picked up nothing or it was just static, skip to next loop
        if not user_text.strip():
            continue
#--------------------------------------------------------------------------------------------        
        
        
        # --- 2. NATURAL GOODBYE DETECTION ---
        # Get the list from config, lower-case the user text for matching
        goodbye_list = cfg['llm'].get('goodbye_phrases', ['quit', 'exit', 'bye'])
        user_text_lower = user_text.lower()
        
        # Check if ANY of the goodbye phrases are inside what you just said
        if any(phrase in user_text_lower for phrase in goodbye_list):
            
            # Generate a dynamic goodbye based on the conversation!
            goodbye_prompt = "*System Notification*: The user is leaving. Say a quick, in-character goodbye."
            final_words = generate_response(goodbye_prompt, cfg)
            
            speak(
                target_text=final_words, 
                ref_audio_path=audio_ref, 
                prompt_text=text_ref, 
                output_device=speaker_id
            )
            
            # Compress and save memory
            compress_and_save_memory(chat_history, cfg)
            
            log_event("SYSTEM", "=== CHAT SESSION ENDED ===\n")
            break
 #--------------------------------------------------------------------------------------------        
           
        # Log User input and save to short-term memory
        log_event("User", user_text)
        
        # 2. Generate text (Brain)
        ai_response = generate_response(user_text, cfg)
        print(f"ALICE: {ai_response}")
        
        # Log AI response and save both to short-term memory
        log_event("ALICE", ai_response)
        
        chat_history.append({"speaker": "User", "text": user_text})
        chat_history.append({"speaker": "ALICE", "text": ai_response})
        
        # Prevent memory from getting too big (trim to the most recent X messages)
        
        MAX_HISTORY_LENGTH = cfg['memory']['max_history']
        if len(chat_history) > MAX_HISTORY_LENGTH * 2:
            chat_history = chat_history[-(MAX_HISTORY_LENGTH * 2):]
        
        # 3. Generate audio (Mouth)
        speak(
            target_text=ai_response,
            ref_audio_path=audio_ref,
            prompt_text=text_ref
        )