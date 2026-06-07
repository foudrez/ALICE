from flask import Blueprint, request, jsonify
from tools.mcp_client import execute_mcp_tool, get_all_mcp_tools

mcp_bp = Blueprint('mcp_bp', __name__)

@mcp_bp.route('/servers', methods=['GET'])
def get_mcp_servers():
    tools = get_all_mcp_tools()
    return jsonify({"status": "success", "servers": tools})

@mcp_bp.route('/execute', methods=['POST'])
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
