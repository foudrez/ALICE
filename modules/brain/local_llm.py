import asyncio
import json
import logging
import re
from llama_cpp import ChatCompletionTool, Llama
from core.event_bus import EventBus
from core.hardware_hal import hardware
from memory.memory_manager import MemoryManager

class LocalBrain:
    def __init__(self, bus: EventBus, memory: MemoryManager,config):
        self.bus = bus
        self.memory = memory
        self.config = config

        model_path = self.config.get("models", {}).get("primary_llm", "assets/llm/google_gemma-4-E2B-it-Q4_K_M.gguf")
        
        logging.info(f"[Brain] Booting Local LLM from {model_path}...")
        try:
            self.llm = Llama(
                model_path=model_path,
                n_gpu_layers=-1 if hardware.device in ["cuda", "mps"] else 0,
                n_ctx=4096,
                verbose=False
            )
        except Exception as e:
            logging.error(f"[Brain] Failed to load LLM (Did you download the .gguf?): {e}")
            self.llm = None

        self.bus.subscribe("USER_SPOKE", self._on_user_spoke)

    async def _on_user_spoke(self, text: str):
        context = []
        # Tell the LLM what physical tools it has
        available_tools: list[ChatCompletionTool] = [
    {
        "type": "function",
        "function": {
            "name": "toggle_device",
            "description": "Turns a smart home device on or off.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string"},
                    "action": {"type": "string", "enum": ["turn_on", "turn_off"]}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Searches the internet for real-time information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                }
            }
        }
    }
    ]

        # When calling the LLM, pass the tools array
        response = self.llm.create_chat_completion(
            messages=context,
            tools= available_tools,
            tool_choice="auto", # Allows the AI to decide if it needs to use a tool
            max_tokens=150
        )

        # Check if ALICE decided to use a tool instead of just talking
        message = response["choices"][0]["message"]

        if "tool_calls" in message and message["tool_calls"]:
            for tool_call in message["tool_calls"]:
                func_name = tool_call["function"]["name"]
                arguments = json.loads(tool_call["function"]["arguments"])
                
                logging.info(f"[Brain] ALICE decided to use physical tool: {func_name}")
                
                # Fire event to the IoT subsystem
                asyncio.run_coroutine_threadsafe(
                    self.bus.publish("TOOL_CALL_REQUESTED", {
                        "name": func_name, 
                        "arguments": arguments
                    }), loop
                )
        else:
            # Standard text/voice streaming output logic...
            pass
        if not self.llm:
            logging.warning("[Brain] LLM not loaded. Bypassing.")
            return

        context = self.memory.get_full_context(text)
        logging.info("[Brain] Generating response...")
        
        # Run inference in a thread to keep the orchestrator alive
        loop = asyncio.get_running_loop()

        def run_inference():
            return self.llm.create_chat_completion(
                messages=context,
                stream=True,
                max_tokens=150
            )

        stream = await loop.run_in_executor(None, run_inference)
        
        full_response = ""
        current_sentence = ""
        
        for chunk in stream:
            emotion_match = re.search(r'\[(.*?)\]', current_sentence)
            if emotion_match:
                emotion = emotion_match.group(1).lower()
                # Tell the avatar to change its face!
                asyncio.run_coroutine_threadsafe(
                    self.bus.publish("EXPRESSION_CHANGED", emotion), loop
                )
                # Remove the tag so the TTS engine doesn't read the word "bracket happy bracket" out loud
                current_sentence = re.sub(r'\[.*?\]', '', current_sentence)
            if "content" in chunk["choices"][0]["delta"]:
                token = chunk["choices"][0]["delta"]["content"]
                full_response += token
                current_sentence += token
                
                # Stream to UI
                asyncio.run_coroutine_threadsafe(
                    self.bus.publish("LLM_TOKEN_GENERATED", token), loop
                )

                # Chunking logic for Voice Pipeline: Send to TTS when a sentence ends
                if re.search(r'[.!?]\s*$', current_sentence):
                    sentence_to_speak = current_sentence.strip()
                    asyncio.run_coroutine_threadsafe(
                        self.bus.publish("SENTENCE_READY_FOR_TTS", sentence_to_speak), loop
                    )
                    current_sentence = ""

        # Save AI's response to memory
        self.memory.add_message("assistant", full_response.strip())
        logging.info(f"[Brain] Completed thought: {full_response.strip()}")