import os
import re
import asyncio
import logging
from openai import AsyncOpenAI
from core.event_bus import EventBus
from memory.memory_manager import MemoryManager

class RemoteBrain:
    def __init__(self, bus: EventBus, memory: MemoryManager):
        self.bus = bus
        self.memory = memory
        
        # Uses OpenRouter, OpenAI, or local vLLM API endpoints
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.client = AsyncOpenAI(api_key=self.api_key)
        self.model_name = "gpt-4o-mini" # Fast, cheap, capable
        
        logging.info(f"[Brain] Initialized Remote LLM ({self.model_name})")
        self.bus.subscribe("USER_SPOKE", self._on_user_spoke)

    async def _on_user_spoke(self, text: str):
        if not self.api_key:
            logging.error("[Brain] Missing API Key in .env!")
            return

        context = self.memory.get_full_context(text)
        logging.info("[Brain] Contacting remote neural network...")
        
        try:
            stream = await self.client.chat.completions.create(
                model=self.model_name,
                messages=context,
                stream=True,
                max_tokens=150
            )

            full_response = ""
            current_sentence = ""

            async for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    token = chunk.choices[0].delta.content
                    full_response += token
                    current_sentence += token
                    
                    # Stream to Discord/WebUI
                    await self.bus.publish("LLM_TOKEN_GENERATED", token)

                    # Sentence chunking for TTS
                    if re.search(r'[.!?]\s*$', current_sentence):
                        sentence_to_speak = current_sentence.strip()
                        await self.bus.publish("SENTENCE_READY_FOR_TTS", sentence_to_speak)
                        current_sentence = ""

            self.memory.add_message("assistant", full_response.strip())
            logging.info(f"[Brain] Thought complete: {full_response.strip()}")

        except Exception as e:
            logging.error(f"[Brain] Remote inference failed: {e}")