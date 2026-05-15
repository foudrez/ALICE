import asyncio
import logging
import cv2
import numpy as np
import pyautogui
import time
from mss import mss
from core.event_bus import EventBus

# PyAutoGUI failsafe - move mouse to corner of screen to abort
pyautogui.FAILSAFE = True 
pyautogui.PAUSE = 0.01 # Minimal pause for fast execution

class MotorAgent:
    def __init__(self, bus: EventBus):
        self.bus = bus
        self.sct = mss()
        self.monitor = self.sct.monitors[1]
        self.is_playing = False
        self.current_game = None
        self.motor_task = None
        
        # Subscribe to high-level commands from the Brain
        self.bus.subscribe("START_GAMING", self.start_routine)
        self.bus.subscribe("STOP_GAMING", self.stop_routine)
        self.bus.subscribe("EXECUTE_GAME_MACRO", self._trigger_macro)

    async def start_routine(self, game_name: str):
        if self.is_playing:
            return
            
        self.is_playing = True
        self.current_game = game_name
        logging.info(f"[Motor] Hooking into {game_name} process. Zero-latency loop starting.")
        
        # Start the fast action loop based on the game
        if game_name.lower() == "osu!":
            self.motor_task = asyncio.create_task(self._osu_aim_loop())
        elif game_name.lower() == "minecraft":
            self.motor_task = asyncio.create_task(self._minecraft_nav_loop())
        else:
            logging.warning(f"[Motor] No specific heuristics built for {game_name}. Standing by.")

    async def stop_routine(self, _=None):
        self.is_playing = False
        if self.motor_task:
            self.motor_task.cancel()
        logging.info("[Motor] Controller disconnected. Hands off keyboard.")

    async def _trigger_macro(self, action: str):
        """Allows the LLM to trigger specific predefined sequences."""
        logging.info(f"[Motor] Executing macro: {action}")
        if action == "jump":
            pyautogui.press('space')
        elif action == "attack":
            pyautogui.click()
        elif action == "inventory":
            pyautogui.press('e')

    # --- GAME SPECIFIC HEURISTICS (The "Fast" Agents) ---

    async def _osu_aim_loop(self):
        """
        A high-speed loop (60+ FPS) that uses basic OpenCV thresholding
        to find circles and click them instantly, bypassing the LLM.
        """
        logging.info("[Motor] osu! heuristic loaded. Look for circles.")

        # [STUB] osu! template matching disabled - requires game-specific asset templates
        # To enable: (1) Create/obtain osu_hitcircle.png template (capture from in-game)
        # (2) Uncomment template loading line
        # (3) Uncomment matchTemplate and click logic
        # (4) Tune confidence threshold (0.8) based on game resolution
        # template = cv2.imread('assets/vision/template_images/osu_hitcircle.png', 0)

        while self.is_playing:
            # 1. Grab screen instantly
            img = np.array(self.sct.grab(self.monitor))
            gray = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)

            # 2. Fast computer vision logic (Template matching stub)
            # res = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
            # min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

            # if max_val > 0.8: # Confidence threshold
            #     target_x, target_y = max_loc
            #     pyautogui.moveTo(target_x, target_y, duration=0.01)
            #     pyautogui.click()

            # Yield control back to the async loop so we don't freeze the system
            await asyncio.sleep(0.016) # Roughly 60 ticks per second

    async def _minecraft_nav_loop(self):
        """
        A loop that handles WASD movement and block breaking,
        directed by the LLM's high-level goals.
        """
        logging.info("[Motor] Minecraft nav heuristic loaded.")

        # [STUB] Minecraft navigation incomplete - requires LLM-motor coordination
        # To enable: (1) Implement state machine for coordinated WASD control
        # (2) Add computer vision for lava/cliff detection
        # (3) Hook into LLM's movement commands via event bus
        # (4) Implement block detection and breaking logic

        while self.is_playing:
            # E.g., The LLM said "Move forward", so the motor agent holds 'W'
            # while constantly checking computer vision to avoid falling in lava.
            await asyncio.sleep(0.1)