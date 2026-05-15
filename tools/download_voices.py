import os
import urllib.request
import json

def download_kokoro_voices():
    save_dir = os.path.join(os.path.dirname(__file__), "..", "assets", "tts", "base_voices")
    os.makedirs(save_dir, exist_ok=True)

    # Comprehensive library of Kokoro v0.19 voices and their descriptions
    voice_library = {
        "af_bella": "American Female - Soft, friendly, warm",
        "af_nicole": "American Female - Slightly raspy, whispery",
        "af_sarah": "American Female - Confident, clear announcer",
        "af_sky": "American Female - Bright, energetic, youthful",
        "af_alloy": "American Female - Neutral, balanced",
        "af_aoede": "American Female - Smooth, calm, soothing",
        "af_heart": "American Female - Warm, gentle, caring",
        "af_jessica": "American Female - Casual, conversational",
        "af_kore": "American Female - Light, soft, delicate",
        "af_nova": "American Female - Professional, articulate",
        "af_river": "American Female - Upbeat, friendly, chipper",
        "am_adam": "American Male - Clear, deep, narrator",
        "am_michael": "American Male - Professional, crisp",
        "am_onyx": "American Male - Very deep, cinematic, authoritative",
        "am_puck": "American Male - Energetic, youthful",
        "am_echo": "American Male - Friendly, neutral, approachable",
        "am_eric": "American Male - Conversational, relaxed",
        "am_fenrir": "American Male - Gruff, mature, textured",
        "am_liam": "American Male - Young, energetic student",
        "am_santa": "American Male - Jolly, booming, deep",
        "bf_alice": "British Female - Proper, clear, crisp",
        "bf_aria": "British Female - Soft, pleasant, melodic",
        "bf_emma": "British Female - Professional, warm, reliable",
        "bf_isabella": "British Female - Bright, youthful, fast",
        "bm_daniel": "British Male - Authoritative, deep, news",
        "bm_fable": "British Male - Storyteller, calm, wise",
        "bm_george": "British Male - Proper, conversational",
        "bm_lewis": "British Male - Young, casual, modern"
    }

    base_url = "https://huggingface.co/hexgrad/Kokoro-82M/resolve/main/voices/{}.pt"

    print(f"=== Downloading 28 Kokoro Voice Tensors ===")
    print(f"Destination: {os.path.abspath(save_dir)}\n")

    # 1. Download the Voice Tensors
    for voice in voice_library.keys():
        url = base_url.format(voice)
        save_path = os.path.join(save_dir, f"{voice}.pt")
        
        if os.path.exists(save_path):
            print(f"[~] Skipping {voice}.pt (Already exists)")
            continue
            
        print(f"[*] Downloading {voice}.pt...")
        try:
            urllib.request.urlretrieve(url, save_path)
            print(f"[+] Successfully saved {voice}.pt")
        except Exception as e:
            print(f"[-] Failed to download {voice}: {e}")

    # 2. Save the Metadata for the WebUI
    metadata_path = os.path.join(save_dir, "metadata.json")
    with open(metadata_path, "w") as f:
        json.dump(voice_library, f, indent=4)
    print(f"\n[+] Metadata saved to {metadata_path}")
    print("=== Download Complete! ===")

if __name__ == "__main__":
    download_kokoro_voices()