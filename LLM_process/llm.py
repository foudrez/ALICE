import requests
import random
import os

def generate_response(user_input, config, chat_history=[]):
    backend = config['llm']['backend'].lower()
    model = config['llm']['model']
    base_prompt = config['llm']['character_prompt']
    
    # --- LOAD LONG-TERM MEMORY ---
    past_memory = ""
    if os.path.exists("memory.txt"):
        with open("memory.txt", "r", encoding="utf-8") as f:
            past_memory = f.read().strip()
        
    word_limit = random.randint(10, 40)
    
    # --- INJECT MEMORIES & RULES ---
    system_prompt = f"{base_prompt}\n\nCRITICAL RULE: Answer in under {word_limit} words."
    
    if past_memory:
        system_prompt += f"\n\n=== CRITICAL CONTEXT: LONG-TERM MEMORY ===\n{past_memory}\n=============================="

    # --- OLLAMA BACKEND ---
    if backend == "ollama":
        url = "http://localhost:11434/api/chat"
        messages = [{"role": "system", "content": system_prompt}]
        for msg in chat_history:
            role = "user" if msg["speaker"] == "User" else "assistant"
            messages.append({"role": role, "content": msg["text"]})
        messages.append({"role": "user", "content": user_input})
        
        try:
            response = requests.post(url, json={"model": model, "messages": messages, "stream": False})
            return response.json()['message']['content'].strip()
        except Exception as e:
            return f"Ollama Error: {e}"

    # --- LLAMA.CPP BACKEND ---
    elif backend == "llama.cpp":
        url = "http://localhost:8080/completion"
        prompt_template = f"{system_prompt}\n\n"
        for msg in chat_history:
            prompt_template += f"{msg['speaker']}: {msg['text']}\n"
        prompt_template += f"User: {user_input}\nALICE:"
        
        try:
            response = requests.post(url, json={"prompt": prompt_template, "n_predict": 128})
            return response.json()['content'].strip()
        except Exception as e:
            return f"llama.cpp Error: {e}"
            
    return "Error: Unknown LLM backend"