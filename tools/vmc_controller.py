import time
import math
import threading
import audioop
import pyaudio
from pythonosc import udp_client

class VMCController:
    def __init__(self, mic_id=None, ip="127.0.0.1", port=39539):
        """
        Initializes the VMC (Virtual Motion Capture) Protocol controller.
        Port 39539 is the default for VSeeFace and Warudo receivers.
        """
        self.ip = ip
        self.port = port
        self.client = udp_client.SimpleUDPClient(self.ip, self.port)
        
        self.mic_name_fragment = mic_id
        self.is_running = False
        
        # --- SMOOTHING VARIABLES ---
        self.current_mouth = 0.0
        self.target_mouth = 0.0
        self.smoothing_speed = 0.25 # Lower = smoother/slower, Higher = snappier
        
        # --- ANIMATION STATE ---
        self.start_time = time.time()
        self.next_blink = self.start_time + 3.0
        self.is_blinking = False

    def _get_device_index(self, p):
        if not self.mic_name_fragment:
            return None
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if self.mic_name_fragment.lower() in info['name'].lower() and info['maxInputChannels'] > 0:
                return i
        return None

    def start(self):
        if self.is_running: return
        self.is_running = True
        
        # We split the brain into two threads: One listens to audio, one renders frames at 60fps
        threading.Thread(target=self._audio_analysis_loop, daemon=True).start()
        threading.Thread(target=self._vmc_animation_loop, daemon=True).start()
        print(f"[VMC] Motion Engine Active. Broadcasting OSC to {self.ip}:{self.port}")

    def _audio_analysis_loop(self):
        """Listens to the Virtual Cable and maps volume to a target mouth shape."""
        p = pyaudio.PyAudio()
        device_idx = self._get_device_index(p)
        
        chunk = 1024
        stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, 
                        input=True, frames_per_buffer=chunk, input_device_index=device_idx)
        
        # Calibration thresholds
        min_rms = 100  # Floor noise
        max_rms = 2000 # Max shouting volume
        
        while self.is_running:
            try:
                data = stream.read(chunk, exception_on_overflow=False)
                rms = audioop.rms(data, 2)
                
                if rms < min_rms:
                    self.target_mouth = 0.0
                else:
                    # Map the volume to a 0.0 to 1.0 range
                    normalized = (rms - min_rms) / (max_rms - min_rms)
                    self.target_mouth = min(1.0, max(0.0, normalized))
            except Exception:
                pass

        stream.stop_stream()
        stream.close()
        p.terminate()

    def _euler_to_quat(self, roll, pitch, yaw):
        """VMC requires Quaternions for bone rotation. This converts human-readable angles."""
        cr, sr = math.cos(roll * 0.5), math.sin(roll * 0.5)
        cp, sp = math.cos(pitch * 0.5), math.sin(pitch * 0.5)
        cy, sy = math.cos(yaw * 0.5), math.sin(yaw * 0.5)

        w = cr * cp * cy + sr * sp * sy
        x = sr * cp * cy - cr * sp * sy
        y = cr * sp * cy + sr * cp * sy
        z = cr * cp * sy - sr * sp * cy
        return x, y, z, w

    def _vmc_animation_loop(self):
        """Runs at a locked 60 FPS, calculating physics and sending data."""
        while self.is_running:
            current_time = time.time()
            elapsed = current_time - self.start_time
            
            # 1. LERP THE MOUTH (The secret to smooth lip-sync)
            self.current_mouth += (self.target_mouth - self.current_mouth) * self.smoothing_speed
            self.client.send_message("/VMC/Ext/Blend/Val", ["A", self.current_mouth])
            
            # 2. RANDOMIZED BLINKING
            if current_time > self.next_blink:
                self.is_blinking = True
                self.next_blink = current_time + 0.15 # Blink takes 150ms
            elif self.is_blinking and current_time > self.next_blink:
                self.is_blinking = False
                # Schedule next blink between 2 and 6 seconds
                import random
                self.next_blink = current_time + random.uniform(2.0, 6.0)
                
            blink_val = 1.0 if self.is_blinking else 0.0
            self.client.send_message("/VMC/Ext/Blend/Val", ["Blink", blink_val])
            
            # 3. PROCEDURAL IDLE BREATHING (Spine & Head Sway)
            # Sine waves create infinite, smooth looping motions
            head_pitch = math.sin(elapsed * 1.5) * 0.02
            head_yaw = math.cos(elapsed * 0.8) * 0.015
            x, y, z, w = self._euler_to_quat(0, head_pitch, head_yaw)
            
            # Note: 0,0,0 are X,Y,Z positions. We only want to affect rotation (x,y,z,w).
            self.client.send_message("/VMC/Ext/Bone/Pos", ["Head", 0.0, 0.0, 0.0, x, y, z, w])
            
            # 4. EXECUTE ALL COMMANDS
            self.client.send_message("/VMC/Ext/Blend/Apply", [])
            
            # Sleep to maintain ~60 FPS so we don't flood the network
            time.sleep(1.0 / 60.0)