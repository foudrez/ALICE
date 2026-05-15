import asyncio
import logging
import base64
import cv2
import numpy as np
from mss import mss
from core.event_bus import EventBus
from core.hardware_hal import hardware

# In a full implementation, you would import the Llama-CPP Vision handler:
# from llama_cpp import Llama
# from llama_cpp.llama_chat_format import Llava15ChatHandler

class VisionEngine:
    def __init__(self, bus: EventBus):
        self.bus = bus
        self.sct = mss()  # High-speed screen capture
        self.monitor = self.sct.monitors[1]  # Capture primary monitor
        self.is_watching = False
        self.vision_loop_task = None
        
        # NOTE: To run this locally, you need a multimodal model like LLaVA 1.5 7B (.gguf)
        self.model_path = "assets/llm/vision_llava_7b.gguf"
        logging.info(f"[Eyes] Initializing Vision Engine on {hardware.device}...")
        
        # self.chat_handler = Llava15ChatHandler(clip_model_path="assets/llm/mmproj-model-f16.gguf")
        # self.vlm = Llama(model_path=self.model_path, chat_handler=self.chat_handler, n_gpu_layers=-1)

        # Listen for commands to open/close her eyes
        self.bus.subscribe("START_LOOKING", self.start_watching)
        self.bus.subscribe("STOP_LOOKING", self.stop_watching)
        self.bus.subscribe("USER_ASKED_ABOUT_SCREEN", self._analyze_current_screen)

    def _capture_and_compress(self) -> str:
        """Captures the screen, resizes it to save VRAM, and encodes to base64."""
        # 1. Grab raw screen data
        raw_img = self.sct.grab(self.monitor)
        img_np = np.array(raw_img)
        
        # 2. Convert BGRA to RGB
        img_rgb = cv2.cvtColor(img_np, cv2.COLOR_BGRA2RGB)
        
        # 3. Downscale for the VLM (LLaVA prefers 336x336 or similar multiples)
        # We shrink it to a max width of 512px to maintain aspect ratio but drop file size
        scale_percent = 512 / img_rgb.shape[1]
        width = int(img_rgb.shape[1] * scale_percent)
        height = int(img_rgb.shape[0] * scale_percent)
        resized = cv2.resize(img_rgb, (width, height), interpolation=cv2.INTER_AREA)
        
        # 4. Encode to JPEG, then Base64
        _, buffer = cv2.imencode('.jpg', cv2.cvtColor(resized, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 80])
        b64_image = base64.b64encode(buffer).decode('utf-8')
        
        return f"data:image/jpeg;base64,{b64_image}"

    async def _analyze_current_screen(self, query: str = "Describe what is happening on the screen briefly."):
        """Takes a snapshot and asks the VLM to interpret it."""
        logging.info("[Eyes] Capturing screen for analysis...")
        b64_img = self._capture_and_compress()

        # [STUB] VLM inference disabled - multimodal model not downloaded
        # To enable: (1) Download llava-7b.gguf and mmproj-model-f16.gguf to assets/llm/
        # (2) Uncomment the Llama imports at top of file
        # (3) Uncomment the model initialization lines in __init__
        # (4) Uncomment the response code below
        # response = self.vlm.create_chat_completion(
        #     messages=[
        #         {"role": "system", "content": "You are ALICE. You are looking at the user's screen."},
        #         {"role": "user", "content": [
        #             {"type": "image_url", "image_url": {"url": b64_img}},
        #             {"type": "text", "text": query}
        #         ]}
        #     ]
        # )
        # description = response["choices"][0]["message"]["content"]

        # Using mock data instead
        await asyncio.sleep(1)
        description = "[MOCK] I see a code editor open with a Python script, and a web browser showing documentation."
        logging.warning(f"[Eyes] USING MOCK VISION - Real VLM inference disabled. Output: {description}")

        # Inject this description into ALICE's working memory via the bus
        await self.bus.publish("SCREEN_CONTEXT_UPDATED", description)

    async def start_watching(self, interval_seconds: int = 10):
        """Starts a background loop where ALICE periodically checks the screen."""
        if self.is_watching:
            return
            
        self.is_watching = True
        logging.info("[Eyes] Active vision loop started.")
        
        async def watch_loop():
            while self.is_watching:
                await self._analyze_current_screen("What game is the user playing, or what app are they using?")
                await asyncio.sleep(interval_seconds)
                
        self.vision_loop_task = asyncio.create_task(watch_loop())

    async def stop_watching(self, _=None):
        self.is_watching = False
        if self.vision_loop_task:
            self.vision_loop_task.cancel()
        logging.info("[Eyes] Vision loop stopped.")