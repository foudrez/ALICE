<div align="center">

![A.L.I.C.E. Architecture](https://picsum.photos/seed/alice_dark_tech/1920/800)

<br>

# A.L.I.C.E.
### Autonomous Local Interactive Character Emulator

**A fully local AI voice assistant and VTuber character emulator featuring offline STT/TTS, contextual memory, and zero-latency interaction.**

</div>

<br>
<br>

## SYSTEM ARCHITECTURE & WORKFLOW

ALICE operates on a strict, offline modular architecture. The data flows sequentially from the user's microphone, through local inference engines, and back as synthesized audio.

| Phase | Subsystem | Technology | Description |
| :--- | :--- | :--- | :--- |
| **Input** | Hearing Engine | OpenAI Whisper | 100% offline speech-to-text with automatic silence detection and noise calibration. |
| **Processing** | Cognitive Core | Ollama / Llama.cpp | Local LLM inference that processes transcripts, formulates responses, and maintains long-term memory via `memory.txt`. |
| **Output** | Vocal Synthesis | GPT-SoVITS | High-fidelity, zero-shot voice cloning for emotional text-to-speech rendering. |

> **Workflow Diagram Placeholder**
> *[Microphone] ➔ [Whisper STT] ➔ [Ollama LLM] ➔ [GPT-SoVITS TTS] ➔ [Speaker]*

<br>
<br>

## DEPLOYMENT & INSTALLATION

The system requires Python 3.10 and a dedicated Nvidia GPU for optimal local inference performance.

### I. Environment Initialization

```bash
python -m venv .venv
.\.venv\Scripts\activate
```

### II. Core Dependencies

```bash
# Install Python Libraries
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install gpt_sovits_python[all] openai-whisper pyaudio pyyaml requests sounddevice soundfile

# Fetch the WebUI 3D Rendering Library (three-vrm)
curl -o three-vrm.js https://unpkg.com/@pixiv/three-vrm@3.3.5/lib/three-vrm.js
```

### III. System Patches

```bash
pip install transformers==4.46.3
pip install git+https://github.com/chameleon-ai/LangSegment-0.3.5-backup.git
python -c "import nltk; nltk.download('averaged_perceptron_tagger_eng'); nltk.download('cmudict')"
```

### IV. Model Placement

Download the GPT-SoVITS base models and place them in the `ALICE/pretrained_models/` directory. Update the explicit paths in `main.py` accordingly.

<br>
<br>

## CONFIGURATION & EXECUTION

### System Dashboard
The `config.yaml` file controls the entire runtime state.
- `llm`: Define the backend (Ollama/Llama.cpp) and inject the character prompt.
- `stt`: Toggle microphone state and adjust idle timeouts.
- `tts`: Assign reference audio paths and target speaker IDs.
- `system`: Managed autonomously by `hardware.py` on boot.

### Initialization Sequence

1. **Hardware Diagnostic:** Execute `python check_cuda.py` to verify GPU visibility.
2. **Audio Routing:** Execute `python check_audio.py` to identify hardware IDs, then append to `config.yaml`.
3. **Ignition:** 
   ```bash
   python brain.py
   ```

### Runtime Commands
- **Interact:** Speak naturally when the terminal indicates listening state.
- **Terminate:** State "Goodbye", "Exit", or "I'm going to bed" to trigger memory compression and graceful shutdown.

<br>
<br>

## REPOSITORY STRUCTURE

- `brain.py` — Main orchestrator handling STT and LLM logic.
- `main.py` — TTS engine managing GPU memory allocations and voice synthesis.
- `hardware.py` — Auto-configurator detecting CUDA and modifying YAML configurations.
- `check_audio.py` — Diagnostic utility for hardware identification.

<br>
<br>

---

<div align="center">
  <small>
    <b>REFERENCES & EXTERNAL REPOSITORIES</b><br>
    <a href="https://download.pytorch.org/whl/cu121">PyTorch CUDA Wheels</a> &nbsp; | &nbsp;
    <a href="https://github.com/tronghieuit/valtec-tts.git">Valtec-TTS Vietnamese Support</a> &nbsp; | &nbsp;
    <a href="https://huggingface.co/valtecAI-team/valtec-tts-pretrained">Valtec Pretrained Models</a> &nbsp; | &nbsp;
    <a href="https://huggingface.co/microsoft/bitnet-b1.58-2B-4T-gguf">BitNet 1.58 Models</a>
  </small>
</div>