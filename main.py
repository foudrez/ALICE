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

if __name__ == "__main__":
    cfg = load_config()
    mem = MemoryManager(history_limit=cfg['memory'].get('max_history', 10))
    
    print(f"Loading Whisper on {COMPUTE_DEVICE}...")
    whisper_model = whisper.load_model(cfg['stt']['whisper_model'], device=COMPUTE_DEVICE, download_root="./models")
    
    mic_id = cfg['stt'].get('input_device_index')
    active_threshold = 500
    if cfg['stt'].get('auto_calibrate'):
        active_threshold = calibrate_mic(input_device=mic_id)
        
    print("ALICE Terminal Session Started.")

    while True:
        user_text = listen(cfg, whisper_model, active_threshold, input_device=mic_id)
        
        if user_text == "[IDLE_TICK]":
            user_text = "continue the conversation... [System: User is idle, complain to them]"

        if not user_text.strip(): continue
        
        # Thinking logic
        ai_response = generate_response(user_text, cfg, mem.get_history())
        print(f"ALICE: {ai_response}")
        
        mem.add_to_history("User", user_text)
        mem.add_to_history("ALICE", ai_response)
        
        # Handling Dynamic Playback (Local)
        result = speak(ai_response, cfg)
        
        if isinstance(result, types.GeneratorType):
            for chunk_bytes in result:
                data, fs = sf.read(io.BytesIO(chunk_bytes))
                sd.play(data, fs)
                sd.wait() # In CLI, we wait for audio to finish before next loop
        else:
            data, fs = sf.read(io.BytesIO(result))
            sd.play(data, fs)
            sd.wait()