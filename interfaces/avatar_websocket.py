import asyncio
import json
import logging
import websockets
from core.event_bus import EventBus

class AvatarWebSocketServer:
    def __init__(self, bus: EventBus, host="127.0.0.1", port=8080):
        self.bus = bus
        self.host = host
        self.port = port
        self.connected_clients = set()
        
        # Listen for internal events to forward to the visual avatar
        self.bus.subscribe("AVATAR_LIPSYNC", self._on_lipsync_data)
        self.bus.subscribe("EXPRESSION_CHANGED", self._on_expression)
        
    async def _register(self, websocket):
        """Registers a new frontend client (like a Three.js browser window)."""
        self.connected_clients.add(websocket)
        logging.info(f"[Avatar] Frontend connected: {websocket.remote_address}")
        try:
            await websocket.wait_closed()
        finally:
            self.connected_clients.remove(websocket)
            logging.info(f"[Avatar] Frontend disconnected: {websocket.remote_address}")

    async def _broadcast(self, message: dict):
        """Sends a JSON payload to all connected visual clients."""
        if not self.connected_clients:
            return
            
        payload = json.dumps(message)
        # Fire and forget to all clients
        await asyncio.gather(
            *[client.send(payload) for client in self.connected_clients],
            return_exceptions=True
        )

    async def _on_lipsync_data(self, text: str):
        """
        Sends the text (or phonemes) to the avatar for lip-syncing.
        In a highly advanced setup, you'd send exact audio volume amplitudes (visemes) here.
        """
        await self._broadcast({
            "type": "lipsync",
            "data": text
        })

    async def _on_expression(self, emotion: str):
        """
        Sends an emotion trigger (e.g., 'happy', 'angry') to change the Live2D/VRM blendshapes.
        """
        logging.info(f"[Avatar] Changing expression to: {emotion}")
        await self._broadcast({
            "type": "expression",
            "emotion": emotion
        })

    async def start_server(self):
        """Starts the WebSocket server in the background."""
        logging.info(f"[Avatar] Starting WebSocket Server on ws://{self.host}:{self.port}")
        try:
            async with websockets.serve(self._register, self.host, self.port):
                # Keep the server running indefinitely
                await asyncio.Future() 
        except asyncio.CancelledError:
            # Catch the shutdown signal gracefully
            logging.info("[Avatar] WebSocket server safely shut down.")