from test import llm
from tts import speak
if __name__ == "__main__":
    user_prompt = input("Enter your question: ").strip()
    if not user_prompt:
        print("Prompt cannot be empty.")
    else:
        reply = llm(user_prompt)
        print("\nOllama says:", reply)
        speak(reply)