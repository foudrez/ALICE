import os
import re
import time
from flask import Blueprint, request, jsonify, current_app

config_bp = Blueprint('config_bp', __name__)

@config_bp.route('/models', methods=['GET'])
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

@config_bp.route('/config', methods=['GET'])
def get_config():
    cfg = current_app.config['ALICE_CFG']
    return jsonify({
        "renderer": cfg.get('system', {}).get('renderer', 'vrm'),
        "live2d_model_path": cfg.get('system', {}).get('live2d_model_path', ''),
        "background_image": cfg.get('system', {}).get('background_image', '/static/bg.jpg'),
        "animation": cfg.get('animation', {
            "use_fbx": False,
            "fbx_mapping": {
                "idle": ["fidgets/Female Standing Pose.fbx"], "happy": "None", "sad": "None", 
                "angry": "None", "relaxed": "None", "neutral": "None", "surprised": "None",
                "thinking": "None", "speaking": "None", "queued": "None", "listening": "None"
            },
            "blendshape_mapping": {},
            "custom_actions": {}
        })
    })

@config_bp.route('/animations', methods=['GET'])
def get_animations():
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

def update_config_animation(anim_cfg):
    with open("config.yaml", "r", encoding="utf-8") as f:
        content = f.read()
    import yaml
    anim_yaml = yaml.dump({"animation": anim_cfg}, default_flow_style=False)
    if re.search(r'^animation:', content, re.MULTILINE):
        content = re.sub(r'^animation:.*?(?=^[a-zA-Z_]+:|\Z)', anim_yaml, content, flags=re.MULTILINE | re.DOTALL)
    else:
        content += "\n" + anim_yaml
    with open("config.yaml", "w", encoding="utf-8") as f:
        f.write(content)

@config_bp.route('/set_animation_config', methods=['POST'])
def set_animation_config():
    data = request.json
    cfg = current_app.config['ALICE_CFG']
    cfg['animation'] = data
    update_config_animation(data)
    return jsonify({"status": "success", "msg": "Animation settings saved."})

def update_config_voice(audio_path, prompt_text):
    with open("config.yaml", "r", encoding="utf-8") as f:
        content = f.read()
    content = re.sub(
        r'(reference_audio_path:\s*").*?(")',
        f'\\1{audio_path.replace(chr(92), "/")}\\2',
        content
    )
    escaped_prompt = prompt_text.replace('"', '\\"')
    content = re.sub(
        r'(reference_prompt_text:\s*").*?(")',
        f'\\1{escaped_prompt}\\2',
        content
    )
    with open("config.yaml", "w", encoding="utf-8") as f:
        f.write(content)

@config_bp.route('/voice_clone', methods=['POST'])
def handle_voice_clone():
    if 'audio' not in request.files or 'prompt_text' not in request.form:
        return jsonify({"error": "Missing audio file or prompt_text"}), 400
        
    audio_file = request.files['audio']
    prompt_text = request.form['prompt_text']
    
    if audio_file.filename == '':
        return jsonify({"error": "No selected file"}), 400
        
    save_dir = os.path.join("charvoice", "custom")
    os.makedirs(save_dir, exist_ok=True)
    
    file_ext = os.path.splitext(audio_file.filename)[1]
    save_path = os.path.join(save_dir, f"cloned_voice_{int(time.time())}{file_ext}")
    audio_file.save(save_path)
    
    cfg = current_app.config['ALICE_CFG']
    cfg['tts']['reference_audio_path'] = save_path
    cfg['tts']['reference_prompt_text'] = prompt_text
    
    update_config_voice(save_path, prompt_text)
    return jsonify({"status": "success", "msg": "Voice cloned successfully!", "path": save_path})

def update_config_background(bg_path):
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

@config_bp.route('/upload_background', methods=['POST'])
def handle_upload_background():
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
    
    cfg = current_app.config['ALICE_CFG']
    if 'system' not in cfg: cfg['system'] = {}
    cfg['system']['background_image'] = web_path
    
    update_config_background(web_path)
    return jsonify({"status": "success", "msg": "Background updated!", "path": web_path})
