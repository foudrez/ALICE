import threading
import whisper
import base64
import types
import os 
import re
from flask import Flask, render_template, send_from_directory, request, jsonify, session
from flask_socketio import SocketIO
import uuid
import requests
from functools import wraps
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
from tools.home_assistant import execute_ha_command
from tools.mcp_client import execute_mcp_tool, get_all_mcp_tools
#---------------------------------------------------------------------------------------------

# Update your Flask initialization line
app = Flask(__name__, 
            template_folder='webui', 
            static_folder='webui', 
            static_url_path='/static')
app.secret_key = os.urandom(24)

@app.before_request
def ensure_session():
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())

socketio = SocketIO(app)

cfg = load_config()
if 'tts' not in cfg: cfg['tts'] = {}
cfg['tts']['audio_mode'] = 'vb'
mem = MemoryManager(
    history_limit=cfg['memory'].get('max_history', 10),
    db_path=cfg.get('memory', {}).get('db_path', 'alice_memory.db'),
    config=cfg,
)

# Initialize Animation Custom Actions & Auto-Map existing FBX files
if 'animation' not in cfg:
    cfg['animation'] = {"use_fbx": False, "fbx_mapping": {}, "custom_actions": {}}
if 'custom_actions' not in cfg['animation']:
    cfg['animation']['custom_actions'] = {}

def rescan_motions():
    global cfg
    if 'animation' not in cfg:
        cfg['animation'] = {"use_fbx": True, "fbx_mapping": {}}
    cfg['animation']['fbx_mapping'] = {}
        
    motions_dir = os.path.join('webui', 'models', 'motions')
    if os.path.exists(motions_dir):
        for category in os.listdir(motions_dir):
            cat_dir = os.path.join(motions_dir, category)
            if os.path.isdir(cat_dir):
                fbx_files = [f"{category}/{item}" for item in os.listdir(cat_dir) if item.endswith('.fbx')]
                if fbx_files:
                    cfg['animation']['fbx_mapping'][category.lower()] = fbx_files
    return cfg['animation']

rescan_motions()

whisper_model = None
if cfg['stt'].get('engine', 'whisper') == 'whisper':
    whisper_model = whisper.load_model(cfg['stt']['whisper_model'], device=COMPUTE_DEVICE, download_root="./models")
active_threshold = 500 

import queue
import time

alice_queue = queue.Queue()
latest_frame_buffer = None

last_interaction_time = time.time()
last_interaction_sid = None

def update_interaction(sid=None):
    global last_interaction_time, last_interaction_sid
    last_interaction_time = time.time()
    if sid:
        last_interaction_sid = sid

def queue_worker():
    global latest_frame_buffer
    while True:
        task = alice_queue.get()
        try:
            user_text = task['text']
            client_sid = task.get('client_sid')
            session_id = task.get('session_id', 'local')
            image_data = task.get('image_data', None)
            
            # If the user didn't explicitly send an image, but we have a live background feed running, grab it!
            if latest_frame_buffer and not image_data:
                image_data = latest_frame_buffer
            
            response = run_alice_cycle(user_text, client_sid, session_id, image_data=image_data)
            
            if 'response_box' in task:
                task['response_box']['text'] = response
                
        except Exception as e:
            print(f"Queue Error: {e}")
        finally:
            if 'event' in task and task['event']:
                task['event'].set()
            alice_queue.task_done()

threading.Thread(target=queue_worker, daemon=True).start()

def proactive_worker_thread():
    import random
    from datetime import datetime
    global last_interaction_time, last_interaction_sid, latest_frame_buffer
    
    # Delay between 15-30 minutes
    next_delay = random.randint(900, 1800)
    
    while True:
        time.sleep(10) # check every 10 seconds
        
        # Don't trigger if she's currently speaking
        if alice_is_speaking:
            update_interaction()
            continue
            
        if time.time() - last_interaction_time > next_delay:
            update_interaction() # reset timer
            next_delay = random.randint(900, 1800)
            
            current_time = datetime.now().strftime("%I:%M %p")
            
            prompt = f"[System] You haven't heard from the user in a while. The current time is {current_time}. You can optionally say something proactive (e.g. comment on the time, make a sassy remark, or comment on what you see if an image is provided). If you have nothing interesting to say, just output exactly [IDLE]."
            
            image_to_send = None
            if latest_frame_buffer and random.random() > 0.5:
                image_to_send = latest_frame_buffer
                
            alice_queue.put({
                'text': prompt,
                'client_sid': last_interaction_sid,
                'session_id': 'local',
                'image_data': image_to_send
            })

threading.Thread(target=proactive_worker_thread, daemon=True).start()

def require_token(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.headers.get('Authorization') != cfg['system']['api_token']:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated_function


alice_is_speaking = False
stop_generation_event = threading.Event()

# Pass client_sid to target specific web/phone connections safely
def run_alice_cycle(user_text, client_sid=None, session_id="local", image_data=None):
    global alice_is_speaking
    alice_is_speaking = True
    stop_generation_event.clear()
    
    # 1. Instantly display the user's message
    socketio.emit('new_message', {'speaker': 'User', 'text': user_text}, to=client_sid)
    socketio.emit('status', {'msg': 'Thinking...'}, to=client_sid)

    is_streaming = cfg.get('enable_streaming', True)
    memory_context = mem.get_context_for_prompt(query_text=user_text)
    ai_response_generator = generate_response(user_text, cfg, mem.get_history(session_id), stream_output=is_streaming, past_memory_text=memory_context, image_data=image_data)
    
    full_response = ""
    
    try:
        # 2. Process ALICE's response
        def process_sentence(sentence):
            nonlocal full_response
            
            # Look for [CMD: SOMETHING] or [ANIM: SOMETHING] in the sentence
            commands = re.findall(r'\[CMD:\s*(.*?)\]', sentence)
            animations = re.findall(r'\[ANIM:\s*(.*?)\]', sentence)
            
            # Strip the tags from the text so she doesn't speak them
            clean_sentence = re.sub(r'\[CMD:.*?\]', '', sentence)
            clean_sentence = re.sub(r'\[ANIM:.*?\]', '', clean_sentence)
            clean_sentence = re.sub(r'<think>.*?</think>', '', clean_sentence, flags=re.DOTALL | re.IGNORECASE)
            clean_sentence = re.sub(r'<[^>]+>', '', clean_sentence).strip()
            
            # We store the custom animations to emit them STRICTLY synced with the audio later.
            for anim in animations:
                print(f"[System] 💃 Queuing Animation Action: {anim}")
            
            # Fire the tools in the background
            for cmd in commands:
                if cmd.startswith("MCP "):
                    # Example cmd: "MCP schedule set_alarm time=8:00 AM"
                    parts = cmd.split(" ", 3)
                    if len(parts) >= 3:
                        server_name = parts[1]
                        tool_name = parts[2]
                        # Super simple arg parsing for the skeleton (e.g. key=val, key=val)
                        args_str = parts[3] if len(parts) > 3 else ""
                        tool_args = {}
                        if args_str:
                            for pair in args_str.split(','):
                                if '=' in pair:
                                    k, v = pair.split('=', 1)
                                    tool_args[k.strip()] = v.strip()
                        
                        # Run the MCP tool asynchronously in a background thread
                        def run_mcp_bg():
                            print(f"[System] 🚀 Spawning background MCP task: {server_name}:{tool_name}")
                            socketio.emit('mcp_tool_start', {'server': server_name, 'tool': tool_name}, to=client_sid)
                            
                            result = execute_mcp_tool(server_name, tool_name, tool_args)
                            print(f"[System] 📥 MCP Result received: {result}")
                            
                            socketio.emit('mcp_tool_end', {'server': server_name, 'tool': tool_name, 'result': result}, to=client_sid)
                            
                            # Drop the result back into ALICE's context so she can follow up!
                            alice_queue.put({
                                'text': f"[SYSTEM: The background MCP task completed with result: {result}. Please acknowledge this to the user.]",
                                'client_sid': client_sid,
                                'session_id': session_id
                            })
                            
                        threading.Thread(target=run_mcp_bg, daemon=True).start()
                else:
                    execute_ha_command(cmd, cfg)
                
            # If the sentence was ONLY a command tag with no spoken text, skip the audio generation
            if not clean_sentence:
                return
                
            # --- STANDARD AUDIO/UI ROUTING ---
            full_response += clean_sentence + " "
            target_lang = cfg['tts'].get('default_lang', 'en')
            if cfg['tts'].get('auto_detect_language', True):
                target_lang = get_language(clean_sentence, default_lang=target_lang)
                
            result = speak(clean_sentence, cfg, lang=target_lang)
            
            full_audio_buffer = b""
            if isinstance(result, types.GeneratorType):
                for chunk_bytes in result:
                    full_audio_buffer += chunk_bytes
            else:
                full_audio_buffer = result

            b64_audio = base64.b64encode(full_audio_buffer).decode('utf-8')
            
            # If interrupted while generating TTS, discard it!
            if stop_generation_event.is_set():
                return
                
            # Emit Speaking status precisely when the audio is ready to play!
            socketio.emit('status', {'msg': 'Speaking...'}, to=client_sid)
            
            # Notice we use 'clean_sentence' here so the tag stays hidden!
            socketio.emit('alice_speech', {
                'text': clean_sentence, 
                'audio_data': b64_audio,
                'animations': [anim.strip() for anim in animations]
            }, to=client_sid)
            
            output_audio(full_audio_buffer, cfg)

        # Route streaming or blocking generation
        if is_streaming:
            for sentence in ai_response_generator:
                if stop_generation_event.is_set():
                    print("[System] Voice Barge-In: Halting generation early!")
                    break
                process_sentence(sentence)
        else:
            if not stop_generation_event.is_set():
                process_sentence(ai_response_generator)
                
        # Save to memory + trigger L2/L3/L4 processing
        mem.process_turn("User", user_text, cfg, session_id=session_id)
        mem.process_turn("ALICE", full_response.strip(), cfg, session_id=session_id)
        socketio.emit('status', {'msg': 'Ready'}, to=client_sid)
    except Exception as e:
        print(f"\n[WebUI Cycle Error] {e}")
        socketio.emit('status', {'msg': 'Error occurred'}, to=client_sid)
    finally:
        alice_is_speaking = False
    
    return full_response.strip()


@app.route('/')
def index():
    vrm_path = cfg.get('system', {}).get('vrm_model_path', '/static/models/ALICE.vrm')
    return render_template('webui_mode.html', vrm_path=vrm_path)

@app.route('/vpet')
def vpet():
    vrm_path = cfg.get('system', {}).get('vrm_model_path', '/static/models/ALICE.vrm')
    return render_template('vpet.html', vrm_path=vrm_path)

@app.route('/webui')
def webui_mode():
    vrm_path = cfg.get('system', {}).get('vrm_model_path', '/static/models/ALICE.vrm')
    return render_template('webui_mode.html', vrm_path=vrm_path)

@app.route('/headless')
def headless():
    return render_template('headless.html')

@app.route('/api/chat', methods=['POST'])
@require_token
def api_chat():
    data = request.json
    user_text = data.get('text')
    
    session_id = session.get('session_id', 'api_user')
    
    event = threading.Event()
    response_box = {}
    
    alice_queue.put({
        'text': user_text,
        'client_sid': None,
        'session_id': session_id,
        'event': event,
        'response_box': response_box
    })
    
    # Wait for the queue worker to process this request
    event.wait()
    
    return jsonify({
        "status": "success",
        "response": response_box.get('text', "")
    })

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/api/mcp/servers', methods=['GET'])
def get_mcp_servers():
    tools = get_all_mcp_tools()
    return jsonify({"status": "success", "servers": tools})

@app.route('/api/mcp/execute', methods=['POST'])
def execute_mcp_api():
    data = request.json
    server_name = data.get('server_name')
    tool_name = data.get('tool_name')
    tool_args = data.get('tool_args', {})
    if not server_name or not tool_name:
        return jsonify({"error": "Missing server_name or tool_name"}), 400
    try:
        res = execute_mcp_tool(server_name, tool_name, tool_args)
        return jsonify({"status": "success", "result": res})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/models', methods=['GET'])
def get_models():
    """Returns a list of available VRM and Live2D models in the static/models folder."""
    models_dir = os.path.join('webui', 'models')
    vrm_models = []
    live2d_models = []
    
    if os.path.exists(models_dir):
        for item in os.listdir(models_dir):
            item_path = os.path.join(models_dir, item)
            if os.path.isfile(item_path) and item.endswith('.vrm'):
                vrm_models.append({"name": item, "path": f"/static/models/{item}"})
            elif os.path.isdir(item_path):
                # Search for the .model3.json file inside the folder
                model3_json = None
                for subitem in os.listdir(item_path):
                    if subitem.endswith('.model3.json'):
                        model3_json = subitem
                        break
                if model3_json:
                    live2d_models.append({"name": item, "path": f"/static/models/{item}/{model3_json}"})
                
    return jsonify({
        "status": "success",
        "vrm": vrm_models,
        "live2d": live2d_models
    })

@app.route('/api/config', methods=['GET'])
def get_config():
    """Exposes safe system configuration to the frontend (like renderer type)."""
    return jsonify({
        "renderer": cfg.get('system', {}).get('renderer', 'vrm'),
        "live2d_model_path": cfg.get('system', {}).get('live2d_model_path', ''),
        "background_image": cfg.get('system', {}).get('background_image', '/static/bg.jpg'),
        "animation": cfg.get('animation', {
            "use_fbx": False,
            "fbx_mapping": {
                "idle": "None", "happy": "None", "sad": "None", 
                "angry": "None", "relaxed": "None", "neutral": "None", "surprised": "None",
                "thinking": "None", "speaking": "None", "queued": "None", "listening": "None"
            },
            "custom_actions": {}
        })
    })

@app.route('/api/animations', methods=['GET'])
def get_animations():
    """Returns a categorized dictionary of available FBX animations from subfolders."""
    motions_dir = os.path.join('webui', 'models', 'motions')
    categories = {'emotions': [], 'actions': [], 'dances': [], 'fidgets': []}
    
    if os.path.exists(motions_dir):
        for cat in categories.keys():
            cat_dir = os.path.join(motions_dir, cat)
            if os.path.exists(cat_dir):
                for item in os.listdir(cat_dir):
                    if item.endswith('.fbx'):
                        categories[cat].append(f"{cat}/{item}")
                        
    return jsonify({"status": "success", "animations": categories})

@app.route('/api/rescan_animations', methods=['POST'])
def handle_rescan_animations():
    """Rescans the motions folder and updates mapping dynamically without a restart."""
    try:
        updated_anim_cfg = rescan_motions()
        update_config_animation(updated_anim_cfg)
        return jsonify({"status": "success", "msg": "Animations rescanned successfully!", "animation": updated_anim_cfg})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
def update_config_animation(anim_cfg):
    with open("config.yaml", "r", encoding="utf-8") as f:
        content = f.read()
    
    import yaml
    anim_yaml = yaml.dump({"animation": anim_cfg}, default_flow_style=False)
    
    import re
    if re.search(r'^animation:', content, re.MULTILINE):
        content = re.sub(r'^animation:.*?(?=^[a-zA-Z_]+:|\Z)', anim_yaml, content, flags=re.MULTILINE | re.DOTALL)
    else:
        content += "\n" + anim_yaml
        
    with open("config.yaml", "w", encoding="utf-8") as f:
        f.write(content)

@app.route('/api/set_animation_config', methods=['POST'])
def set_animation_config():
    data = request.json
    global cfg
    cfg['animation'] = data
    update_config_animation(data)
    return jsonify({"status": "success", "msg": "Animation settings saved."})

@app.route('/api/market/download', methods=['POST'])
def download_animation_from_market():
    data = request.json
    url = data.get('url')
    name = data.get('name', 'DownloadedAnimation')
    category = data.get('category', 'emotions')
    
    if not url:
        return jsonify({"error": "No URL provided"}), 400
        
    try:
        # Create directory if it doesn't exist
        save_dir = os.path.join('webui', 'models', 'motions', category)
        os.makedirs(save_dir, exist_ok=True)
        
        # Ensure filename ends with .fbx
        filename = f"{name}.fbx"
        save_path = os.path.join(save_dir, filename)
        
        # Download the file
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        return jsonify({"status": "success", "msg": f"Successfully downloaded {filename}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/set_renderer', methods=['POST'])
def set_renderer():
    data = request.json
    new_renderer = data.get('renderer')
    if new_renderer not in ['vrm', 'live2d']:
        return jsonify({"status": "error", "msg": "Invalid renderer"}), 400
        
    global cfg
    cfg['system']['renderer'] = new_renderer
    
    with open("config.yaml", "r", encoding="utf-8") as f:
        content = f.read()
    
    content = re.sub(
        r'(renderer:\s*").*?(")',
        f'\\1{new_renderer}\\2',
        content
    )
    
    with open("config.yaml", "w", encoding="utf-8") as f:
        f.write(content)
        
    return jsonify({"status": "success", "msg": f"Renderer switched to {new_renderer}"})
    
@app.route('/load_avatar')
def serve_avatar():
    vrm_path = cfg.get('system', {}).get('vrm_model_path', 'webui/models/silver_wolf.vrm')
    # Get just the filename (e.g., 'silver_wolf.vrm')
    filename = os.path.basename(vrm_path)
    # Tell Flask to look in the 'webui/models' folder for this file
    return send_from_directory(os.path.join('webui', 'models'), filename)

def update_config_voice(audio_path, prompt_text):
    with open("config.yaml", "r", encoding="utf-8") as f:
        content = f.read()
    
    # Safely replace reference_audio_path
    # Windows paths might have backslashes, so we use string formatting safely
    content = re.sub(
        r'(reference_audio_path:\s*").*?(")',
        f'\\1{audio_path.replace(chr(92), "/")}\\2',
        content
    )
    
    # Safely replace reference_prompt_text
    escaped_prompt = prompt_text.replace('"', '\\"')
    content = re.sub(
        r'(reference_prompt_text:\s*").*?(")',
        f'\\1{escaped_prompt}\\2',
        content
    )
    
    with open("config.yaml", "w", encoding="utf-8") as f:
        f.write(content)

@app.route('/api/voice_clone', methods=['POST'])
def handle_voice_clone():
    if 'audio' not in request.files or 'prompt_text' not in request.form:
        return jsonify({"error": "Missing audio file or prompt_text"}), 400
        
    audio_file = request.files['audio']
    prompt_text = request.form['prompt_text']
    
    if audio_file.filename == '':
        return jsonify({"error": "No selected file"}), 400
        
    # Ensure custom voice dir exists
    save_dir = os.path.join("charvoice", "custom")
    os.makedirs(save_dir, exist_ok=True)
    
    # Save the file
    file_ext = os.path.splitext(audio_file.filename)[1]
    save_path = os.path.join(save_dir, f"cloned_voice_{int(time.time())}{file_ext}")
    audio_file.save(save_path)
    
    # Update active config in memory so the next turn uses it immediately!
    global cfg
    cfg['tts']['reference_audio_path'] = save_path
    cfg['tts']['reference_prompt_text'] = prompt_text
    
    # Persist to disk
    update_config_voice(save_path, prompt_text)
    
    return jsonify({"status": "success", "msg": "Voice cloned successfully!", "path": save_path})

def update_config_background(bg_path):
    import time
    with open("config.yaml", "r", encoding="utf-8") as f:
        content = f.read()
    
    if "background_image:" in content:
        content = re.sub(
            r'(background_image:\s*").*?(")',
            f'\\1{bg_path.replace(chr(92), "/")}\\2',
            content
        )
    else:
        content = content.replace("system:\n", f"system:\n  background_image: \"{bg_path.replace(chr(92), '/')}\"\n", 1)
        
    with open("config.yaml", "w", encoding="utf-8") as f:
        f.write(content)

@app.route('/api/upload_background', methods=['POST'])
def handle_upload_background():
    import time
    if 'image' not in request.files:
        return jsonify({"error": "Missing image file"}), 400
        
    image_file = request.files['image']
    if image_file.filename == '':
        return jsonify({"error": "No selected file"}), 400
        
    save_dir = os.path.join("webui", "backgrounds")
    os.makedirs(save_dir, exist_ok=True)
    
    file_ext = os.path.splitext(image_file.filename)[1]
    save_filename = f"bg_{int(time.time())}{file_ext}"
    save_path = os.path.join(save_dir, save_filename)
    image_file.save(save_path)
    
    web_path = f"/static/backgrounds/{save_filename}"
    
    global cfg
    if 'system' not in cfg: cfg['system'] = {}
    cfg['system']['background_image'] = web_path
    
    update_config_background(web_path)
    
    return jsonify({"status": "success", "msg": "Background updated!", "path": web_path})

@socketio.on('interrupt_generation')
def handle_interrupt(*args):
    stop_generation_event.set()
    global alice_is_speaking
    alice_is_speaking = False
    print("[System] Manual interrupt received from frontend.")
    
@socketio.on('send_text')
def handle_text(data):
    # Capture the unique user connection ID BEFORE threading
    client_sid = request.sid 
    session_id = session.get('session_id', str(uuid.uuid4()))
    update_interaction(client_sid)
    
    socketio.emit('status', {'msg': 'Queued...'}, to=client_sid)
    alice_queue.put({
        'text': data['text'],
        'client_sid': client_sid,
        'session_id': session_id
    })

@socketio.on('trigger_ptt')
def handle_ptt():
    # Capture the unique user connection ID BEFORE threading
    client_sid = request.sid 
    session_id = session.get('session_id', str(uuid.uuid4()))
    update_interaction(client_sid)
    
    def ptt_worker():
        socketio.emit('status', {'msg': 'Listening...'}, to=client_sid)
        user_text = listen(cfg, whisper_model, active_threshold, input_device=cfg['stt'].get('input_device_index'))
        if user_text != "[IDLE_TICK]": 
            socketio.emit('status', {'msg': 'Queued...'}, to=client_sid)
            alice_queue.put({
                'text': user_text,
                'client_sid': client_sid,
                'session_id': session_id
            })
            socketio.emit('status', {'msg': 'Ready'}, to=client_sid)
            
    threading.Thread(target=ptt_worker).start()

from tools.vision import capture_webcam, capture_screen

@socketio.on('trigger_vision_webcam')
def handle_vision_webcam():
    client_sid = request.sid 
    session_id = session.get('session_id', str(uuid.uuid4()))
    update_interaction(client_sid)
    
    def vision_worker():
        socketio.emit('status', {'msg': 'Looking at webcam...'}, to=client_sid)
        image_data = capture_webcam()
        if image_data:
            socketio.emit('status', {'msg': 'Queued vision request...'}, to=client_sid)
            alice_queue.put({
                'text': "[System] The user has shown you an image from their webcam. Please describe what you see, or answer their questions about it.",
                'client_sid': client_sid,
                'session_id': session_id,
                'image_data': image_data
            })
        else:
            socketio.emit('status', {'msg': 'Failed to capture webcam'}, to=client_sid)
            
    threading.Thread(target=vision_worker).start()

@socketio.on('trigger_vision_screen')
def handle_vision_screen():
    client_sid = request.sid 
    session_id = session.get('session_id', str(uuid.uuid4()))
    update_interaction(client_sid)
    
    def vision_worker():
        socketio.emit('status', {'msg': 'Looking at screen...'}, to=client_sid)
        image_data = capture_screen()
        if image_data:
            socketio.emit('status', {'msg': 'Queued vision request...'}, to=client_sid)
            alice_queue.put({
                'text': "[System] The user has shown you a screenshot of their computer screen. Please describe what you see, or answer their questions about it.",
                'client_sid': client_sid,
                'session_id': session_id,
                'image_data': image_data
            })
        else:
            socketio.emit('status', {'msg': 'Failed to capture screen'}, to=client_sid)
            
    threading.Thread(target=vision_worker).start()

@socketio.on('stream_frame_capture')
def handle_stream_frame_capture(data):
    """Receives a base64 encoded frame from the frontend WebRTC stream every 2 seconds"""
    global latest_frame_buffer
    latest_frame_buffer = data.get('image')

@socketio.on('stop_stream')
def handle_stop_stream():
    global latest_frame_buffer
    latest_frame_buffer = None
    socketio.emit('status', {'msg': 'Streaming Stopped.'}, to=request.sid)
active_connections = {}

@socketio.on('connect')
def handle_connect():
    client_sid = request.sid
    session_id = session.get('session_id', str(uuid.uuid4()))
    update_interaction(client_sid)
    
    active_connections[session_id] = active_connections.get(session_id, 0) + 1
    
    if not session.get('has_greeted'):
        session['has_greeted'] = True
        print(f"[System] Client {client_sid} connected for the first time. Triggering greeting.")
        alice_queue.put({
            'text': "[System] The user has just loaded the interface and connected. Please greet them warmly.",
            'client_sid': client_sid,
            'session_id': session_id
        })
    else:
        print(f"[System] Client {client_sid} reconnected (e.g. refresh). Skipping greeting.")

@socketio.on('disconnect')
def handle_disconnect():
    client_sid = request.sid
    session_id = session.get('session_id', 'local')
    
    if session_id in active_connections:
        active_connections[session_id] -= 1
        
    def check_and_goodbye():
        if active_connections.get(session_id, 0) <= 0:
            print(f"[System] Session {session_id} disconnected fully. Triggering goodbye.")
            session['has_greeted'] = False # Reset for next true visit if cookie persists
            alice_queue.put({
                'text': "[System] The user has just closed the interface or disconnected. Please say goodbye to them.",
                'client_sid': None,
                'session_id': session_id
            })
            
    # Wait 5 seconds to allow for page refreshes
    threading.Timer(5.0, check_and_goodbye).start()

def webui_ear_thread():
    import time
    global alice_is_speaking, active_threshold
    
    use_wakeword = cfg.get('stt', {}).get('use_wakeword', False)
    wakeword_threshold = cfg.get('stt', {}).get('wakeword_threshold', 0.5)
    mic_id = cfg['stt'].get('input_device_index')
    
    if use_wakeword:
        import openwakeword
        from openwakeword.model import Model
        import glob
        import os
        
        if not os.path.exists(os.path.join(os.path.dirname(openwakeword.__file__), "resources", "models", "melspectrogram.onnx")):
            print("[System] Downloading openwakeword ONNX feature extractors...")
            openwakeword.utils.download_models()
        
        custom_models = glob.glob(os.path.join("tools", "wakeword", "*.onnx"))
        custom_models = [m for m in custom_models if not m.endswith("embedding_model.onnx") and not m.endswith("melspectrogram.onnx")]
        
        if not custom_models:
            print("[System] No custom .onnx wakeword models found in tools/wakeword/. Disabling WebUI Auto-Attention.")
            use_wakeword = False
        else:
            print(f"\n[System] WebUI Loading Custom Wakeword Models: {custom_models}")
            try:
                # Force ONNX inference framework to avoid tflite-runtime issues on Windows
                oww_model = Model(wakeword_models=custom_models, inference_framework="onnx")
            except Exception as e:
                print(f"[Error] Failed to load wakeword models in WebUI: {e}")
                use_wakeword = False
            
    print("\n[👂 WebUI Auto-Attention Mode: ON]")
    
    while True:
        if alice_is_speaking:
            time.sleep(0.5)
            continue
            
        if use_wakeword:
            import pyaudio
            import numpy as np
            p = pyaudio.PyAudio()
            CHUNK = 1280
            stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=CHUNK, input_device_index=mic_id)
            
            triggered = False
            while not alice_is_speaking and not triggered:
                try:
                    data = stream.read(CHUNK, exception_on_overflow=False)
                except OSError:
                    continue
                audio_data = np.frombuffer(data, dtype=np.int16)
                oww_model.predict(audio_data)
                
                for mdl in oww_model.prediction_buffer.keys():
                    if oww_model.prediction_buffer[mdl][-1] > wakeword_threshold:
                        triggered = True
                        break
            
            stream.stop_stream()
            stream.close()
            p.terminate()
            
            if not triggered:
                continue
                
            print("\n[✨ Wakeword Detected! Listening in WebUI...]")
            socketio.emit('status', {'msg': 'Listening...'})
            
        user_text = listen(cfg, whisper_model, active_threshold, input_device=mic_id)
        if user_text and user_text != "[IDLE_TICK]":
            update_interaction()
            print(f"\n[Subtitles]: {user_text}")
            socketio.emit('status', {'msg': 'Queued...'})
            alice_queue.put({
                'text': user_text,
                'client_sid': None,
                'session_id': 'local'
            })

# ==========================================
# FULL-DUPLEX VAD INTERRUPT THREAD
# ==========================================
def vad_interrupt_thread():
    """
    Runs a dedicated Voice Activity Detector (Silero VAD) that monitors the
    microphone WHILE ALICE is speaking. If the user talks over her, it fires
    force_stop to instantly kill TTS/LLM generation and clear the frontend queue.
    """
    import time
    import numpy as np
    global alice_is_speaking
    
    vad_cfg = cfg.get('vad', {})
    if not vad_cfg.get('enabled', True):
        print("[VAD] Voice Activity Detection disabled in config.")
        return
    
    vad_threshold = vad_cfg.get('threshold', 0.5)
    min_trigger_frames = vad_cfg.get('min_trigger_frames', 3)
    mic_id = cfg['stt'].get('input_device_index')
    
    # Load Silero VAD model (tiny, runs on CPU in <1ms per frame)
    try:
        import torch
        vad_model, vad_utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            trust_repo=True
        )
        (get_speech_timestamps, _, read_audio, _, _) = vad_utils
        print("[VAD] ✅ Silero VAD loaded successfully. Hands-free interruption is ACTIVE.")
    except Exception as e:
        print(f"[VAD] ⚠️ Failed to load Silero VAD: {e}")
        print("[VAD] Hands-free interruption will be disabled.")
        return
    
    CHUNK = 512  # 32ms at 16kHz — Silero's expected window size
    RATE = 16000
    
    while True:
        # Sleep until ALICE starts speaking
        if not alice_is_speaking:
            time.sleep(0.3)
            continue
        
        # Open a dedicated mic stream for VAD
        try:
            import pyaudio
            p = pyaudio.PyAudio()
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK,
                input_device_index=mic_id
            )
        except Exception as e:
            print(f"[VAD] Mic open failed: {e}")
            time.sleep(2)
            continue
        
        consecutive_speech_frames = 0
        
        try:
            while alice_is_speaking:
                try:
                    data = stream.read(CHUNK, exception_on_overflow=False)
                except OSError:
                    continue
                
                # Convert raw bytes to float32 tensor for Silero
                audio_int16 = np.frombuffer(data, dtype=np.int16)
                audio_float32 = audio_int16.astype(np.float32) / 32768.0
                audio_tensor = torch.from_numpy(audio_float32)
                
                # Run VAD inference
                confidence = vad_model(audio_tensor, RATE).item()
                
                if confidence > vad_threshold:
                    consecutive_speech_frames += 1
                else:
                    consecutive_speech_frames = 0
                
                # Trigger interrupt after sustained speech detection
                if consecutive_speech_frames >= min_trigger_frames:
                    print(f"[VAD] 🗣️ User voice detected (confidence: {confidence:.2f})! Interrupting ALICE...")
                    
                    # 1. Kill backend generation
                    stop_generation_event.set()
                    alice_is_speaking = False
                    
                    # 2. Broadcast force_stop to ALL connected frontends
                    socketio.emit('force_stop')
                    
                    consecutive_speech_frames = 0
                    break
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()


if __name__ == '__main__':
    check_path = os.path.join('webui', 'alice.vrm')
    print(f"🕵️ SYSTEM CHECK: Does alice.vrm exist? {os.path.exists(check_path)}")
    if cfg['stt'].get('auto_calibrate'):
        active_threshold = calibrate_mic(input_device=cfg['stt'].get('input_device_index'))
    
    threading.Thread(target=webui_ear_thread, daemon=True).start()
    threading.Thread(target=vad_interrupt_thread, daemon=True).start()
    
    try:
        socketio.run(app, debug=False, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        print("\n[System] Shutting down WebUI...")
        if cfg.get('memory', {}).get('l3_consolidate_on_exit', True):
            print("[🧠 Consolidating memories before shutdown...]")
            mem.consolidate(cfg)