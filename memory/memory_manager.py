import logging
from typing import List, Dict
from memory.vector_db.chroma_store import VectorMemory
import yaml
import logging
import uuid

class MemoryManager:
    def __init__(self):
        self.identity = self._load_identity()
        self.conversation_history: List[Dict[str, str]] = []
        self.max_history = 100  # Increased from 10: rolling window of recent chat

        # Initialize L2 Cache: Long-term persistent memory
        self.l2_memory = VectorMemory()
        self.seen_message_ids: set = set()


    def add_message(self, role: str, content: str, msg_id: str = None) -> str:
        """Saves a message to both short-term RAM and long-term disk. Returns message ID."""
        if msg_id is None:
            msg_id = str(uuid.uuid4())

        if msg_id in self.seen_message_ids:
            return msg_id

        self.seen_message_ids.add(msg_id)

        # 1. Save to L1 Cache (Short-term RAM)
        self.conversation_history.append({
            "role": role,
            "content": content,
            "id": msg_id
        })
        if len(self.conversation_history) > self.max_history:
            old_msg = self.conversation_history.pop(0)
            self.seen_message_ids.discard(old_msg.get("id"))
            
        # 2. Save to L2 Cache (Vector DB)
        self.l2_memory.add_memory(content, role)

    def get_full_context(self, new_user_message: str) -> List[Dict[str, str]]:
        """Assembles the system prompt by fusing Identity, Long-Term Memory, and Short-Term History."""
        
        # 1. Search Vector DB for relevant past context
        logging.info(f"[Memory] Searching archives for context related to: '{new_user_message}'")
        recalled_memories = self.l2_memory.query_memory(new_user_message)
        
        # 2. Build the dynamic system prompt
        dynamic_system_prompt = self.identity
        
        if recalled_memories:
            logging.info(f"[Memory] Recalled {len(recalled_memories)} relevant memories.")
            memory_string = "\n".join(recalled_memories)
            dynamic_system_prompt += f"\n\n[RECALLED PAST MEMORIES]\n{memory_string}\n"
            
        # 3. Add the new message to history
        self.add_message("user", new_user_message)
        
        # 4. Assemble the final OpenAI/Llama-compatible message array
        messages = [{"role": "system", "content": dynamic_system_prompt}]
        messages.extend(self.conversation_history)
        
        return messages
    def _load_identity(self) -> str:
        """Loads the base persona and the dynamically learned facts."""
        try:
            with open("config/identity/character.yaml", 'r') as file:
                dna = yaml.safe_load(file)
                
            persona = dna.get('base_persona', '')
            facts = "\n".join([f"- {f}" for f in dna.get('learned_facts', [])])
            
            full_identity = f"{persona}\n\n[Core Directives & Learned Facts about User]\n{facts}"
            return full_identity
            
        except FileNotFoundError:
            logging.warning("[Memory] character.yaml not found. Using fallback identity.")
            return "You are ALICE. Be helpful and concise."
            