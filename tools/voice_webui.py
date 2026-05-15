import gradio as gr
import os
import torch
import soundfile as sf
import numpy as np
import urllib.request
from threading import Thread
from kokoro import KPipeline

# ==========================================
# 1. KOKORO VOICE DATABASE & DESCRIPTIONS
# ==========================================
VOICE_DATABASE = {
    # American Female
    "af_alloy": "American Female - Clean, articulate, studio-quality",
    "af_aoede": "American Female - Broadcaster, professional, authoritative",
    "af_bella": "American Female - Soft, friendly, warm, conversational",
    "af_jessica": "American Female - Expressive, upbeat, casual",
    "af_kore": "American Female - Calm, soothing, slightly deep",
    "af_nicole": "American Female - Whispery, slightly raspy, intimate",
    "af_nova": "American Female - Bright, energetic, youthful",
    "af_river": "American Female - Confident, clear, slightly robotic",
    "af_sarah": "American Female - Serious, news-anchor style",
    "af_sky": "American Female - Breathy, light, very casual",
    
    # American Male
    "am_adam": "American Male - Deep, resonant, announcer",
    "am_echo": "American Male - Smooth, conversational, friendly",
    "am_eric": "American Male - High energy, upbeat, YouTuber style",
    "am_fenrir": "American Male - Gruff, rough, intense",
    "am_liam": "American Male - Young, casual, modern",
    "am_michael": "American Male - Professional, corporate, clear",
    "am_onyx": "American Male - Very deep, cinematic, authoritative",
    "am_puck": "American Male - Expressive, animated, character-like",
    "am_santa": "American Male - Booming, older, joyful",
    
    # British Female
    "bf_alice": "British Female - Clear, posh, BBC style",
    "bf_amma": "British Female - Warm, mature, comforting",
    "bf_emma": "British Female - Young, bright, modern RP",
    "bf_isabella": "British Female - Soft, elegant, refined",
    "bf_lily": "British Female - Casual, upbeat, friendly",
    
    # British Male
    "bm_daniel": "British Male - Authoritative, newsreader, deep",
    "bm_fable": "British Male - Storyteller, expressive, mid-tone",
    "bm_george": "British Male - Casual, conversational, modern",
    "bm_lewis": "British Male - Energetic, sports-commentator style"
}

class VoiceStudio:
    def __init__(self):
        # Setup directories
        self.base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "tts", "base_voices"))
        self.output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "tts", "voice_profiles"))
        os.makedirs(self.base_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        
        print("[Voice Studio] Booting Kokoro Pipelines (American & British)...")
        # Initialize both pipelines so we can preview all voices
        self.pipeline_a = KPipeline(lang_code='a')
        self.pipeline_b = KPipeline(lang_code='b')

    # ==========================================
    # LOGIC FUNCTIONS
    # ==========================================
    def get_downloaded_voices(self):
        """Scans the disk for downloaded .pt files."""
        downloaded = [f.replace('.pt', '') for f in os.listdir(self.base_dir) if f.endswith('.pt')]
        return sorted(downloaded) if downloaded else []

    def get_description(self, voice_name):
        """Returns the description of the selected voice."""
        if not voice_name:
            return "No voice selected."
        return VOICE_DATABASE.get(voice_name, "Custom or unknown voice profile.")

    def download_all_voices(self, progress=gr.Progress()):
        """Downloads all missing voices from the Hugging Face repo."""
        base_url = "https://huggingface.co/hexgrad/Kokoro-82M/resolve/main/voices/{}.pt"
        total = len(VOICE_DATABASE)
        
        for i, voice in enumerate(VOICE_DATABASE.keys()):
            save_path = os.path.join(self.base_dir, f"{voice}.pt")
            if not os.path.exists(save_path):
                progress((i, total), desc=f"Downloading {voice}...")
                try:
                    urllib.request.urlretrieve(base_url.format(voice), save_path)
                except Exception as e:
                    print(f"Failed to download {voice}: {e}")
                    
        return "✅ Library Sync Complete! All official base voices downloaded.", gr.update(choices=self.get_downloaded_voices())

    def play_sample(self, voice_name):
        """Generates a quick audio sample for a base voice."""
        if not voice_name:
            return None
            
        path = os.path.join(self.base_dir, f"{voice_name}.pt")
        if not os.path.exists(path):
            return None
            
        try:
            tensor = torch.load(path, weights_only=True)
            pipeline = self.pipeline_b if voice_name.startswith('b') else self.pipeline_a
            
            text = f"Hello. My designation is {voice_name}. This is a sample of my vocal parameters."
            generator = pipeline(text, voice=tensor, speed=1.0)
            
            audio_chunks = [audio for _, _, audio in generator]
            final_audio = np.concatenate(audio_chunks)
            
            temp_path = os.path.join(self.output_dir, f"temp_{voice_name}_sample.wav")
            sf.write(temp_path, final_audio, 24000)
            return temp_path
        except Exception as e:
            print(f"Sample generation failed: {e}")
            return None

    def blend_and_test(self, v1, v2, ratio, output_name, test_text):
        """Blends two voices and generates test audio."""
        if not v1 or not v2:
            return "❌ Please select both Voice A and Voice B.", None

        try:
            tensor1 = torch.load(os.path.join(self.base_dir, f"{v1}.pt"), weights_only=True)
            tensor2 = torch.load(os.path.join(self.base_dir, f"{v2}.pt"), weights_only=True)
            
            # Blend
            custom_voice = (tensor1 * ratio) + (tensor2 * (1.0 - ratio))
            
            # Save
            safe_name = output_name.strip().replace(" ", "_") or "alice_v1"
            save_path = os.path.join(self.output_dir, f"{safe_name}.pt")
            torch.save(custom_voice, save_path)
            
            # Test
            # Use pipeline A by default for custom mixed voices
            generator = self.pipeline_a(test_text, voice=custom_voice, speed=1.0)
            audio_chunks = [audio for _, _, audio in generator]
            final_audio = np.concatenate(audio_chunks)
            
            test_file = os.path.join(self.output_dir, f"{safe_name}_test.wav")
            sf.write(test_file, final_audio, 24000)
            
            return f"✅ Blended & Saved as {safe_name}.pt\nUpdate system.yaml to use this file.", test_file
            
        except Exception as e:
            return f"❌ Error: {str(e)}", None

    # ==========================================
    # GRADIO UI (1-Page Layout)
    # ==========================================
    def launch(self):
        # We use a custom JS script to force Dark Mode on load
        dark_mode_js = """
        function refresh() {
            const url = new URL(window.location);
            if (url.searchParams.get('__theme') !== 'dark') {
                url.searchParams.set('__theme', 'dark');
                window.location.href = url.href;
            }
        }
        """

        # Using the Monchrome theme for a sleek, terminal-like appearance
        with gr.Blocks(theme=gr.themes.Monochrome(), js=dark_mode_js, title="ALICE Voice Forge") as ui:
            gr.Markdown("# 🎙️ A.L.I.C.E. Voice Forge (Kokoro)")
            gr.Markdown("Download base voices, preview their personalities, and blend them into a unique identity.")
            
            downloaded = self.get_downloaded_voices()

            # --- SECTION 1: LIBRARY MANAGER ---
            with gr.Group():
                gr.Markdown("### 📚 1. Library Manager")
                with gr.Row():
                    dl_btn = gr.Button("⬇️ Download / Sync All Official Base Voices", variant="secondary")
                    dl_status = gr.Textbox(label="System Status", value=f"{len(downloaded)} / {len(VOICE_DATABASE)} voices currently cached on disk.", interactive=False)

            gr.HTML("<hr>")

            # --- SECTION 2: BASE VOICE EXPLORER ---
            gr.Markdown("### 🔍 2. Preview Base Voices")
            with gr.Row():
                with gr.Column(scale=1):
                    v1_dropdown = gr.Dropdown(choices=downloaded, label="Voice A (Primary)", value=downloaded[0] if downloaded else None)
                    v1_desc = gr.Textbox(label="Personality Description", value=self.get_description(downloaded[0] if downloaded else None), interactive=False)
                    v1_play_btn = gr.Button("▶️ Generate Sample A")
                    v1_audio = gr.Audio(label="Sample A", interactive=False)

                with gr.Column(scale=1):
                    v2_dropdown = gr.Dropdown(choices=downloaded, label="Voice B (Secondary)", value=downloaded[1] if len(downloaded)>1 else None)
                    v2_desc = gr.Textbox(label="Personality Description", value=self.get_description(downloaded[1] if len(downloaded)>1 else None), interactive=False)
                    v2_play_btn = gr.Button("▶️ Generate Sample B")
                    v2_audio = gr.Audio(label="Sample B", interactive=False)

            gr.HTML("<hr>")

            # --- SECTION 3: THE FORGE ---
            gr.Markdown("### 🧬 3. The Forge (Blend & Export)")
            with gr.Row():
                with gr.Column(scale=2):
                    ratio_slider = gr.Slider(minimum=0.0, maximum=1.0, value=0.6, step=0.05, 
                                             label="Blend Ratio", info="1.0 = 100% Voice A | 0.0 = 100% Voice B | 0.5 = Perfect Split")
                    test_text = gr.Textbox(label="Test Phrase", value="Hello there. My name is ALICE. I am an Artificial Local Intelligence and Conversational Entity.")
                    output_name = gr.Textbox(label="Save Profile As", value="alice_v1")
                    blend_btn = gr.Button("🔥 Forge ALICE's Voice", variant="primary")
                
                with gr.Column(scale=1):
                    blend_status = gr.Textbox(label="Forge Status", interactive=False)
                    blend_audio = gr.Audio(label="Final Voice Result", interactive=False)

            # --- EVENT LISTENERS ---
            dl_btn.click(fn=self.download_all_voices, outputs=[dl_status, v1_dropdown])
            dl_btn.click(fn=self.download_all_voices, outputs=[dl_status, v2_dropdown])

            v1_dropdown.change(fn=self.get_description, inputs=v1_dropdown, outputs=v1_desc)
            v2_dropdown.change(fn=self.get_description, inputs=v2_dropdown, outputs=v2_desc)

            v1_play_btn.click(fn=self.play_sample, inputs=v1_dropdown, outputs=v1_audio)
            v2_play_btn.click(fn=self.play_sample, inputs=v2_dropdown, outputs=v2_audio)

            blend_btn.click(
                fn=self.blend_and_test,
                inputs=[v1_dropdown, v2_dropdown, ratio_slider, output_name, test_text],
                outputs=[blend_status, blend_audio]
            )

        # Launch on port 7861 so it doesn't conflict with ALICE's main dashboard
        ui.launch(server_name="127.0.0.1", server_port=7861, inbrowser=True)

if __name__ == "__main__":
    studio = VoiceStudio()
    studio.launch()