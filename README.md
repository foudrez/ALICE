# A.L.I.C.E. - Autonomous Local Interactive Character Emulator

ALICE is a fully local, voice-to-voice virtual assistant. She features a modular architecture that separates "Hearing" (Whisper), "Thinking" (Ollama/Llama.cpp), and "Speaking" (GPT-SoVITS), all while maintaining long-term memory of your conversations.

## ✨ Core Features

* **🧠 Contextual Memory:** Automatically summarizes and archives conversation highlights to `memory.txt` to remember facts about you indefinitely.
* **🎙️ Pure Whisper STT:** 100% offline speech recognition with automatic silence detection and noise calibration.
* **🗣️ Cloned TTS:** Powered by GPT-SoVITS for emotional, high-fidelity voice synthesis.
* **⚙️ Auto-Hardware Detection:** On startup, the system detects your GPU/CPU and rewrites `config.yaml` to optimize performance.
* **🎮 Idle Animations:** ALICE will get impatient and speak to you if you stay silent for too long.

---

## 🛠️ Installation & Setup

### 1. Environment & Dependencies
Ensure you have **Python 3.10** and an **Nvidia GPU** (optional, but recommended).

```bash
# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\activate

# Install core libraries
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install gpt_sovits_python[all] openai-whisper pyaudio pyyaml requests sounddevice soundfile

# Apply critical dependency fixes
pip install transformers==4.46.3
pip install git+https://github.com/chameleon-ai/LangSegment-0.3.5-backup.git

# Download NLTK data
python -c "import nltk; nltk.download('averaged_perceptron_tagger_eng'); nltk.download('cmudict')"
```

### 2. Model Placement
Download the GPT-SoVITS base models and place them in `ALICE/pretrained_models/`. Update the paths in `main.py` accordingly.

---

## ⚙️ Configuration (`config.yaml`)

The `config.yaml` acts as the master dashboard. You can toggle features and change ALICE's personality here:

* **`llm`**: Set your backend (Ollama/Llama.cpp) and your character prompt.
* **`stt`**: Toggle `use_microphone` and adjust `idle_timeout`.
* **`tts`**: Set your reference audio and target speaker ID.
* **`system`**: Automatically updated by `hardware.py` on boot.

---

## 🚀 Usage

1.  **Hardware Check:** Run `python check_cuda.py` to ensure your GPU is visible.
2.  **Audio Routing:** Run `python check_audio.py` to find your Microphone and Speaker IDs, then paste them into `config.yaml`.
3.  **Start ALICE:**
    ```bash
    python brain.py
    ```

### Terminal Commands
* **Talk:** Simply speak when the prompt says `[🎙️ ALICE is listening...]`.
* **Exit:** Say "Goodbye", "Exit", or "I'm going to bed" to trigger the memory compression and shutdown.

---

## 📁 Project Structure

* `brain.py`: The main orchestrator. Handles STT and LLM logic.
* `main.py`: The TTS engine. Manages GPU memory and voice synthesis.
* `hardware.py`: The auto-configurator. Detects CUDA and manages YAML settings.
* `check_audio.py`: Diagnostic tool for finding hardware IDs.