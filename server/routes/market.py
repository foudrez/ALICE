import os
import requests
from flask import Blueprint, request, jsonify

market_bp = Blueprint('market_bp', __name__)

@market_bp.route('/market/download', methods=['POST'])
def download_animation_from_market():
    data = request.json
    url = data.get('url')
    name = data.get('name', 'DownloadedAnimation')
    category = data.get('category', 'emotions')
    
    if not url:
        return jsonify({"error": "No URL provided"}), 400
        
    try:
        save_dir = os.path.join('webui', 'models', 'motions', category)
        os.makedirs(save_dir, exist_ok=True)
        
        filename = f"{name}.fbx"
        save_path = os.path.join(save_dir, filename)
        
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        return jsonify({"status": "success", "msg": f"Successfully downloaded {filename}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
