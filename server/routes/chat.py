from flask import Blueprint, request, current_app, session
from flask_socketio import emit
import threading
import queue
import re
from LLM_process.llm import generate_response
from voice_process.tts import speak
from tools.language_detector import get_language
from tools.home_assistant import execute_ha_command
from tools.mcp_client import execute_mcp_tool

chat_bp = Blueprint('chat_bp', __name__)

alice_queue = queue.Queue()
latest_frame_buffer = None
alice_is_speaking = False
stop_generation_event = threading.Event()

def run_alice_cycle(socketio, app, user_text, client_sid=None, session_id="local", image_data=None):
    global alice_is_speaking
    alice_is_speaking = True
    stop_generation_event.clear()
    
    socketio.emit('new_message', {'speaker': 'User', 'text': user_text}, to=client_sid)
    socketio.emit('status', {'msg': 'Thinking...'}, to=client_sid)

    cfg = app.config['ALICE_CFG']
    mem = app.config['ALICE_MEM']

    is_streaming = cfg.get('enable_streaming', True)
    memory_context = mem.get_context_for_prompt(query_text=user_text)
    
    # We pass the generator so we can iterate over it
    ai_response_generator = generate_response(user_text, cfg, mem.get_history(session_id), stream_output=is_streaming, past_memory_text=memory_context, image_data=image_data)
    
    full_response = ""
    
    try:
        def process_sentence(sentence):
            nonlocal full_response
            
            commands = re.findall(r'\[CMD:\s*(.*?)\]', sentence)
            animations = re.findall(r'\[ANIM:\s*(.*?)\]', sentence)
            
            clean_sentence = re.sub(r'\[CMD:.*?\]', '', sentence)
            clean_sentence = re.sub(r'\[ANIM:.*?\]', '', clean_sentence).strip()
            
            for anim in animations:
                socketio.emit('play_action_animation', {'anim': anim.strip()}, to=client_sid)
            
            for cmd in commands:
                if cmd.startswith("MCP "):
                    parts = cmd.split(" ", 3)
                    if len(parts) >= 3:
                        server_name = parts[1]
                        tool_name = parts[2]
                        args_str = parts[3] if len(parts) > 3 else ""
                        tool_args = {}
                        if args_str:
                            for pair in args_str.split(','):
                                if '=' in pair:
                                    k, v = pair.split('=', 1)
                                    tool_args[k.strip()] = v.strip()
                        
                        def run_mcp_bg():
                            socketio.emit('mcp_tool_start', {'server': server_name, 'tool': tool_name}, to=client_sid)
                            result = execute_mcp_tool(server_name, tool_name, tool_args)
                            socketio.emit('mcp_tool_end', {'server': server_name, 'tool': tool_name, 'result': result}, to=client_sid)
                            
                            alice_queue.put({
                                'text': f"[SYSTEM: The background MCP task completed with result: {result}. Please acknowledge this to the user.]",
                                'client_sid': client_sid,
                                'session_id': session_id
                            })
                            
                        threading.Thread(target=run_mcp_bg, daemon=True).start()
                else:
                    execute_ha_command(cmd, cfg)
                
            if not clean_sentence:
                return
                
            full_response += clean_sentence + " "
            socketio.emit('status', {'msg': 'Speaking...'}, to=client_sid)
            
            target_lang = cfg['tts'].get('default_lang', 'en')
            if cfg['tts'].get('auto_detect_language', True):
                target_lang = get_language(clean_sentence, default_lang=target_lang)
                
            result = speak(clean_sentence, cfg, lang=target_lang)
            
            if result:
                socketio.emit('audio_ready', {
                    'audio': result['audio'], 
                    'text': clean_sentence, 
                    'visemes': result.get('visemes')
                }, to=client_sid)
            else:
                socketio.emit('new_message', {'speaker': 'ALICE', 'text': clean_sentence}, to=client_sid)

        for sentence in ai_response_generator:
            if stop_generation_event.is_set():
                break
            process_sentence(sentence)
            
    except Exception as e:
        print(f"Error in response processing: {e}")
        socketio.emit('status', {'msg': 'Error occurred.'}, to=client_sid)
    finally:
        mem.add_interaction(user_text, full_response.strip(), session_id)
        alice_is_speaking = False
        socketio.emit('status', {'msg': 'Listening...'}, to=client_sid)
    
    return full_response.strip()

def queue_worker(socketio, app):
    global latest_frame_buffer
    with app.app_context():
        while True:
            task = alice_queue.get()
            try:
                user_text = task['text']
                client_sid = task.get('client_sid')
                session_id = task.get('session_id', 'local')
                image_data = task.get('image_data', None)
                
                if latest_frame_buffer and not image_data:
                    image_data = latest_frame_buffer
                
                response = run_alice_cycle(socketio, app, user_text, client_sid, session_id, image_data=image_data)
                
                if 'response_box' in task:
                    task['response_box']['text'] = response
                    
            except Exception as e:
                print(f"Queue Error: {e}")
            finally:
                if 'event' in task and task['event']:
                    task['event'].set()
                alice_queue.task_done()

def init_chat_socketio(socketio, app):
    # Start the background worker
    threading.Thread(target=queue_worker, args=(socketio, app), daemon=True).start()

    @socketio.on('send_text')
    def handle_text(data):
        text = data.get('text', '').strip()
        if text:
            alice_queue.put({
                'text': text,
                'client_sid': request.sid,
                'session_id': session.get('session_id', 'local')
            })

    @socketio.on('interrupt')
    def handle_interrupt():
        stop_generation_event.set()
        
    @socketio.on('video_frame')
    def handle_video_frame(data):
        global latest_frame_buffer
        frame_data = data.get('image')
        if frame_data:
            header, encoded = frame_data.split(",", 1)
            import base64
            latest_frame_buffer = base64.b64decode(encoded)
