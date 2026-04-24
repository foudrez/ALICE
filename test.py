import ollama

def llm(prompt: str, model: str = "gemma4:e2b") -> str:
    """
    Sends a prompt to the specified Ollama model and returns the response.
    
    Args:
        prompt (str): The text prompt to send to the model.
        model (str): The name of the Ollama model to use.
    
    Returns:
        str: The model's response text.
    """
    try:
        # Send the prompt to Ollama
        response = ollama.chat(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ]
        )
        
        # Extract and return the model's reply
        return response["message"]["content"].strip()
    
    except Exception as e:
        return f"Error communicating with Ollama: {e}"

if __name__ == "__main__":
    user_prompt = input("Enter your question: ").strip()
    if not user_prompt:
        print("Prompt cannot be empty.")
    else:
        reply = llm(user_prompt)
        print("\nOllama says:", reply)
