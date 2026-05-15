import asyncio
import logging
import aiohttp
import json
from core.event_bus import EventBus

class HomeAssistantMCP:
    def __init__(self, bus: EventBus):
        self.bus = bus
        # Replace with your actual Home Assistant IP and Long-Lived Access Token
        self.ha_url = "http://homeassistant.local:8123/api"
        self.ha_token = "YOUR_LONG_LIVED_ACCESS_TOKEN" 
        
        self.headers = {
            "Authorization": f"Bearer {self.ha_token}",
            "Content-Type": "application/json",
        }
        
        # Listen for the Brain requesting a tool execution
        self.bus.subscribe("TOOL_CALL_REQUESTED", self._execute_tool)

    async def get_available_tools(self) -> list:
        """
        Dynamically fetches what ALICE is allowed to do in the house.
        Passed to the LLM during the System Prompt assembly.
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": "toggle_device",
                    "description": "Turns a smart home device on or off (e.g., lights, fans).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "entity_id": {
                                "type": "string",
                                "description": "The ID of the device (e.g., light.living_room)"
                            },
                            "action": {
                                "type": "string",
                                "enum": ["turn_on", "turn_off"]
                            }
                        },
                        "required": ["entity_id", "action"]
                    }
                }
            }
        ]

    async def _execute_tool(self, tool_data: dict):
        """Executes the action requested by the LLM."""
        function_name = tool_data.get("name")
        kwargs = tool_data.get("arguments", {})
        
        if function_name == "toggle_device":
            await self._toggle_device(kwargs.get("entity_id"), kwargs.get("action"))
        else:
            logging.warning(f"[IoT] Unknown tool requested: {function_name}")

    async def _toggle_device(self, entity_id: str, action: str):
        """Sends the REST API call to Home Assistant."""
        if not entity_id or action not in ["turn_on", "turn_off"]:
            logging.error(f"[IoT] Invalid payload: {entity_id} | {action}")
            return

        domain = entity_id.split(".")[0] # e.g., 'light' from 'light.living_room'
        endpoint = f"{self.ha_url}/services/{domain}/{action}"
        payload = {"entity_id": entity_id}

        logging.info(f"[IoT] Attempting to {action} on {entity_id}...")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(endpoint, headers=self.headers, json=payload) as response:
                    if response.status == 200:
                        logging.info(f"[IoT] Success! {entity_id} is now {action}.")
                        # Tell ALICE's brain the action succeeded so she can mention it
                        await self.bus.publish("TOOL_EXECUTION_SUCCESS", f"Successfully executed {action} on {entity_id}.")
                    else:
                        error_text = await response.text()
                        logging.error(f"[IoT] HA Error {response.status}: {error_text}")
                        await self.bus.publish("TOOL_EXECUTION_FAILED", f"Failed to control {entity_id}.")
        except Exception as e:
            logging.error(f"[IoT] Connection to Home Assistant failed: {e}")