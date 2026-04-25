import sounddevice as sd 
from gpt_sovits_python import TTS, TTS_Config
import os
import warnings
import logging

from tools.detect_cuda import COMPUTE_DEVICE, IS_HALF_PRECISION

# --- 1. SILENCE THE WARNINGS ---
# Block PyTorch's annoying FutureWarnings
warnings.filterwarnings("ignore", category=FutureWarning)

# Block Hugging Face Transformers warnings (force it to only show critical errors)
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
logging.getLogger("transformers").setLevel(logging.ERROR)



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

def speak(target_text, ref_audio_path, prompt_text, output_device=None):
    params = {
        "text": target_text,
        "text_lang": "en",           
        "ref_audio_path": ref_audio_path, # <-- Now comes from config
        "prompt_text": prompt_text,       # <-- Now comes from config
        "prompt_lang": "en",         
        "text_split_method": "cut5", 
        "batch_size": 1, 
        "speed_factor": 1.0,         
        "media_type": "wav",
        "streaming_mode": False      
    }

    tts_generator = tts_pipeline.run(params)
    sampling_rate, audio_data = next(tts_generator)
    # Tell sounddevice which speaker to use right before playing
    if output_device is not None:
        sd.default.device[1] = output_device # [1] targets the output device
        
    print("Playing audio...")
    sd.play(audio_data, sampling_rate, device=output_device)
    sd.wait()
    
'''__name__ == "__main__":
    # Example usage
    target_text = "Hello, this is a test of the GPT-SoVITS text-to-speech system."
    speak(target_text)'''