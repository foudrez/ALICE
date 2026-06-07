import sys
import os
import json

# Ensure we can import from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.load_config import load_config
from memory.memory_manager import MemoryManager

def print_separator(title):
    print(f"\n{'='*20} {title.upper()} {'='*20}")

def main():
    print("Initializing Memory Debugger...")
    cfg = load_config()
    
    # We just need to read the db, not start heavy LLM inference
    mem = MemoryManager(
        history_limit=cfg['memory'].get('max_history', 10),
        db_path=cfg.get('memory', {}).get('db_path', 'alice_memory.db'),
        config=cfg,
    )
    
    print_separator("L1: Short-Term Buffer")
    l1_history = mem.l1.get_window()
    if not l1_history:
        print("(Empty)")
    for msg in l1_history:
        print(f"[{msg['timestamp']}] {msg['speaker']}: {msg['text']}")
        
    print_separator("L2: Undistilled Events")
    l2_events = mem.l2.get_undistilled(limit=20)
    if not l2_events:
        print("(No undistilled events. All events have been consumed by L3)")
    for evt in l2_events:
        print(f"[{evt['timestamp']}] Type: {evt['event_type']} | Subject: {evt['subject']} | Emotion: {evt['emotion']}")
        print(f"  -> {evt['detail']}")

    print_separator("L3: Long-Term Knowledge (Top 10)")
    l3_knowledge = mem.l3.get_top_knowledge(n=10)
    if not l3_knowledge:
        print("(Empty)")
    else:
        print(l3_knowledge)

    print_separator("L4: Emotional State")
    state = mem.l4.get_state()
    print(json.dumps(state, indent=4))
    
    print("\n[🧠 Debugger Finished]")

if __name__ == "__main__":
    main()
