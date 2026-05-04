import threading
import whisper
import base64
import types
import os 
from flask import Flask, render_template, send_from_directory
from flask_socketio import SocketIO
#---------------------------------------------------------------------------------------------
from tools.load_config import load_config
from tools.detect_cuda import COMPUTE_DEVICE
from tools.auto_threehold import calibrate_mic
from memory.memory_manager import MemoryManager
from LLM_process.llm import generate_response
from voice_process.stt import listen
from voice_process.tts import speak
from tools.language_detector import get_language
from tools.audio_output import output_audio
#---------------------------------------------------------------------------------------------

# Update your Flask initialization line
app = Flask(__name__, 
            template_folder='webui', 
            static_folder='webui', 
            static_url_path='/static')
socketio = SocketIO(app)

cfg = load_config()
if 'tts' not in cfg: cfg['tts'] = {}
cfg['tts']['audio_mode'] = 'vb'
mem = MemoryManager(history_limit=cfg['llm'].get('max_history_turns', 10))
whisper_model = None
if cfg['stt'].get('engine', 'whisper') == 'whisper':
    whisper_model = whisper.load_model(cfg['stt']['whisper_model'], device=COMPUTE_DEVICE, download_root="./models")
active_threshold = 500 


def run_alice_cycle(user_text):
    socketio.emit('new_message', {'speaker': 'User', 'text': user_text})
    socketio.emit('status', {'msg': 'Thinking...'})
    
    is_streaming = cfg.get('enable_streaming', True)
    ai_response_generator = generate_response(user_text, cfg, mem.get_history(), stream_output=is_streaming)
    
    full_response = ""
    
    if is_streaming:
        for sentence in ai_response_generator:
            full_response += sentence + " "
            
            # Send text to web bubble immediately
            socketio.emit('new_message', {'speaker': 'ALICE', 'text': sentence})
            socketio.emit('status', {'msg': 'Speaking...'})
            
            target_lang = cfg['tts'].get('default_lang', 'en')
            if cfg['tts'].get('auto_detect_language', True):
                target_lang = get_language(sentence, default_lang=target_lang)
                
            # Generate Audio
            result = speak(sentence, cfg, lang=target_lang)
            
            # Push Audio to Web and VMC
            if isinstance(result, types.GeneratorType):
                full_audio_buffer = b""
                for chunk_bytes in result:
                    full_audio_buffer += chunk_bytes
                    b64_chunk = base64.b64encode(chunk_bytes).decode('utf-8')
                    socketio.emit('audio_packet', {'audio_data': b64_chunk})
                output_audio(full_audio_buffer, cfg)
            else:
                b64_audio = base64.b64encode(result).decode('utf-8')
                socketio.emit('play_full_audio', {'audio_data': b64_audio})
                output_audio(result, cfg)
    else:
        # Standard Mode (Blocking)
        full_response = ai_response_generator
        socketio.emit('new_message', {'speaker': 'ALICE', 'text': full_response})
        target_lang = cfg['tts'].get('default_lang', 'en')
        if cfg['tts'].get('auto_detect_language', True):
            target_lang = get_language(full_response, default_lang=target_lang)
        result = speak(full_response, cfg, lang=target_lang)
        
        if isinstance(result, types.GeneratorType):
            full_audio_buffer = b""
            for chunk_bytes in result:
                full_audio_buffer += chunk_bytes
                b64_chunk = base64.b64encode(chunk_bytes).decode('utf-8')
                socketio.emit('audio_packet', {'audio_data': b64_chunk})
            output_audio(full_audio_buffer, cfg)
        else:
            b64_audio = base64.b64encode(result).decode('utf-8')
            socketio.emit('play_full_audio', {'audio_data': b64_audio})
            output_audio(result, cfg)
            
    # Save to memory after loop completes
    mem.add_to_history("User", user_text)
    mem.add_to_history("ALICE", full_response.strip())
    socketio.emit('status', {'msg': 'Ready'})
@app.route('/')
def index():# Grab the path from the config, fallback to a default if it's missing
    vrm_path = cfg.get('system', {}).get('vrm_model_path', '/static/ALICE.vrm')
    return render_template('index.html', vrm_path=vrm_path)


@app.route('/load_avatar')
def serve_avatar():
    # 1. Ask the config for the target path (e.g., "/static/my_new_avatar.vrm")
    vrm_path = cfg.get('system', {}).get('vrm_model_path', '/static/alice.vrm')
    
    # 2. Extract just the filename ("my_new_avatar.vrm")
    filename = os.path.basename(vrm_path)
    
    # 3. Serve that specific file from the webui folder
    return send_from_directory('webui', filename)

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
    import os
    check_path = os.path.join('webui', 'alice.vrm')
    print(f"🕵️ SYSTEM CHECK: Does alice.vrm exist? {os.path.exists(check_path)}")
    if cfg['stt'].get('auto_calibrate'):
        active_threshold = calibrate_mic(input_device=cfg['stt'].get('input_device_index'))
    socketio.run(app, debug=False, host='0.0.0.0', port=5000)