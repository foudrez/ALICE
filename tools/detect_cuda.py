import torch
import re

def auto_configure_yaml():
    # 1. Detect Hardware (Ignore what the YAML currently says)
    if torch.cuda.is_available():
        target_device = "cuda"
        target_is_half = "true"  # String for YAML
        python_is_half = True    # Boolean for Python
        print("[Hardware] 🟢 Nvidia GPU (CUDA) detected.")
    else:
        target_device = "cpu"
        target_is_half = "false"
        python_is_half = False
        print("[Hardware] 🟡 CUDA not found. Falling back to CPU.")

    # 2. Read the YAML file as raw text (to preserve comments)
    try:
        with open("config.yaml", "r", encoding="utf-8") as f:
            yaml_text = f.read()

        # 3. Find and overwrite the exact settings using Regex
        # Overwrites: device: "cpu" -> device: "cuda"
        yaml_text = re.sub(r'device:\s*".*"', f'device: "{target_device}"', yaml_text)
        
        # Overwrites: is_half: false -> is_half: true
        yaml_text = re.sub(r'is_half:\s*(true|false|True|False)', f'is_half: {target_is_half}', yaml_text)

        # 4. Save the corrected text back to the file
        with open("config.yaml", "w", encoding="utf-8") as f:
            f.write(yaml_text)
            
        print(f"[Hardware] 💾 Auto-configured config.yaml (device: {target_device}, is_half: {target_is_half})")
        
    except FileNotFoundError:
        print("[Hardware] ⚠️ config.yaml not found! Please create it.")

    # 5. Return the true values for the rest of the script to use
    return target_device, python_is_half

# Run this exactly once when the module is imported
COMPUTE_DEVICE, IS_HALF_PRECISION = auto_configure_yaml()