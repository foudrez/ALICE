import torch
import logging

class HardwareHAL:
    """Hardware Abstraction Layer to auto-detect and manage compute resources."""
    
    def __init__(self):
        self.device = self._detect_device()
        self.vram = self._get_vram()
        logging.info(f"[HardwareHAL] System initialized on: {self.device.upper()} | VRAM: {self.vram}GB")

    def _detect_device(self) -> str:
        if torch.cuda.is_available():
            return "cuda"
        elif torch.backends.mps.is_available():
            return "mps" # Apple Silicon
        else:
            return "cpu"

    def _get_vram(self) -> float:
        if self.device == "cuda":
            return round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 2)
        return 0.0 # CPU/MPS shares RAM

    def get_optimal_execution_mode(self) -> dict:
        """Determines if heavy models can run locally based on hardware."""
        return {
            "device": self.device,
            "can_run_local_llm": self.vram >= 8.0 or self.device == "mps",
            "can_run_local_tts": self.device in ["cuda", "mps"],
            "use_quantization": self.vram < 12.0 if self.device == "cuda" else True
        }

hardware = HardwareHAL()