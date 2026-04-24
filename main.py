import whisper
import yaml
import requests
from voice_process.stt import listen
from voice_process.tts import speak
from LLM_process.llm import generate_response
from memory.log_memory import log_event
#--------------------------------------------------------------------------------------------


def load_config():
    with open("config.yaml", "r", encoding="utf-8") as file:
        return yaml.safe_load(file)
#--------------------------------------------------------------------------------------------


#2 Main Application Loop
if __name__ == "__main__":
     # Load settings
    cfg = load_config()
    # Initialize chat history and load Whisper model
    chat_history = []
    print("Loading Whisper model into memory...")
    model= cfg['stt']['whisper_model'] # Change to 'small' or 'tiny' if needed
    whisper_model = whisper.load_model(model)
    print("Whisper ready!")
    
    # Get the TTS reference variables directly from the config file
    audio_ref = cfg['tts']['reference_audio_path']
    text_ref = cfg['tts']['reference_prompt_text']
    log_event("SYSTEM", "=== NEW CHAT SESSION STARTED ===")
    print("ALICE System Initialized. Type 'quit' to exit.")
#--------------------------------------------------------------------------------------------

    while True:
        user_text = listen(cfg, whisper_model, cfg['stt']['use_microphone'])
        
        # If the mic picked up nothing or it was just static, skip to next loop
        if not user_text.strip():
            continue
        
        
        
        if user_text.lower() in ['quit', 'exit']:
            log_event("SYSTEM", "=== CHAT SESSION ENDED ===\n")
            break
            
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