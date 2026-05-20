import io
import os
import warnings
import logging
import soundfile as sf

from tools.detect_cuda import COMPUTE_DEVICE, IS_HALF_PRECISION
from gpt_sovits_python import TTS, TTS_Config

# --- SILENCE THE WARNINGS ---
warnings.filterwarnings("ignore", category=FutureWarning)
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
logging.getLogger("transformers").setLevel(logging.ERROR)

# ==========================================
# 1. INITIALIZE GPT-SOVITS (ENGLISH DEFAULT)
# ==========================================
sovits_config_dict = {
    "default": {
        "device": COMPUTE_DEVICE,
        "is_half": IS_HALF_PRECISION,
        "t2s_weights_path": "pretrained_models/s1bert25hz-2kh-longer-epoch=68e-step=50232.ckpt",
        "vits_weights_path": "pretrained_models/s2G488k.pth",
        "cnhuhbert_base_path": "pretrained_models/chinese-hubert-base",
        "bert_base_path": "pretrained_models/chinese-roberta-wwm-ext-large"
    }
}

print("Loading GPT-SoVITS (English) into memory...")
tts_config = TTS_Config(sovits_config_dict)
tts_pipeline = TTS(tts_config)


# ==========================================
# 3. THE ROUTER 
# ==========================================
def speak(target_text, config, lang="en"):
    """
    Routes the text to the correct engine based on the detected language.
    """
    
    # --- BRANCH B: ENGLISH (Default) ---
    is_streaming = config['tts'].get('streaming', False)
    
    params = {
        "text": target_text,
        "text_lang": "en",           
        "ref_audio_path": config['tts']['reference_audio_path'],
        "prompt_text": config['tts']['reference_prompt_text'],       
        "prompt_lang": "en",         
        "text_split_method": "cut5", 
        "batch_size": 1, 
        "speed_factor": 1.0,         
        "media_type": "wav",
        "streaming_mode": is_streaming
    }

    tts_generator = tts_pipeline.run(params)

    # Return as packets (Streaming) or a single file (Batch)
    if is_streaming:
        def chunk_generator():
            for sampling_rate, audio_chunk in tts_generator:
                buffer = io.BytesIO()
                sf.write(buffer, audio_chunk, sampling_rate, format='WAV')
                buffer.seek(0)
                yield buffer.read()
        return chunk_generator()
    else:
        sampling_rate, audio_data = next(tts_generator)
        buffer = io.BytesIO()
        sf.write(buffer, audio_data, sampling_rate, format='WAV')
        buffer.seek(0)
        return buffer.read()