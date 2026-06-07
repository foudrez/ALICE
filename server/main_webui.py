import os
import threading
import whisper
from server.app import create_app, socketio

from tools.load_config import load_config
from tools.detect_cuda import COMPUTE_DEVICE
from tools.auto_threehold import calibrate_mic
from memory.memory_manager import MemoryManager

# We will need the VAD interrupt thread and Ear thread, but we can reuse the ones from webui for now
# We will just import them, or rewrite them.
from webui import webui_ear_thread, vad_interrupt_thread, alice_queue

if __name__ == '__main__':
    cfg = load_config()
    
    mem = MemoryManager(
        history_limit=cfg['memory'].get('max_history', 10),
        db_path=cfg.get('memory', {}).get('db_path', 'alice_memory.db'),
        config=cfg,
    )
    
    app = create_app(cfg, mem)
    
    whisper_model = None
    if cfg['stt'].get('engine', 'whisper') == 'whisper':
        whisper_model = whisper.load_model(cfg['stt']['whisper_model'], device=COMPUTE_DEVICE, download_root="./models")
    
    if cfg['stt'].get('auto_calibrate'):
        active_threshold = calibrate_mic(input_device=cfg['stt'].get('input_device_index'))
    
    # In a full refactor, we would move the ear and vad threads to a background task manager.
    # For now, we will start them directly.
    threading.Thread(target=webui_ear_thread, daemon=True).start()
    threading.Thread(target=vad_interrupt_thread, daemon=True).start()
    
    print("Starting Next.js API server on port 5000...")
    
    try:
        socketio.run(app, debug=False, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        print("\n[System] Shutting down Server...")
        if cfg.get('memory', {}).get('l3_consolidate_on_exit', True):
            mem.consolidate(cfg)
