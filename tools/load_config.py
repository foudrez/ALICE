import yaml
import os

def load_config():
    with open("config.yaml", "r", encoding="utf-8") as file:
        cfg = yaml.safe_load(file)
        
    motions_dir = os.path.join("webui", "models", "motions")
    if os.path.exists(motions_dir):
        if "animation" not in cfg:
            cfg["animation"] = {}
        if "fbx_mapping" not in cfg["animation"]:
            cfg["animation"]["fbx_mapping"] = {}
        if "custom_actions" not in cfg["animation"]:
            cfg["animation"]["custom_actions"] = {}
            
        fbx_mapping = cfg["animation"]["fbx_mapping"]
        custom_actions = cfg["animation"]["custom_actions"]
        
        for category in os.listdir(motions_dir):
            cat_path = os.path.join(motions_dir, category)
            if os.path.isdir(cat_path):
                fbx_files = [f for f in os.listdir(cat_path) if f.lower().endswith('.fbx')]
                if not fbx_files:
                    continue
                    
                if category.lower() in ["actions", "dances"]:
                    # map to custom actions
                    for fbx in fbx_files:
                        action_name = os.path.splitext(fbx)[0]
                        custom_actions[action_name] = f"{category}/{fbx}"
                else:
                    # map to fbx_mapping (emotion/state)
                    fbx_paths = [f"{category}/{fbx}" for fbx in fbx_files]
                    fbx_mapping[category.lower()] = fbx_paths

    return cfg