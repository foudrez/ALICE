"""
Auto-compress tool — delegates to the L3 distillation layer.

This is a thin wrapper that maintains backward compatibility for any code
that calls compress_and_save_memory() directly. The actual work is now
handled by the MemoryManager's consolidate() method.
"""

import sqlite3


def compress_and_save_memory(history, config, mem=None):
    """Compress conversation history into long-term memory.
    
    If a MemoryManager instance is provided, delegates to L3 consolidation.
    Otherwise falls back to the legacy direct-LLM summarization.
    
    Args:
        history: list of {"speaker": ..., "text": ...} dicts
        config: ALICE config dict
        mem: optional MemoryManager instance for L3 delegation
    """
    if len(history) < 2:
        return  # Don't save if we barely talked

    # New path: delegate to L3 via MemoryManager
    if mem is not None:
        print("\n[🧠 ALICE is consolidating memories before shutting down...]")
        try:
            mem.consolidate(config)
            print("[✅ Memory consolidation complete.]")
        except Exception as e:
            print(f"[Memory Consolidation Error: {e}]")
            # Fall through to legacy path
            _legacy_compress(history, config)
        return

    # Legacy path: direct LLM summarization (kept as fallback)
    _legacy_compress(history, config)


def _legacy_compress(history, config):
    """Original direct-LLM compression logic (fallback)."""
    import requests

    print("\n[🧠 ALICE is compressing memories before shutting down...]")

    convo = "\n".join([f"{msg['speaker']}: {msg['text']}" for msg in history])
    sys_prompt = (
        "You are a memory compressor. Summarize the key facts, user preferences, "
        "and important events from this conversation in exactly 1 or 2 short sentences. "
        "Focus ONLY on what the AI should remember about the user for tomorrow."
    )

    backend = config['llm']['backend'].lower()
    model = config['llm']['model']
    summary = ""

    try:
        if backend == "ollama":
            url = "http://localhost:11434/api/generate"
            payload = {"model": model, "prompt": convo, "system": sys_prompt, "stream": False}
            summary = requests.post(url, json=payload).json()['response']

        elif backend == "llama.cpp":
            url = "http://localhost:8080/completion"
            payload = {"prompt": f"{sys_prompt}\n\nConversation:\n{convo}\n\nSummary:", "n_predict": 64}
            summary = requests.post(url, json=payload).json()['content'].strip()

        if summary:
            if summary.startswith("- "):
                summary = summary[2:]
            db_path = config.get('memory', {}).get('db_path', 'alice_memory.db')
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO summaries (content) VALUES (?)", (summary,))
            conn.commit()
            conn.close()

            try:
                import chromadb
                import uuid
                chroma_client = chromadb.PersistentClient(path=db_path + "_chroma")
                chroma_collection = chroma_client.get_or_create_collection(name="long_term_memory")
                chroma_collection.add(
                    documents=[summary],
                    ids=[str(uuid.uuid4())]
                )
                print("[✅ Memories successfully archived to ChromaDB and SQLite!]")
            except ImportError:
                print("[✅ Memories successfully archived to SQLite database! (ChromaDB not installed)]")
            except Exception as e:
                print(f"[✅ Memories successfully archived to SQLite database! (ChromaDB Error: {e})]")

    except Exception as e:
        print(f"[Memory Save Error: {e}]")