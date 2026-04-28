import sounddevice as sd 
from gpt_sovits_python import TTS, TTS_Config
import os
import warnings
import logging
import io
import soundfile as sf
from tools.detect_cuda import COMPUTE_DEVICE, IS_HALF_PRECISION
from tools.load_config import load_config
# --- 1. SILENCE THE WARNINGS ---
# Block PyTorch's annoying FutureWarnings
warnings.filterwarnings("ignore", category=FutureWarning)

# Block Hugging Face Transformers warnings (force it to only show critical errors)
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
logging.getLogger("transformers").setLevel(logging.ERROR)


config = load_config()
# 1. Define Model Paths an d Hardware
# Update the paths below to point to the models inside your GPT-SoVITS folder
sovits_config = {
    "default": {
        "device": COMPUTE_DEVICE,  # Change to "cuda" if you have a compatible GPU and want faster inference
        "is_half": IS_HALF_PRECISION,  # Set to False if using "cpu"
        "t2s_weights_path": "pretrained_models/s1bert25hz-2kh-longer-epoch=68e-step=50232.ckpt",
        "vits_weights_path": "pretrained_models/s2G488k.pth",
        "cnhuhbert_base_path": "pretrained_models/chinese-hubert-base", # <-- Typo added here
        "bert_base_path": "pretrained_models/chinese-roberta-wwm-ext-large"
    }
}

print("Loading models into memory...")
tts_config = TTS_Config(sovits_config)
tts_pipeline = TTS(tts_config)

def speak(target_text, config):
    # Pull params from config
    ref_audio = config['tts']['reference_audio_path']
    ref_text = config['tts']['reference_prompt_text']
    is_streaming = config['tts'].get('streaming', False)
    params = {
        "text": target_text,
        "text_lang": "en",           
        "ref_audio_path": ref_audio,
        "prompt_text": ref_text,       
        "prompt_lang": "en",         
        "text_split_method": "cut5", 
        "batch_size": 1, 
        "speed_factor": 1.0,         
        "media_type": "wav",
        "streaming_mode": is_streaming # <-- Now dynamic
    }

    tts_generator = tts_pipeline.run(params)

    if is_streaming:
        # RETURN A GENERATOR: Yields tiny audio chunks as they are ready
        def chunk_generator():
            for sampling_rate, audio_chunk in tts_generator:
                buffer = io.BytesIO()
                sf.write(buffer, audio_chunk, sampling_rate, format='WAV')
                buffer.seek(0)
                yield buffer.read()
        return chunk_generator()
    else:
        # RETURN BYTES: Gets the full sentence at once
        sampling_rate, audio_data = next(tts_generator)
        buffer = io.BytesIO()
        sf.write(buffer, audio_data, sampling_rate, format='WAV')
        buffer.seek(0)
        return buffer.read()
    
'''__name__ == "__main__":
    # Example usage
    target_text = "Hello, this is a test of the GPT-SoVITS text-to-speech system."
    speak(target_text)'''