import sounddevice as sd 
from gpt_sovits_python import TTS, TTS_Config
# 1. Define Model Paths an d Hardware
# Update the paths below to point to the models inside your GPT-SoVITS folder
sovits_config = {
    "default": {
        "device": "cpu",  # Change to "cuda" if you have a compatible GPU and want faster inference
        "is_half": False,  # Set to False if using "cpu"
        "t2s_weights_path": "GPT_SoVITS/pretrained_models/s1bert25hz-2kh-longer-epoch=68e-step=50232.ckpt",
        "vits_weights_path": "GPT_SoVITS/pretrained_models/s2G488k.pth",
        "cnhuhbert_base_path": "GPT_SoVITS/pretrained_models/chinese-hubert-base", # <-- Typo added here
        "bert_base_path": "GPT_SoVITS/pretrained_models/chinese-roberta-wwm-ext-large"
    }
}

print("Loading models into memory...")
tts_config = TTS_Config(sovits_config)
tts_pipeline = TTS(tts_config)

def speak(target_text):
    params = {
        "text": target_text,                     # <-- We pass the new text here
        "text_lang": "en",           
        "ref_audio_path": "charvoice\silverworf\VO_Archive_Silver_Wolf_16.ogg", # Put your trimmed audio path here
        "prompt_text": "I heard that no one has been able to find out where she lives? One day, I'll definitely break that myth", # Put your reference text here
        "prompt_lang": "en",         
        "text_split_method": "cut5", 
        "batch_size": 1, 
        "speed_factor": 1.0,         
        "media_type": "wav",
        "streaming_mode": False      
    }

    print(f"Generating audio for: '{target_text}'")
    tts_generator = tts_pipeline.run(params)
    sampling_rate, audio_data = next(tts_generator)

    print("Playing audio...")
    sd.play(audio_data, sampling_rate)
    sd.wait()
    
if __name__ == "__main__":
    # Example usage
    target_text = "Hello, this is a test of the GPT-SoVITS text-to-speech system."
    speak(target_text)