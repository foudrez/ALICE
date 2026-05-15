import cv2
import base64
import logging
import asyncio
from core.event_bus import EventBus

class CameraEngine:
    def __init__(self, bus: EventBus):
        self.bus = bus
        self.camera_index = 0 # Default webcam
        
        logging.info("[Eyes] Webcam module initialized.")
        self.bus.subscribe("USER_ASKED_ABOUT_ENVIRONMENT", self._capture_and_analyze)

    def _get_base64_frame(self) -> str:
        """Captures a single frame from the webcam and encodes it."""
        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            logging.error("[Eyes] Could not access webcam.")
            return ""

        ret, frame = cap.read()
        cap.release()

        if not ret:
            return ""

        # Resize to save token/bandwidth costs
        frame = cv2.resize(frame, (512, 512), interpolation=cv2.INTER_AREA)
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return base64.b64encode(buffer).decode('utf-8')

    async def _capture_and_analyze(self, query: str = "What do you see in the real world?"):
        logging.info("[Eyes] Looking through webcam...")
        b64_image = self._get_base64_frame()
        
        if b64_image:
            # Here you would pass it to your VLM (like LLaVA or GPT-4o Vision)
            description = "I see a person sitting at a desk looking at a monitor."
            logging.info(f"[Eyes] Camera observation: {description}")
            await self.bus.publish("CAMERA_CONTEXT_UPDATED", description)