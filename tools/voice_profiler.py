import os
import torch
from kokoro import KPipeline
import soundfile as sf

class VoiceProfiler:
    def __init__(self):
        # Base paths
        self.base_dir = os.path.join(os.path.dirname(__file__), "..", "assets", "tts", "base_voices")
        self.output_dir = os.path.join(os.path.dirname(__file__), "..", "assets", "tts", "voice_profiles")
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Initialize pipeline just for the text-to-audio generation testing
        self.pipeline = KPipeline(lang_code='a')

    def blend_voices(self, voice1_name: str, voice2_name: str, blend_ratio: float, output_name: str):
        print(f"[*] Blending {voice1_name} and {voice2_name} at a {blend_ratio} ratio...")
        
        v1_path = os.path.join(self.base_dir, f"{voice1_name}.pt")
        v2_path = os.path.join(self.base_dir, f"{voice2_name}.pt")
        
        if not os.path.exists(v1_path) or not os.path.exists(v2_path):
            print(f"[-] Error: Missing base voice files.")
            print(f"    Ensure {v1_path} and {v2_path} exist.")
            print("    Run 'python tools/download_voices.py' first!")
            return None
            
        try:
            # Load the raw tensors from disk safely
            v1 = torch.load(v1_path, weights_only=True)
            v2 = torch.load(v2_path, weights_only=True)
            
            # Tensor Math: Blend them!
            custom_voice = (v1 * blend_ratio) + (v2 * (1.0 - blend_ratio))
            
            # Save the new persona
            output_path = os.path.join(self.output_dir, f"{output_name}.pt")
            torch.save(custom_voice, output_path)
            print(f"[+] Success! New voice saved to {os.path.abspath(output_path)}")
            
            return custom_voice
            
        except Exception as e:
            print(f"[-] Failed to blend voices: {e}")
            return None

    def test_voice(self, voice_tensor, output_filename="test_output.wav"):
        print("[*] Generating test audio...")
        text = "Hello! I am ALICE. This is what my new blended voice sounds like. Do you like it?"
        
        generator = self.pipeline(text, voice=voice_tensor, speed=1.0)
        
        for i, (gs, ps, audio) in enumerate(generator):
            sf.write(output_filename, audio, 24000)
            print(f"[+] Test audio saved to {os.path.abspath(output_filename)}")
            break 

if __name__ == "__main__":
    print("=== ALICE Voice Profiler ===")
    profiler = VoiceProfiler()
    
    # 0.6 means 60% Bella, 40% Sarah
    custom_tensor = profiler.blend_voices("af_bella", "af_sarah", blend_ratio=0.6, output_name="alice2")
    
    if custom_tensor is not None:
        profiler.test_voice(custom_tensor)
        print("\n[!] Workflow Complete. Listen to test_output.wav!")