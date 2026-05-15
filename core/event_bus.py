import asyncio
from typing import Callable, Dict, List

class EventBus:
    """Asynchronous Pub/Sub message bus for decoupled module communication."""
    
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}
        self.queue = asyncio.Queue()

    def subscribe(self, event_type: str, callback: Callable):
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)

    async def publish(self, event_type: str, payload: any = None):
        """Puts an event onto the bus."""
        await self.queue.put({"type": event_type, "payload": payload})

    async def _process_events(self):
        """Background task that routes events to subscribers."""
        while True:
            event = await self.queue.get()
            event_type = event["type"]
            if event_type in self.subscribers:
                for callback in self.subscribers[event_type]:
                    # Fire and forget callbacks to prevent blocking
                    asyncio.create_task(callback(event["payload"]))
            self.queue.task_done()

    async def start(self):
        asyncio.create_task(self._process_events())