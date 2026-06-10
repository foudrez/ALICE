# Desktop AI Assistant: Architecture & Tech Stack Summary

This document summarizes the technical stack, system architecture, and the design rationale for the transparent desktop AI assistant. This overview is designed to be easily merged into broader project documentation (such as the `vrm-Control` repository).

---

## 1. High-Level Architecture
The system utilizes a decoupled, two-node architecture communicating locally over **OSC (Open Sound Control)** via UDP.
1. **The Brain (Backend):** A lightweight Python background process responsible for hardware input, screen capture, and all AI inference.
2. **The Shell (Frontend):** A Unity standalone application responsible exclusively for rendering the VRM avatar, handling transparent window logic, and executing animation state machines.

```mermaid
flowchart LR
    subgraph Python Backend (The Brain)
        SC[mss Screen Capture] --> LLM[Ollama LLaVA]
        MIC[Microphone Input] --> LLM
        LLM --> TTS[Silero TTS]
        LLM --> EMO[Emotion Parser]
        TTS --> OSC_TX[OSC Sender]
        EMO --> OSC_TX
    end

    subgraph Unity Frontend (The Shell)
        OSC_RX[OSC Receiver] --> Audio[AudioSource]
        OSC_RX --> Anim[Animator Controller]
        Audio --> LipSync[Blendshape Driver]
        Anim --> Render[Transparent VRM Window]
    end

    OSC_TX -- UDP Port 9000 --> OSC_RX
```

---

## 2. Tech Stack Details

### Python Backend ("The Brain")
*   **Language:** Python 3.10+
*   **Screen Capture:** `mss` (Chosen for extremely fast, cross-platform screenshot capability with minimal CPU overhead).
*   **Vision & Language Model:** `Ollama` running the `llava` (Large Language-and-Vision Assistant) model locally.
*   **Text-to-Speech (TTS):** `Silero TTS` (via PyTorch) for high-quality, completely offline voice generation.
*   **Networking:** `python-osc` for formatting and transmitting data to Unity.
*   **Hotkeys:** `keyboard` for global system-level push-to-talk triggers.

### Unity Frontend ("The Shell")
*   **Engine:** Unity (Standalone Desktop Build).
*   **Avatar Format:** `UniVRM` package for standardized importing of `.vrm` files, handling humanoid rigs, and spring bones.
*   **Window Management:** Custom C# scripts calling native Windows APIs (`SetWindowLong`, `DwmExtendFrameIntoClientArea`) to create a frameless, transparent, click-through desktop overlay.
*   **Networking:** `extOSC` (or basic UDP Client) to ingest emotion strings and audio triggers.

---

## 3. Design Rationale (Why this Stack?)

When merging this system with other projects or assessing its viability, the following design philosophies were prioritized:

### A. Strict Separation of Concerns (Python + Unity)
*   **Why not do everything in Unity?** Integrating cutting-edge AI (like PyTorch, local LLMs, and computer vision libraries) directly into Unity via C# is notoriously difficult, brittle, and lags behind the Python ecosystem.
*   **Why not do everything in Python?** Python lacks robust, hardware-accelerated 3D rendering engines capable of handling advanced VRM physics (Spring Bones) and complex animation blend trees.
*   **The Solution:** Splitting the logic allows the AI to run in its native environment (Python) while relying on an industry-standard game engine (Unity) to handle the visual output.

### B. Maximum Privacy and Zero Ongoing Costs
An assistant that actively monitors and screenshots your desktop poses a massive privacy risk if it relies on cloud APIs. By utilizing **Ollama (LLaVA)** and **Silero TTS**, 100% of the screen data, voice data, and text generation happens locally on the user's GPU. There are no API keys required, no subscription costs, and no data leaves the machine.

### C. Standardized Interoperability (OSC)
By using Open Sound Control (OSC) as the bridge between the backend and frontend, the architecture becomes highly modular:
*   The Python "Brain" can easily be pointed to drive an avatar in **VRChat**, Unreal Engine, or Godot without rewriting the AI logic.
*   The Unity "Shell" can be driven by a different backend (e.g., a Twitch chat script or a cloud-based API) simply by sending the same standardized OSC messages (e.g., `/avatar/emotion joy`).
