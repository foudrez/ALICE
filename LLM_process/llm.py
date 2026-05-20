import requests
import random
import os
import json
from tools.web_search import perform_web_search

# --- 1. NATIVE LLAMA.CPP ENGINE SETUP ---
try:
    from llama_cpp import Llama
    LLAMA_CPP_AVAILABLE = True
except ImportError:
    LLAMA_CPP_AVAILABLE = False

llamacpp_engine = None

def init_llamacpp(config):
    """Lazy-loads a local GGUF model directly into memory."""
    global llamacpp_engine
    if LLAMA_CPP_AVAILABLE and not llamacpp_engine:
        print("\n[🧠 Initializing Native Llama.cpp Engine...]")
        
        # Load paths from config
        l_cfg = config.get('llm', {}).get('llama_cpp', {})
        model_path = l_cfg.get('model_path', 'models/llm/Phi-3-mini-4k-instruct-Q4_K_M.gguf')
        n_ctx = l_cfg.get('context_size', 2048)
        n_gpu = l_cfg.get('n_gpu_layers', 0) # Defaults to 0 for CPU-only setups
        
        # --- NEW: SAFE LORA CHECK ---
        raw_lora = l_cfg.get('lora_path', None)
        valid_lora_path = None
        
        if raw_lora:
            if os.path.exists(raw_lora):
                print(f"[🔗 LoRA Adapter Found: {raw_lora}]")
                valid_lora_path = raw_lora
            else:
                print(f"[⚠️ Warning] LoRA path in config not found: {raw_lora}. Booting base model only.")
        # ----------------------------

        if os.path.exists(model_path):
            llamacpp_engine = Llama(
                model_path=model_path, 
                lora_path=valid_lora_path,
                n_ctx=n_ctx, 
                n_gpu_layers=n_gpu, 
                verbose=False 
            )
            print("[✅ Native Llama.cpp Ready]")
        else:
            print(f"[❌ Error] Base GGUF model not found at {model_path}")

# --- 2. WEB SEARCH ROUTER ---
def check_search_intent(user_text, config):
    """
    A lightning-fast internal thought to decide if web search is needed.
    Returns the search query string, or None.
    """
    sys_prompt = (
        "You are a search router. If the user asks for current events, weather, "
        "real-time facts, or something you don't know, reply ONLY with a short search query. "
        "If they are just chatting normally, reply ONLY with the exact word: NO_SEARCH."
    )
    
    backend = config['llm']['backend'].lower()
    model = config['llm']['model']
    
    try:
        if backend == "ollama":
            url = "http://localhost:11434/api/generate"
            payload = {
                "model": model, 
                "prompt": user_text, 
                "system": sys_prompt, 
                "stream": False,
                "options": {"num_predict": 15} # Limit to 15 tokens for ultra-fast response
            }
            res = requests.post(url, json=payload).json().get('response', '').strip()
            
        elif backend in ["llama.cpp", "llamacpp"]:
            global llamacpp_engine
            if not llamacpp_engine: 
                return None
            
            prompt = f"System: {sys_prompt}\nUser: {user_text}\nRouter:"
            output = llamacpp_engine(prompt, max_tokens=15, stop=["\n"], echo=False)
            res = output['choices'][0]['text'].strip()
            
        # Clean up the response
        res = res.replace('"', '').replace("'", "")
        if "NO_SEARCH" in res or not res:
            return None
        return res
        
    except Exception as e:
        print(f"[Router Error] {e}")
        return None

# --- 3. MAIN GENERATION LOOP ---
def generate_response(user_input, config, chat_history=[], stream_output=False):
    backend = config['llm']['backend'].lower()
    model = config['llm']['model']
    base_prompt = config['llm'].get('character_prompt', "You are ALICE, a helpful AI.")
    
    if backend in ["llama.cpp", "llamacpp"]:
        global llamacpp_engine
        if llamacpp_engine is None:
            print("[System] Brain is asleep. Waking up ALICE automatically...")
            init_llamacpp(config)
            
    # --- CHECK WEB SEARCH INTENT ---
    search_query = check_search_intent(user_input, config)
    web_context = ""
    
    if search_query:
        web_results = perform_web_search(search_query)
        web_context = f"\n\n=== LIVE INTERNET SEARCH RESULTS ===\n[SYSTEM NOTE: You just searched the web for '{search_query}'. Here is the real-time data to help you answer the user:]\n{web_results}\n===================================="
            
    # --- LOAD LONG TERM MEMORY ---
    past_memory = ""
    if os.path.exists("memory.txt"):
        with open("memory.txt", "r", encoding="utf-8") as f:
            past_memory = f.read().strip()
            
    word_limit = random.randint(20, 300)
    system_prompt = f"{base_prompt}\n\nCRITICAL RULE: Answer in under {word_limit} words."
    
    if past_memory:
        system_prompt += f"\n\n=== CRITICAL CONTEXT: LONG-TERM MEMORY ===\n{past_memory}\n=============================="
        
    if web_context:
        system_prompt += web_context

    # --- THE TOKEN GENERATOR ---
    def stream_tokens():
        if backend == "ollama":
            url = "http://localhost:11434/api/chat"
            messages = [{"role": "system", "content": system_prompt}]
            for msg in chat_history:
                role = "user" if msg["speaker"] == "User" else "assistant"
                messages.append({"role": role, "content": msg["text"]})
            messages.append({"role": "user", "content": user_input})
            
            try:
                # Force stream=True for Ollama
                response = requests.post(url, json={"model": model, "messages": messages, "stream": True}, stream=True)
                for line in response.iter_lines():
                    if line:
                        data = json.loads(line)
                        yield data.get('message', {}).get('content', '')
            except Exception as e:
                yield f" Ollama Error: {e}"

        elif backend in ["llama.cpp", "llamacpp"]:
            if llamacpp_engine:
                prompt_template = f"{system_prompt}\n\n"
                for msg in chat_history:
                    prompt_template += f"{msg['speaker']}: {msg['text']}\n"
                prompt_template += f"User: {user_input}\nALICE:"
                
                try:
                    # Force stream=True for native engine
                    output = llamacpp_engine(
                        prompt_template,
                        max_tokens=config['llm'].get('max_tokens', 150),
                        stop=["User:", "\n\n", "User: "],
                        echo=False,
                        stream=True # <--- Streaming activated
                    )
                    for chunk in output:
                        yield chunk['choices'][0]['text']
                except Exception as e:
                    yield f" Llama.cpp Error: {e}"

    # --- THE SENTENCE CATCHER ---
    def sentence_chunker(token_stream):
        buffer = ""
        enders = {'.', '!', '?', '\n'}
        for token in token_stream:
            buffer += token
            # If the token contains punctuation, cut the sentence and yield it
            if any(e in token for e in enders):
                last_ender_idx = max(buffer.rfind(e) for e in enders)
                if last_ender_idx != -1:
                    sentence = buffer[:last_ender_idx+1].strip()
                    if sentence:
                        yield sentence
                    buffer = buffer[last_ender_idx+1:]
        if buffer.strip():
            yield buffer.strip()

    # --- ROUTER RETURN ---
    if stream_output:
        return sentence_chunker(stream_tokens())
    else:
        # If streaming is off, just join everything into one string
        return "".join(list(stream_tokens()))