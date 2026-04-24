import requests
import random
# 1 The LLM Generator (The Brain)
def generate_response(user_input, config, chat_history=[]):
    backend = config['llm']['backend'].lower()
    model = config['llm']['model']
    system_prompt = config['llm']['character_prompt']
    
    print(f"Thinking using {backend} ({model})...")
    
    # --- 2. GENERATE RANDOM LIMIT ---
    word_limit = random.randint(10, 50)
    print(f"Thinking using {backend} ({model})... [Word limit: {word_limit}]")
    
    # --- 3. INJECT THE LIMIT INTO HER BRAIN ---
    # We append a strict rule to the end of her personality prompt
    system_prompt = f"{system_prompt}\n\nCRITICAL RULE: You MUST answer in {word_limit} words or less. Keep it brief and snappy!"
    # --- OLLAMA BACKEND ---
    if backend == "ollama":
        url = "http://localhost:11434/api/generate"
        # Build the memory array for Ollama
        messages = [{"role": "system", "content": system_prompt}]
        
        # Load past memory
        for msg in chat_history:
            role = "user" if msg["speaker"] == "User" else "assistant"
            messages.append({"role": role, "content": msg["text"]})
            
        # Add current message
        messages.append({"role": "user", "content": user_input})
        
        payload = {
            "model": model,
            "prompt": user_input,
            "stream": False
        }
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            return response.json()['response']
        except Exception as e:
            return f"Ollama connection error: {e}"


#----------------------------------------------------------------------------------------------------------------------

    # --- LLAMA.CPP BACKEND ---
    elif backend == "llama.cpp":
        # Assuming you are running the llama.cpp server on its default port (8080)
        # Command to start it: ./server -m models/your_model.gguf -c 2048
        url = "http://localhost:8080/completion"
        # Build the memory string for Llama.cpp
        prompt_template = f"{system_prompt}\n\n"
        
        # Load past memory
        for msg in chat_history:
            prompt_template += f"{msg['speaker']}: {msg['text']}\n"
            
        # Add current message
        prompt_template += f"User: {user_input}\nALICE:"
        
        payload = {
            "prompt": prompt_template,
            "n_predict": 128
        }
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            return response.json()['content'].strip()
        except Exception as e:
            return f"llama.cpp connection error: {e}"
            
    else:
        return "Error: Unknown LLM backend in config.yaml"


