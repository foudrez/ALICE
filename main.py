import whisper
import types
import sounddevice as sd
import soundfile as sf
import io
from tools.load_config import load_config
from tools.detect_cuda import COMPUTE_DEVICE
from tools.auto_threehold import calibrate_mic
from memory.memory_manager import MemoryManager
from voice_process.stt import listen
from voice_process.tts import speak
from LLM_process.llm import generate_response
from tools.audio_output import output_audio
# -------------------------------------- MAIN ENTRY POINT --------------------------------------------------------------    
if __name__ == "__main__":
    cfg = load_config()
    mem = MemoryManager(history_limit=cfg['memory'].get('max_history', 10))
    
    # Load Whisper
    whisper_model = whisper.load_model(cfg['stt']['whisper_model'], device=COMPUTE_DEVICE, download_root="./models")
    
    # Calibrate
    mic_id = cfg['stt'].get('input_device_index')
    active_threshold = calibrate_mic(input_device=mic_id) if cfg['stt'].get('auto_calibrate') else 500
    
    print("ALICE Modular System Active.")
# -------------------------------------- MAIN LOOP -------------------------------------------------------------------
    while True:
        # Hearing
        user_text = listen(cfg, whisper_model, active_threshold, input_device=mic_id)
        if not user_text.strip(): continue

        # Thinking
        ai_response = generate_response(user_text, cfg, mem.get_history())
        print(f"ALICE: {ai_response}")
        
        mem.add_to_history("User", user_text)
        mem.add_to_history("ALICE", ai_response)
        
        # Speaking (Uses the new tool)
        result = speak(ai_response, cfg)
        output_audio(result, cfg)