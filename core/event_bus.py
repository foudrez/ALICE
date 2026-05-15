import asyncio
import uuid
from typing import Callable, Dict, List

class EventBus:
    """Asynchronous Pub/Sub message bus for decoupled module communication."""

    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}
        self.queue = asyncio.Queue()
        self.event_counter = 0
        self.processed_ids: set = set()

    def subscribe(self, event_type: str, callback: Callable):
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)

    async def publish(self, event_type: str, payload: any = None, msg_id: str = None):
        """Puts an event onto the bus with unique ID and sequence number."""
        if msg_id is None:
            msg_id = str(uuid.uuid4())

        self.event_counter += 1
        await self.queue.put({
            "type": event_type,
            "payload": payload,
            "id": msg_id,
            "sequence": self.event_counter
        })

    async def _process_events(self):
        """Background task that routes events to subscribers."""
        while True:
            event = await self.queue.get()
            event_type = event["type"]
            event_id = event.get("id")

            if event_id in self.processed_ids:
                self.queue.task_done()
                continue

            self.processed_ids.add(event_id)
            if len(self.processed_ids) > 10000:
                self.processed_ids = set(list(self.processed_ids)[-5000:])

            if event_type in self.subscribers:
                for callback in self.subscribers[event_type]:
                    asyncio.create_task(callback(event["payload"]))
            self.queue.task_done()

    async def start(self):
        asyncio.create_task(self._process_events())