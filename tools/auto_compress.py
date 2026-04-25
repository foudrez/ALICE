import requests

def compress_and_save_memory(history, config):
    if len(history) < 2: 
        return # Don't save if we barely talked
        
    print("\n[🧠 ALICE is compressing memories before shutting down...]")
    
    # Turn the history list into a single block of text
    convo = "\n".join([f"{msg['speaker']}: {msg['text']}" for msg in history])
    
    # The secret prompt that forces the LLM to summarize
    sys_prompt = "You are a memory compressor. Summarize the key facts, user preferences, and important events from this conversation in exactly 1 or 2 short sentences. Focus ONLY on what the AI should remember about the user for tomorrow."
    
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
            # Append the new memory as a bullet point to the text file
            with open("memory.txt", "a", encoding="utf-8") as file:
                file.write(f"- {summary}\n")
            print("[✅ Memories successfully archived to memory.txt!]")
            
    except Exception as e:
        print(f"[Memory Save Error: {e}]")