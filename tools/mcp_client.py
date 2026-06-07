import asyncio
import os
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Define the paths to the available MCP servers
MCP_SERVERS = {
    "schedule": os.path.join("mcp_servers", "schedule", "server.py")
}

async def execute_mcp_tool_async(server_name: str, tool_name: str, tool_args: dict) -> str:
    """
    Connects to an MCP server via stdio, executes a tool, and returns the result.
    """
    if server_name not in MCP_SERVERS:
        return f"[Error] Unknown MCP server: {server_name}"
        
    server_script = MCP_SERVERS[server_name]
    if not os.path.exists(server_script):
        return f"[Error] MCP server script not found at: {server_script}"
        
    # We use the current Python executable to launch the server
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[server_script],
        env=None
    )
    
    print(f"[MCP Client] Connecting to {server_name} server...")
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize the connection
                await session.initialize()
                
                print(f"[MCP Client] Calling tool '{tool_name}' on {server_name}...")
                
                # Call the tool
                result = await session.call_tool(tool_name, arguments=tool_args)
                
                # Parse the returned result content
                if result and hasattr(result, 'content') and len(result.content) > 0:
                    text_content = result.content[0].text
                    return text_content
                else:
                    return f"[Warning] Tool '{tool_name}' executed but returned no text content."
                    
    except Exception as e:
        print(f"[MCP Client Error] {e}")
        return f"[Error] Failed to execute MCP tool: {e}"

def execute_mcp_tool(server_name: str, tool_name: str, tool_args: dict) -> str:
    """
    Synchronous wrapper for executing an MCP tool.
    Used by background threads in the LLM loop.
    """
    return asyncio.run(execute_mcp_tool_async(server_name, tool_name, tool_args))

async def list_mcp_tools_async(server_name: str) -> list:
    """
    Connects to an MCP server via stdio and returns its list of available tools.
    """
    if server_name not in MCP_SERVERS:
        print(f"[Error] Unknown MCP server: {server_name}")
        return []
        
    server_script = MCP_SERVERS[server_name]
    if not os.path.exists(server_script):
        print(f"[Error] MCP server script not found at: {server_script}")
        return []
        
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[server_script],
        env=None
    )
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
                tools = []
                if result and hasattr(result, 'tools'):
                    for t in result.tools:
                        tools.append({
                            "name": t.name,
                            "description": t.description or "",
                            "inputSchema": t.inputSchema or {}
                        })
                return tools
    except Exception as e:
        print(f"[MCP Client Error] {e}")
        return []

def list_mcp_tools(server_name: str) -> list:
    """
    Synchronous wrapper for listing MCP tools.
    """
    return asyncio.run(list_mcp_tools_async(server_name))

_cached_mcp_tools = None

def get_all_mcp_tools() -> dict:
    """
    Returns a dictionary mapping server names to their available tools.
    """
    global _cached_mcp_tools
    if _cached_mcp_tools is not None:
        return _cached_mcp_tools
        
    all_tools = {}
    for server_name in MCP_SERVERS:
        all_tools[server_name] = list_mcp_tools(server_name)
    _cached_mcp_tools = all_tools
    return all_tools

if __name__ == "__main__":
    # Test execution
    print("Available tools:", get_all_mcp_tools())
    res = execute_mcp_tool("schedule", "get_current_time", {})
    print("Test Result:", res)
