import logging
from core.event_bus import EventBus

class APIAgent:
    def __init__(self, bus: EventBus):
        self.bus = bus
        self.bus.subscribe("GAME_API_COMMAND", self._handle_turn)

    async def _handle_turn(self, action: str):
        """Translates an LLM thought into a deterministic game state move."""
        logging.info(f"[API Agent] Committing move: {action}")
        # e.g., if action == "e2e4": send_to_chess_engine("e2e4")
        
        # Simulate returning the new board state to the LLM
        new_state = "Opponent played e7e5."
        await self.bus.publish("GAME_STATE_CHANGED", new_state)