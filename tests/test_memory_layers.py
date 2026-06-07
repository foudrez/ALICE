"""
Smoke test for the 4-layer memory system.
Uses a temporary SQLite database to verify all layers initialize,
store data, and produce the correct output formats.
"""

import os
import sys
import sqlite3
import tempfile

# Make sure we can import from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.l1_buffer import L1Buffer
from memory.l2_events import L2EventExtractor
from memory.l3_distiller import L3Distiller
from memory.l4_emotions import L4EmotionalState
from memory.memory_manager import MemoryManager


def test_l1_buffer():
    """Test L1: short-term buffer stores and trims correctly."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        # Create the messages table (normally done by MemoryManager)
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                speaker TEXT, content TEXT
            )
        """)
        conn.commit()
        conn.close()

        buf = L1Buffer(buffer_size=3, db_path=db_path)

        # Add 4 turns (8 messages) — should trim to last 3 turns (6 messages)
        for i in range(4):
            buf.add("User", f"Hello {i}")
            buf.add("ALICE", f"Hi {i}")

        window = buf.get_window()
        assert len(window) == 6, f"Expected 6 messages, got {len(window)}"
        assert window[0]["text"] == "Hello 1", f"Expected 'Hello 1', got '{window[0]['text']}'"

        recent = buf.get_recent(n=2)
        assert len(recent) == 2
        assert recent[-1]["text"] == "Hi 3"

        history = buf.get_history_for_llm()
        assert "timestamp" not in history[0], "Legacy format should not have timestamps"

        print("[✅ L1 Buffer] All tests passed")
    finally:
        os.unlink(db_path)


def test_l2_schema():
    """Test L2: event extraction table is created with correct schema."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        extractor = L2EventExtractor(db_path=db_path)

        # Verify table exists with correct columns
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(l2_events)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        expected = {"id", "timestamp", "event_type", "subject", "detail", "importance", "emotion", "distilled", "source_turn_id"}
        assert columns == expected, f"Schema mismatch: {columns} != {expected}"

        # Verify undistilled query works on empty table
        assert extractor.get_undistilled() == []
        assert extractor.get_undistilled_count() == 0

        print("[✅ L2 Events] All tests passed")
    finally:
        os.unlink(db_path)


def test_l3_schema():
    """Test L3: knowledge table is created with correct schema."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        distiller = L3Distiller(db_path=db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(l3_knowledge)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        expected = {"id", "created_at", "updated_at", "category", "content", "importance", "access_count"}
        assert columns == expected, f"Schema mismatch: {columns} != {expected}"

        assert distiller.get_all() == []
        assert distiller.get_top_knowledge() == ""

        print("[✅ L3 Distiller] All tests passed")
    finally:
        os.unlink(db_path)
        # Clean up ChromaDB dir if created
        chroma_dir = db_path + "_chroma"
        if os.path.exists(chroma_dir):
            import shutil
            shutil.rmtree(chroma_dir)


def test_l4_emotional_state():
    """Test L4: emotional state initializes and updates correctly."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        emo = L4EmotionalState(db_path=db_path, decay_halflife_hours=48.0)

        # Check initial state
        state = emo.get_state()
        assert state["valence"] == 0.0, f"Expected valence 0.0, got {state['valence']}"
        assert state["trust_level"] == 0.3, f"Expected trust 0.3, got {state['trust_level']}"
        assert state["last_mood"] == "neutral"

        # Send some positive emotions
        emo.update([
            {"emotion": "happy", "importance": 4, "timestamp": "2025-01-01T12:00:00"},
            {"emotion": "grateful", "importance": 5, "timestamp": "2025-01-01T12:01:00"},
        ])

        state = emo.get_state()
        assert state["valence"] > 0, f"Valence should be positive, got {state['valence']}"
        assert state["trust_level"] > 0.3, f"Trust should have grown, got {state['trust_level']}"
        assert state["interaction_count"] == 1

        # Check prompt context generation
        ctx = emo.get_prompt_context()
        assert isinstance(ctx, str) and len(ctx) > 10, f"Context too short: '{ctx}'"

        # Send negative emotion — valence should decrease
        old_valence = state["valence"]
        emo.update([
            {"emotion": "angry", "importance": 5, "timestamp": "2025-01-01T12:02:00"},
        ])
        state = emo.get_state()
        assert state["valence"] < old_valence, "Valence should decrease after anger"

        print("[✅ L4 Emotions] All tests passed")
    finally:
        os.unlink(db_path)


def test_memory_manager_integration():
    """Test: MemoryManager orchestrates all layers correctly."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        config = {
            "memory": {
                "max_history": 5,
                "db_path": db_path,
                "l1_buffer_size": 5,
                "l2_enabled": False,  # Disable LLM calls for this test
                "l4_enabled": True,
                "l3_consolidation_threshold": 100,
            },
            "llm": {"backend": "llama.cpp", "model": "default"},
        }

        mem = MemoryManager(
            history_limit=5,
            db_path=db_path,
            config=config,
        )

        # Test backward-compatible API
        mem.add_to_history("User", "Hello ALICE!")
        mem.add_to_history("ALICE", "Hey! What's up?")
        mem.add_to_history("User", "I like dark roast coffee")
        mem.add_to_history("ALICE", "Noted! Dark roast it is.")

        history = mem.get_history()
        assert len(history) == 4, f"Expected 4 messages, got {len(history)}"

        # Test new API
        context = mem.get_context_for_prompt(query_text="coffee")
        assert isinstance(context, str)

        # Test L4 state access
        state = mem.get_emotional_state()
        assert "valence" in state
        assert "trust_level" in state

        # Test query_long_term_memory returns a string (empty is fine for test)
        result = mem.query_long_term_memory("coffee")
        assert isinstance(result, str)

        # Test load_long_term_memory returns a string
        ltm = mem.load_long_term_memory()
        assert isinstance(ltm, str)

        print("[✅ MemoryManager] All integration tests passed")
    finally:
        os.unlink(db_path)
        chroma_dir = db_path + "_chroma"
        if os.path.exists(chroma_dir):
            import shutil
            shutil.rmtree(chroma_dir)


if __name__ == "__main__":
    print("\n=== 4-Layer Memory System Smoke Tests ===\n")
    test_l1_buffer()
    test_l2_schema()
    test_l3_schema()
    test_l4_emotional_state()
    test_memory_manager_integration()
    print("\n=== ALL TESTS PASSED ===\n")
