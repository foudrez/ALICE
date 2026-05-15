# 🧠 Project A.L.I.C.E.
**Artificial Local Intelligence & Conversational Entity**

A production-ready, open-source AI Operating System and Virtual Avatar framework. ALICE is designed to be a completely autonomous digital entity capable of listening, thinking, speaking, and interacting with the physical and digital world in real-time.

Inspired by architectures like *Neuro-sama* and *Project BEA*, ALICE runs a decoupled, asynchronous Event Bus that allows her to parse computer vision, control smart home devices, and maintain long-term memory without blocking her real-time conversational capabilities.

---

## ✨ Core Features
* **🧠 Decoupled Event-Bus Architecture:** Think, listen, and act simultaneously.
* **🗣️ Sub-second Voice Cloning:** Powered by **Kokoro-82M**, allowing for zero-latency, highly emotive, and customizable voice profiles.
* **👁️ Vision & Actuation:** Hooks into computer vision (VLM/OpenCV) to watch your screen or webcam, and uses the **Motor Agent** to play games like Minecraft.
* **💾 3-Tier Memory System (SEAL):** Short-term RAM, ChromaDB semantic vector storage, and an autonomous background "Reflection" engine that permanently rewrites her source persona based on your interactions.
* **🏠 Agentic Limbs:** Built-in tools for DuckDuckGo web scraping and Home Assistant (IoT) manipulation via the Model Context Protocol (MCP).
* **🎭 Avatar Integration:** Streams JSON viseme (mouth shapes) and emotion tags over a local WebSocket to 3D VRM rendering engines (like VTube Studio or Three.js).

---

## 🗂️ Directory Structure
```text
ALICE/
│── run.py                          # 🚀 THE IGNITION SWITCH
│── test_diagnostics.py             # Pre-flight system check
├── core/                           # 🧠 Message Bus & Hardware Orchestration
├── config/                         # ⚙️ System Settings & Identity (YAML/.env)
├── memory/                         # 💭 ChromaDB & SEAL Reflection Engine
├── modules/                        # 🧩 Senses (Llama.cpp, Whisper, Kokoro, LLaVA)
├── subsystems/                     # 🦾 Limbs (Gaming Motor, IoT, Web Search)
├── interfaces/                     # 🔌 Bodies (Mic/Speaker, Discord, VRM WebSocket)
├── tools/                          # 🛠️ Utilities (Voice Studio WebUI)
└── webui/                          # 🎛️ Gradio Control Dashboard


🚀 Quick Start Guide
1. Install Dependencies
Ensure you have Python 3.11+ installed. Create a virtual environment and install the required packages:

Bash
python -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
pip install torch torchvision torchaudio --index-url [https://download.pytorch.org/whl/cu118](https://download.pytorch.org/whl/cu118)
pip install -r requirements.txt
(Note: You must also install FFmpeg on your operating system for audio processing).

2. Configure Environment
Rename config/openfang.toml.example to config/system.yaml (or just edit the existing YAML).

Create a config/.env file and add any necessary keys (e.g., DISCORD_TOKEN, OPENAI_API_KEY).

3. Forge a Voice
Download the base voice models and launch the Voice Studio to mix a custom persona for ALICE:

Bash
python tools/download_voices.py
python tools/voice_studio.py
Open http://127.0.0.1:7861 to blend her voice and save it as alice_custom.pt.

4. Run Diagnostics
Check your hardware and ensure all components are wired correctly:

Bash
python test_diagnostics.py
5. Ignite the Matrix
Launch the central orchestrator. This will boot the LLM, start the web dashboard, and connect the microphone/Discord interfaces.

Bash
python run.py
Open http://127.0.0.1:7860 to view ALICE's internal thoughts and toggle subsystems.

🛡️ License & Acknowledgements
Built natively for local execution to prioritize privacy, zero-latency execution, and hardware ownership. Portions of this architecture are inspired by the open-source embodied AI community.

