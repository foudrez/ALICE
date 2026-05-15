import logging
import asyncio
import aiohttp
from core.event_bus import EventBus

class NavigationAgent:
    def __init__(self, bus: EventBus):
        self.bus = bus
        # URL of a local Node.js Mineflayer bridge
        self.bridge_url = "http://127.0.0.1:3000/command"
        self.bus.subscribe("NAV_COMMAND", self._execute_pathfinding)

    async def _execute_pathfinding(self, command: dict):
        """Expected command: {'action': 'goto', 'target': 'tree'}"""
        logging.info(f"[Nav Agent] Executing spatial command: {command}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.bridge_url, json=command) as resp:
                    if resp.status == 200:
                        logging.info("[Nav Agent] Target reached.")
                        await self.bus.publish("NAV_SUCCESS", command)
        except Exception as e:
            logging.error(f"[Nav Agent] Navigation bridge offline: {e}")