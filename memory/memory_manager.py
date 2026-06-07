"""
MemoryManager — 4-Layer Cognitive Memory Orchestrator

Coordinates all memory layers and provides a unified API for the rest of ALICE.
Backward-compatible with the old MemoryManager interface so main.py and webui.py
continue to work without breaking.

Layer Architecture:
    L1 (Short-Term Buffer)  → what just happened
    L2 (Event Extraction)   → structured facts & events  
    L3 (Long-Term Distill)  → condensed knowledge
    L4 (Emotional State)    → persistent mood & relationship
"""

import os
import re
import shutil
import sqlite3
import threading
import uuid

try:
    import chromadb
except ImportError:
    chromadb = None

from memory.l1_buffer import L1Buffer
from memory.l2_events import L2EventExtractor
from memory.l3_distiller import L3Distiller
from memory.l4_emotions import L4EmotionalState


class MemoryManager:
    """Orchestrates the 4-layer cognitive memory system.
    
    Provides both the new layered API and backward-compatible methods
    so existing callers (main.py, webui.py, llm.py) continue to work.
    """

    def __init__(self, history_limit=10, db_path="alice_memory.db", config=None):
        self.history_limit = history_limit
        self.db_path = db_path
        self._config = config or {}
        
        # Extract layer-specific config
        mem_cfg = self._config.get("memory", {})
        buffer_size = mem_cfg.get("l1_buffer_size", history_limit)
        decay_halflife = mem_cfg.get("l4_decay_halflife_hours", 48.0)
        trust_rate = mem_cfg.get("l4_trust_growth_rate", 0.02)

        # --- Initialize base schema (legacy tables) ---
        self._init_legacy_db()

        # --- Run legacy migrations (memory.txt, chat_log.txt) ---
        self._auto_migrate_legacy()

        # --- Initialize the 4 layers ---
        self.l1 = L1Buffer(buffer_size=buffer_size, db_path=db_path)
        self.l2 = L2EventExtractor(db_path=db_path)
        self.l3 = L3Distiller(db_path=db_path)
        self.l4 = L4EmotionalState(
            db_path=db_path,
            decay_halflife_hours=decay_halflife,
            trust_growth_rate=trust_rate,
        )

        # Hydrate L1 from database
        self.l1.load_from_db()

        # Config flags
        self._l2_enabled = mem_cfg.get("l2_enabled", True)
        self._l2_async = mem_cfg.get("l2_async", True)
        self._l4_enabled = mem_cfg.get("l4_enabled", True)
        self._consolidation_threshold = mem_cfg.get("l3_consolidation_threshold", 20)
        self._consolidate_on_exit = mem_cfg.get("l3_consolidate_on_exit", True)

        print("[🧠 4-Layer Memory System Initialized]")
        print(f"    L1 Buffer: {buffer_size} turns | L2 Extraction: {'ON' if self._l2_enabled else 'OFF'}")
        print(f"    L3 Threshold: {self._consolidation_threshold} events | L4 Emotions: {'ON' if self._l4_enabled else 'OFF'}")

    # ==================================================================
    # BACKWARD-COMPATIBLE API (used by main.py, webui.py, llm.py)
    # ==================================================================

    def add_to_history(self, speaker: str, text: str, session_id="local"):
        """Add a message to short-term memory and trigger background processing.
        
        This is the main entry point called after each conversational turn.
        Replaces the old flat add_to_history with layered processing.
        """
        # L1: Write to short-term buffer + SQLite
        self.l1.add(speaker, text, session_id=session_id)

    def get_history(self, session_id="local") -> list[dict]:
        """Return chat history in the legacy format for LLM prompt building.
        
        Returns list of {"speaker": ..., "text": ...}
        """
        return self.l1.get_history_for_llm(session_id)

    def load_long_term_memory(self) -> str:
        """Load all long-term knowledge as a formatted string.
        
        Now returns L3 knowledge instead of raw summaries.
        Falls back to legacy summaries if L3 is empty.
        """
        l3_knowledge = self.l3.get_top_knowledge(n=15)
        if l3_knowledge:
            return l3_knowledge

        # Fallback: legacy summaries table
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT content FROM summaries ORDER BY timestamp ASC")
            rows = cursor.fetchall()
            conn.close()
            if rows:
                return "\n".join([f"- {row[0]}" for row in rows])
        except Exception as e:
            print(f"[Memory] Error loading legacy summaries: {e}")
        return ""

    def query_long_term_memory(self, query_text: str, n_results=5) -> str:
        """Semantic search across L3 knowledge + legacy summaries.
        
        Combines results from both the new L3 collection and the old
        'long_term_memory' ChromaDB collection for full coverage.
        """
        results = []

        # Query L3 knowledge
        l3_result = self.l3.query(query_text, n_results=n_results)
        if l3_result:
            results.append(l3_result)

        # Query legacy summaries (from before the L3 migration)
        legacy = self.l3.query_legacy_summaries(query_text, n_results=3)
        if legacy:
            results.append(legacy)

        return "\n".join(results) if results else ""

    def compress_and_archive(self, config, session_id="local"):
        """Legacy compression method — now triggers L3 consolidation.
        
        Kept for backward compatibility with auto_compress.py and
        any code that calls this directly.
        """
        self.consolidate(config)

    # ==================================================================
    # NEW LAYERED API
    # ==================================================================

    def process_turn(self, speaker: str, text: str, config: dict, session_id="local"):
        """Full pipeline for processing a single conversational turn.
        
        Convenience method that combines add_to_history + extract_events.
        Callers can use this instead of calling them separately.
        """
        # L1: Store in short-term buffer
        self.add_to_history(speaker, text, session_id=session_id)

        # Only trigger extraction after ALICE responds (we have a full turn)
        if speaker == "ALICE":
            self.extract_events(config, session_id=session_id)

    def extract_events(self, config: dict, session_id="local"):
        """Trigger L2 event extraction on the most recent turn.
        
        Also updates L4 emotional state and checks if L3 consolidation
        should be triggered based on the threshold.
        """
        if not self._l2_enabled:
            return

        # Get the last 4 messages for L2 to analyze
        recent = self.l1.get_recent(n=4, session_id=session_id)
        if not recent:
            return

        # L2: Extract events (async by default)
        self.l2.extract_events(recent, config, async_mode=self._l2_async)

        # L4: Record interaction and process emotional signals
        if self._l4_enabled:
            # Run emotional update in background since L2 might be async
            def _emotional_update():
                import time
                # Small delay to let L2 finish writing if async
                if self._l2_async:
                    time.sleep(3)
                emotions = self.l2.get_recent_emotions(n=5)
                if emotions:
                    self.l4.update(emotions)
                else:
                    self.l4.record_interaction()

            threading.Thread(target=_emotional_update, daemon=True).start()

        # Check if L3 consolidation threshold is reached
        undistilled_count = self.l2.get_undistilled_count()
        if undistilled_count >= self._consolidation_threshold:
            print(f"[🧠 Memory] {undistilled_count} undistilled events — triggering L3 consolidation")
            self.consolidate(config)

    def consolidate(self, config: dict):
        """Trigger L3 long-term distillation.
        
        Merges all undistilled L2 events with existing L3 knowledge.
        Safe to call at any time (on exit, on threshold, manually).
        """
        undistilled = self.l2.get_undistilled()
        if not undistilled:
            return

        consumed_ids = self.l3.consolidate(undistilled, config)
        if consumed_ids:
            self.l2.mark_distilled(consumed_ids)

    def get_context_for_prompt(self, query_text: str = "", n_results=5) -> str:
        """Assemble a structured memory context string from all 4 layers.
        
        This is the primary method for injecting memory into the LLM prompt.
        Returns a formatted block that can be inserted into the system prompt.
        """
        sections = []

        # L4: Emotional state (always included if enabled)
        if self._l4_enabled:
            emotional_ctx = self.l4.get_prompt_context()
            if emotional_ctx:
                sections.append(f"[EMOTIONAL STATE]: {emotional_ctx}")

        # L3: Core knowledge (top entries)
        top_knowledge = self.l3.get_top_knowledge(n=10)
        if top_knowledge:
            sections.append(f"[KNOWN FACTS]:\n{top_knowledge}")

        # L3: Semantically relevant memories (if query provided)
        if query_text:
            relevant = self.query_long_term_memory(query_text, n_results=n_results)
            if relevant:
                sections.append(f"[RELEVANT MEMORIES]:\n{relevant}")

        if not sections:
            return ""

        return (
            "=== ALICE'S INTERNAL STATE ===\n"
            + "\n\n".join(sections)
            + "\n=============================="
        )

    def get_emotional_state(self) -> dict:
        """Return the raw L4 emotional state dict."""
        return self.l4.get_state()

    # ==================================================================
    # LEGACY DATABASE + MIGRATION (preserved from original)
    # ==================================================================

    def _init_legacy_db(self):
        """Create the original messages and summaries tables.
        
        These are kept for backward compatibility and as the raw data source.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                speaker TEXT,
                content TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                content TEXT
            )
        """)
        conn.commit()
        conn.close()

    def _auto_migrate_legacy(self):
        """Migrate legacy flat files (memory.txt, chat_log.txt) to SQLite.
        
        This is the original migration logic, preserved so that users
        upgrading from older versions don't lose their data.
        """
        # Migrate memory.txt
        if os.path.exists("memory.txt"):
            print("\n[🧠 ALICE is migrating memory.txt to SQLite...]")
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                with open("memory.txt", "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            if line.startswith("- "):
                                line = line[2:]
                            cursor.execute("SELECT 1 FROM summaries WHERE content = ?", (line,))
                            if not cursor.fetchone():
                                cursor.execute("INSERT INTO summaries (content) VALUES (?)", (line,))
                conn.commit()
                conn.close()
                shutil.move("memory.txt", "memory.txt.bak")
                print("[✅ Successfully migrated and backed up memory.txt]")
            except Exception as e:
                print(f"[Migration Error memory.txt: {e}]")

        # Migrate chat_log.txt
        if os.path.exists("chat_log.txt"):
            print("\n[🧠 ALICE is migrating chat_log.txt to SQLite...]")
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                pattern = re.compile(r'^\[(.*?)\]\s*([^:]+):\s*(.*)$')
                with open("chat_log.txt", "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        match = pattern.match(line)
                        if match:
                            timestamp_str, speaker, content = match.groups()
                            cursor.execute(
                                "SELECT 1 FROM messages WHERE timestamp = ? AND speaker = ? AND content = ?",
                                (timestamp_str, speaker, content),
                            )
                            if not cursor.fetchone():
                                cursor.execute(
                                    "INSERT INTO messages (timestamp, speaker, content) VALUES (?, ?, ?)",
                                    (timestamp_str, speaker, content),
                                )
                conn.commit()
                conn.close()
                shutil.move("chat_log.txt", "chat_log.txt.bak")
                print("[✅ Successfully migrated and backed up chat_log.txt]")
            except Exception as e:
                print(f"[Migration Error chat_log.txt: {e}]")

        # Migrate SQLite summaries to legacy ChromaDB collection
        if chromadb is not None:
            try:
                chroma_path = self.db_path + "_chroma"
                client = chromadb.PersistentClient(path=chroma_path)
                collection = client.get_or_create_collection(name="long_term_memory")
                if collection.count() == 0:
                    print("\n[🧠 ALICE is migrating SQLite summaries to ChromaDB...]")
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT content FROM summaries")
                    rows = cursor.fetchall()
                    conn.close()
                    if rows:
                        docs = [row[0] for row in rows]
                        ids = [str(uuid.uuid4()) for _ in rows]
                        collection.add(documents=docs, ids=ids)
                        print("[✅ Successfully migrated summaries to ChromaDB!]")
            except Exception as e:
                print(f"[ChromaDB Migration Error: {e}]")