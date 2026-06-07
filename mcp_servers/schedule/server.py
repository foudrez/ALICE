from mcp.server.fastmcp import FastMCP
import datetime
import asyncio

# Create the FastMCP server
mcp = FastMCP("schedule-server")

@mcp.tool()
async def set_alarm(time_str: str, message: str) -> str:
    """
    Sets an alarm for a given time.
    
    Args:
        time_str: The time to set the alarm for (e.g. "8:00 AM" or "14:30")
        message: The message to display when the alarm goes off
    """
    # This is a skeleton implementation. In a real scenario, this would
    # schedule a local task, write to a database, or connect to Home Assistant.
    print(f"[Schedule MCP] Alarm scheduled for {time_str} with message: '{message}'")
    
    # Simulate a tiny delay for processing
    await asyncio.sleep(0.5)
    
    # Return the confirmation to the LLM context
    return f"Success: Alarm successfully set for {time_str}. Message: '{message}'."

@mcp.tool()
async def get_current_time() -> str:
    """
    Gets the current system time.
    """
    now = datetime.datetime.now()
    return f"The current time is {now.strftime('%I:%M %p')}."

if __name__ == "__main__":
    # Start the server using stdio transport (standard for local MCP microservices)
    mcp.run(transport='stdio')
