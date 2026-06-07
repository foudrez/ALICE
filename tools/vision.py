import cv2
import mss
import numpy as np
import base64

def _encode_image_to_base64(image_np):
    """Encodes a numpy image array to base64 string."""
    # Convert RGB to BGR for OpenCV if it comes from MSS, but MSS returns BGRA. 
    # Let's ensure it's in BGR before encoding to JPEG.
    if image_np.shape[2] == 4:
        image_np = cv2.cvtColor(image_np, cv2.COLOR_BGRA@BGR)
        
    _, buffer = cv2.imencode('.jpg', image_np)
    img_bytes = buffer.tobytes()
    return base64.b64encode(img_bytes).decode('utf-8')

def capture_webcam():
    """Captures a single frame from the webcam and returns it as a Base64 encoded JPEG."""
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[Vision] Error: Could not open webcam.")
        return None
        
    # Read a few frames to let the camera adjust to light
    for _ in range(5):
        cap.read()
        
    ret, frame = cap.read()
    cap.release()
    
    if not ret:
        print("[Vision] Error: Could not read frame from webcam.")
        return None
        
    return _encode_image_to_base64(frame)

def get_monitors():
    """Returns a list of available monitors."""
    try:
        with mss.mss() as sct:
            # sct.monitors[0] is a virtual monitor combining all monitors
            # so we only return the actual physical monitors (index 1 and above)
            monitors = []
            for i, monitor in enumerate(sct.monitors[1:], start=1):
                monitors.append({
                    "id": i,
                    "width": monitor.get("width"),
                    "height": monitor.get("height"),
                    "left": monitor.get("left"),
                    "top": monitor.get("top")
                })
            return monitors
    except Exception as e:
        print(f"[Vision] Error getting monitors: {e}")
        return []

def capture_screen(monitor_index=1):
    """Captures the specified screen (default primary) and returns it as a Base64 encoded JPEG."""
    with mss.mss() as sct:
        if monitor_index < 1 or monitor_index >= len(sct.monitors):
            monitor_index = 1 # Fallback to primary if out of range
            
        monitor = sct.monitors[monitor_index]
        screenshot = sct.grab(monitor)
        
        # Convert to numpy array
        img_np = np.array(screenshot)
        
        # MSS returns BGRA. Convert to BGR inside _encode_image_to_base64
        # Just to be safe, cvtColor to BGR here.
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_BGRA2BGR)
        
        return _encode_image_to_base64(img_bgr)
