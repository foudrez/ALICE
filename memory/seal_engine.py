import os
import yaml
import asyncio
import logging
from core.event_bus import EventBus
from memory.vector_db.chroma_store import VectorMemory
# In a full implementation, you would pass your LLM instance here
# from modules.brain.local_llm import LocalBrain 

class SealEngine:
    def __init__(self, bus: EventBus, l2_memory: VectorMemory, llm_engine):
        self.bus = bus
        self.l2_memory = l2_memory
        self.llm = llm_engine
        self.identity_file = "config/identity/character.yaml"
        self.idle_timeout = 300  # Run reflection after 5 minutes of silence
        self._timer_task = None
        
        # Listen for user activity to reset the sleep timer
        self.bus.subscribe("USER_SPOKE", self._reset_idle_timer)
        asyncio.create_task(self._reset_idle_timer(None))

    async def _reset_idle_timer(self, _):
        """Resets the countdown to the next reflection cycle."""
        if self._timer_task:
            self._timer_task.cancel()
        self._timer_task = asyncio.create_task(self._wait_and_reflect())

    async def _wait_and_reflect(self):
        """Waits for the user to go idle, then triggers memory consolidation."""
        try:
            await asyncio.sleep(self.idle_timeout)
            logging.info("[SEAL] User is idle. Initiating cognitive reflection...")
            await self._run_evolution_cycle()
        except asyncio.CancelledError:
            # User spoke, timer was cancelled
            pass

    async def _run_evolution_cycle(self):
        """The core SEAL loop: Extract, Synthesize, Update."""

        # 1. Fetch recent memories (e.g., the last 20 interactions)
        # For demonstration, we simulate fetching recent DB entries
        recent_context = "User mentioned they want to build a Minecraft bot. User prefers Python."

        prompt = f"""
        You are ALICE's subconscious background processor.
        Review the following recent interactions with the user:
        {recent_context}

        Extract ONLY permanent, important facts about the user or how ALICE should
        behave in the future. Return them as a simple bulleted list.
        If nothing new is learned, output 'NO_NEW_FACTS'.
        """

        # 2. Ask the LLM to extract facts
        logging.info("[SEAL] Analyzing recent memories for permanent facts...")

        # [STUB] LLM inference disabled - using mock data
        # To enable: (1) Remove this section and uncomment code below
        # (2) Ensure self.llm is properly initialized with a generation method
        # new_facts = await self.llm.generate_internal_thought(prompt)

        # Using mock data instead
        new_facts = "[MOCK] - The user is interested in Minecraft automation.\n- The user programs in Python."
        logging.warning(f"[SEAL] USING MOCK LLM - Real inference disabled. Output: {new_facts}")

        if "NO_NEW_FACTS" not in new_facts:
            self._update_character_dna(new_facts)

    def _update_character_dna(self, new_facts: str):
        """Safely rewrites the character.yaml file with new learned traits."""
        try:
            with open(self.identity_file, 'r') as file:
                dna = yaml.safe_load(file)
            
            # Clean up the LLM's bullet points and add to the list
            fact_lines = [line.replace("- ", "").strip() for line in new_facts.split("\n") if line.strip()]
            
            if 'learned_facts' not in dna:
                dna['learned_facts'] = []
                
            dna['learned_facts'].extend(fact_lines)
            
            # Deduplicate and cap the list to prevent prompt bloating (Max 20 facts)
            dna['learned_facts'] = list(set(dna['learned_facts']))[-20:]
            
            with open(self.identity_file, 'w') as file:
                yaml.dump(dna, file, default_flow_style=False, sort_keys=False)
                
            logging.info(f"[SEAL] DNA Updated. ALICE has evolved. Learned {len(fact_lines)} new facts.")
            
            # Notify the system to reload the identity on the next message
            asyncio.create_task(self.bus.publish("IDENTITY_UPDATED", dna))
            
        except Exception as e:
            logging.error(f"[SEAL] Failed to update DNA: {e}")