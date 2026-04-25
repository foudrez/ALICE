import threading
import whisper
import base64
import types
from flask import Flask, render_template
from flask_socketio import SocketIO
from tools.load_config import load_config
from tools.detect_cuda import COMPUTE_DEVICE
from tools.auto_threehold import calibrate_mic
from memory.memory_manager import MemoryManager
from LLM_process.llm import generate_response
from voice_process.stt import listen
from voice_process.tts import speak

# Update your Flask initialization line
app = Flask(__name__, 
            template_folder='webui', 
            static_folder='webui', 
            static_url_path='/static')
socketio = SocketIO(app)

cfg = load_config()
mem = MemoryManager(history_limit=cfg['llm'].get('max_history_turns', 10))
whisper_model = whisper.load_model(cfg['stt']['whisper_model'], device=COMPUTE_DEVICE, download_root="./models")
active_threshold = 500 

def run_alice_cycle(user_text):
    socketio.emit('new_message', {'speaker': 'User', 'text': user_text})
    socketio.emit('status', {'msg': 'Thinking...'})
    
    ai_response = generate_response(user_text, cfg, mem.get_history())
    
    mem.add_to_history("User", user_text)
    mem.add_to_history("ALICE", ai_response)
    socketio.emit('new_message', {'speaker': 'ALICE', 'text': ai_response})
    
    socketio.emit('status', {'msg': 'Speaking...'})
    
    # Get audio from TTS
    result = speak(ai_response, cfg)
    
    # Push to Web based on mode
    if isinstance(result, types.GeneratorType):
        for chunk_bytes in result:
            b64_chunk = base64.b64encode(chunk_bytes).decode('utf-8')
            socketio.emit('audio_packet', {'audio_data': b64_chunk})
    else:
        b64_audio = base64.b64encode(result).decode('utf-8')
        socketio.emit('play_full_audio', {'audio_data': b64_audio})
    
    socketio.emit('status', {'msg': 'Ready'})

@app.route('/')
def index(): return render_template('index.html')

@socketio.on('send_text')
def handle_text(data):
    threading.Thread(target=run_alice_cycle, args=(data['text'],)).start()

@socketio.on('trigger_ptt')
def handle_ptt():
    def ptt_worker():
        socketio.emit('status', {'msg': 'Listening...'})
        user_text = listen(cfg, whisper_model, active_threshold, input_device=cfg['stt'].get('input_device_index'))
        if user_text != "[IDLE_TICK]": run_alice_cycle(user_text)
        socketio.emit('status', {'msg': 'Ready'})
    threading.Thread(target=ptt_worker).start()

if __name__ == '__main__':
    if cfg['stt'].get('auto_calibrate'):
        active_threshold = calibrate_mic(input_device=cfg['stt'].get('input_device_index'))
    socketio.run(app, debug=False, host='0.0.0.0', port=5000)