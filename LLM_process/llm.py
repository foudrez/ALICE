import requests
import random
import os
import json
import threading
from tools.web_search import perform_web_search
from tools.home_assistant import get_smart_home_context
from tools.mcp_client import get_all_mcp_tools
# --- 1. NATIVE LLAMA.CPP ENGINE SETUP ---
try:
    from llama_cpp import Llama
    LLAMA_CPP_AVAILABLE = True
except ImportError:
    LLAMA_CPP_AVAILABLE = False

llamacpp_engine = None
llamacpp_lock = threading.Lock()

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
            with llamacpp_lock:
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

def check_mcp_intent(user_text, config):
    """
    Lightning-fast internal router to detect if an MCP tool (like scheduling) is needed.
    Returns a tuple (filler_response, command_tag) or (None, None).
    """
    mcp_tools_dict = get_all_mcp_tools()
    if not mcp_tools_dict:
        return None, None

    tools_descriptions = []
    for server, tools in mcp_tools_dict.items():
        for t in tools:
            args_str = ", ".join([f"{k}={v.get('type','string')}" for k,v in t.get('inputSchema', {}).get('properties', {}).items()])
            desc = (t.get('description') or 'No description').strip()
            tools_descriptions.append(f"- {server}:{t['name']} - {desc} (Args: {args_str})")
            
    tools_list_text = "\n".join(tools_descriptions)

    sys_prompt = (
        "You are an MCP tool router. You have these tools available:\n"
        f"{tools_list_text}\n\n"
        "If the user asks to use one of these tools, reply with EXACTLY this format: FILLER_PHRASE | TOOL_NAME | ARGS\n"
        "Example 1: Let me set that alarm for you. | schedule:set_alarm | time_str=8:00 AM, message=Wake up\n"
        "Example 2: I will check the time. | schedule:get_current_time | \n"
        "If they are just chatting normally or no tools match, reply ONLY with the exact word: NO_MCP."
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
                "options": {"num_predict": 30}
            }
            res = requests.post(url, json=payload).json().get('response', '').strip()
            
        elif backend in ["llama.cpp", "llamacpp"]:
            global llamacpp_engine
            if not llamacpp_engine: 
                return None, None
            
            prompt = f"System: {sys_prompt}\nUser: {user_text}\nRouter:"
            with llamacpp_lock:
                output = llamacpp_engine(prompt, max_tokens=30, stop=["\n"], echo=False)
            res = output['choices'][0]['text'].strip()
            
        res = res.replace('"', '').replace("'", "")
        if "NO_MCP" in res or not res or "|" not in res:
            return None, None
            
        parts = [p.strip() for p in res.split("|")]
        if len(parts) >= 2:
            filler = parts[0]
            # e.g., "schedule:set_alarm"
            tool_path = parts[1].split(":") 
            
            if len(tool_path) != 2:
                return None, None
                
            server_name, tool_name = tool_path[0], tool_path[1]
            args_str = parts[2] if len(parts) > 2 else ""
            
            # Reconstruct the command tag for webui.py
            command_tag = f"[CMD: MCP {server_name} {tool_name} {args_str}]"
            return filler, command_tag
            
        return None, None
    except Exception as e:
        print(f"[MCP Router Error] {e}")
        return None, None

# --- 3. MAIN GENERATION LOOP ---
def generate_response(user_input, config, chat_history=[], stream_output=False, past_memory_text="", image_data=None):
    # Override backend and model if vision is requested
    if image_data:
        backend = "ollama"
        model = "llava"
    else:
        backend = config['llm']['backend'].lower()
        model = config['llm']['model']
        
    base_prompt = config['llm'].get('character_prompt', "You are ALICE, a helpful AI.")
    
    if backend in ["llama.cpp", "llamacpp"]:
        global llamacpp_engine
        if llamacpp_engine is None:
            print("[System] Brain is asleep. Waking up ALICE automatically...")
            init_llamacpp(config)
            
    # --- CHECK MCP INTENT (Non-Blocking) ---
    mcp_filler, mcp_cmd = check_mcp_intent(user_input, config)
    if mcp_filler and mcp_cmd:
        # Instantly yield the filler phrase + the hidden command tag.
        # webui.py will parse the tag and execute the tool in the background.
        def fast_mcp_yield():
            yield mcp_filler + " " + mcp_cmd
            
        if stream_output:
            return fast_mcp_yield()
        else:
            return mcp_filler + " " + mcp_cmd
    
    # --- CHECK WEB SEARCH INTENT ---
    search_query = check_search_intent(user_input, config)
    web_context = ""
    
    if search_query:
        web_results = perform_web_search(search_query)
        web_context = f"\n\n=== LIVE INTERNET SEARCH RESULTS ===\n[SYSTEM NOTE: You just searched the web for '{search_query}'. Here is the real-time data to help you answer the user:]\n{web_results}\n===================================="   
    # --- LOAD LONG TERM MEMORY ---
    # 1. Fetch live internet and smart home data
    ha_context = get_smart_home_context(config)
    
    # 2. Build the System Prompt
    prompt_template = f"System: {base_prompt}\n\n"
    
    # 3. Inject the Live Home Assistant Data
    if ha_context:
        prompt_template += f"{ha_context}\n\n"
    styles = ["snarky and sarcastic", "sweet, helpful, and bubbly", "mysterious and cryptic", "casual, lazy, and sleepy", "hyperactive and extremely enthusiastic", "overly dramatic and theatrical", "calm, logical, and slightly robotic", "curious and deeply inquisitive"]
    chosen_style = random.choice(styles)
    word_limit = random.randint(20, 300)
    system_prompt = (
        f"{base_prompt}\n\n"
        f"CRITICAL RULE: Answer in under {word_limit} words. Your current mood/style is: {chosen_style}. "
        "Make sure your answer strongly reflects this personality.\n"
        "EMOTION TAGGING RULE: You can inject emotion tags at the start of your response or when your emotion changes. "
        "Instead of just using simple tags, you MUST use percent-based emotion tags or a mix of emotions! "
        "Use the format [emotion:percent] (e.g., [happy:60], [sad:40], [angry:70], [surprised:80], [relaxed:50]). "
        "You can mix emotions inside a single tag separated by commas, like [happy:50, surprised:20]. "
        "Available emotions are: happy, sad, angry, surprised, relaxed. "
        "Ensure the percentage is an integer between 10 and 100. "
    )
    
    # Inject Custom Actions into Prompt
    core_states = {'angry', 'happy', 'idle', 'listening', 'neutral', 'queued', 'relaxed', 'sad', 'speaking', 'surprised', 'thinking'}
    fbx_mapping = config.get('animation', {}).get('fbx_mapping', {})
    custom_actions = [k for k in fbx_mapping.keys() if k not in core_states and fbx_mapping[k] and fbx_mapping[k] != 'None']
    
    if custom_actions:
        actions_list = ", ".join(custom_actions)
        system_prompt += (
            f"ACTION TAGGING RULE: You can perform physical actions by outputting [ANIM: action_name]. "
            f"Available actions are: {actions_list}. "
        )
        
    system_prompt += "You must end your response with <end>."
    
    if past_memory_text:
        # Check if it's already structured context from the 4-layer system, or legacy raw text
        if "=== ALICE'S INTERNAL STATE ===" in past_memory_text:
            system_prompt += f"\n\n{past_memory_text}"
        else:
            system_prompt += f"\n\n=== CRITICAL CONTEXT: LONG-TERM MEMORY ===\n{past_memory_text}\n=============================="
        
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
            
            # If we have an image, inject it into the final user message
            final_user_msg = {"role": "user", "content": user_input}
            if image_data:
                final_user_msg["images"] = [image_data]
            messages.append(final_user_msg)
            
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
                    with llamacpp_lock:
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
        import re
        buffer = ""
        enders = {'.', '!', '?', '\n'}
        in_think_block = False
        
        for token in token_stream:
            buffer += token
            
            if "<think>" in buffer.lower() and not in_think_block:
                in_think_block = True
                
            if in_think_block:
                if "</think>" in buffer.lower():
                    in_think_block = False
                    buffer = re.sub(r'<think>.*?</think>', '', buffer, flags=re.DOTALL | re.IGNORECASE)
                else:
                    continue # Wait for the think block to finish before yielding any sentences
                    
            if "<end>" in buffer:
                pre_end = buffer.split("<end>")[0].strip()
                if pre_end:
                    yield pre_end
                return
            # If the token contains punctuation, cut the sentence and yield it
            if any(e in token for e in enders):
                last_ender_idx = max(buffer.rfind(e) for e in enders)
                if last_ender_idx != -1:
                    sentence = buffer[:last_ender_idx+1].strip()
                    if sentence:
                        yield sentence
                    buffer = buffer[last_ender_idx+1:]
        if buffer.strip():
            clean_buf = buffer.split("<end>")[0].strip()
            # If it ended while still thinking, strip the unclosed block
            if in_think_block:
                clean_buf = re.sub(r'<think>.*', '', clean_buf, flags=re.DOTALL | re.IGNORECASE).strip()
            if clean_buf:
                yield clean_buf

    # --- ROUTER RETURN ---
    if stream_output:
        return sentence_chunker(stream_tokens())
    else:
        # If streaming is off, just join everything into one string
        full_response = "".join(list(stream_tokens()))
        if "<end>" in full_response:
            full_response = full_response.split("<end>")[0].strip()
        return full_response


def run_extraction_prompt(prompt, config):
    """
    Synchronous utility function to safely execute memory extractions
    or background tasks against the active LLM backend.
    """
    backend = config.get("llm", {}).get("backend", "llama.cpp").lower()
    model = config.get("llm", {}).get("model", "default")
    
    if backend == "ollama":
        url = "http://localhost:11434/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": 512}
        }
        try:
            return requests.post(url, json=payload, timeout=30).json().get("response", "")
        except Exception:
            return ""
            
    elif backend in ("llama.cpp", "llamacpp"):
        global llamacpp_engine
        if not llamacpp_engine:
            return ""
            
        try:
            # We must acquire the lock before doing background extraction
            with llamacpp_lock:
                output = llamacpp_engine(
                    prompt,
                    max_tokens=512,
                    stop=["\n\n\n"],
                    echo=False
                )
            return output['choices'][0]['text'].strip()
        except Exception as e:
            print(f"[Extraction Error] {e}")
            return ""
    
    return ""