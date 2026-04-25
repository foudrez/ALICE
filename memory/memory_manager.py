import os
import requests
import json
from datetime import datetime

class MemoryManager:
    def __init__(self, history_limit=10):
        self.chat_history = []
        self.history_limit = history_limit
        self.memory_file = "memory.txt"

    def add_to_history(self, speaker, text):
        self.chat_history.append({"speaker": speaker, "text": text})
        # Trim history: 1 turn = 2 messages (User + AI)
        if len(self.chat_history) > self.history_limit * 2:
            self.chat_history = self.chat_history[-(self.history_limit * 2):]

    def get_history(self):
        return self.chat_history

    def load_long_term_memory(self):
        if os.path.exists(self.memory_file):
            with open(self.memory_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        return ""

    def compress_and_archive(self, config):
        if len(self.chat_history) < 2: return
        
        print("\n[🧠 ALICE is archiving memories...]")
        convo = "\n".join([f"{m['speaker']}: {m['text']}" for m in self.chat_history])
        sys_prompt = "Summarize the key facts and user preferences from this conversation in 1-2 short sentences for long-term memory."
        
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
                payload = {"prompt": f"{sys_prompt}\n\nConvo:\n{convo}\n\nSummary:", "n_predict": 64}
                summary = requests.post(url, json=payload).json()['content'].strip()

            if summary:
                with open(self.memory_file, "a", encoding="utf-8") as file:
                    file.write(f"- {summary}\n")
                print("[✅ Archive complete.]")
        except Exception as e:
            print(f"[Archive Error: {e}]")