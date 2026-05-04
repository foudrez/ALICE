import json
import os

DATASET_FILE = "models/lora/alice_dataset.jsonl"

def create_training_example(user_text, alice_response):
    """Formats the interaction into standard ShareGPT format."""
    return {
        "conversations": [
            {"from": "system", "value": "You are ALICE, a highly responsive AI VTuber."},
            {"from": "human", "value": user_text},
            {"from": "gpt", "value": alice_response}
        ]
    }

def run_harvester():
    print("\n=== 🧠 ALICE Dataset Harvester ===")
    print("Type a user prompt, then type ALICE's perfect reply.")
    print("Type 'EXIT' to return to menu.\n")
    
    os.makedirs(os.path.dirname(DATASET_FILE), exist_ok=True)
    dataset = []
    
    if os.path.exists(DATASET_FILE):
        with open(DATASET_FILE, 'r', encoding='utf-8') as f:
            dataset = [json.loads(line) for line in f]
        print(f"[Loaded {len(dataset)} existing examples]")

    while True:
        user_input = input("\n[Human]: ").strip()
        if user_input.upper() == "EXIT": break
            
        alice_response = input("[ALICE]: ").strip()
        if alice_response.upper() == "EXIT": break
            
        dataset.append(create_training_example(user_input, alice_response))
        print("✅ Added to dataset.")

    with open(DATASET_FILE, 'w', encoding='utf-8') as f:
        for entry in dataset:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
            
    print(f"\n[Saved] Dataset now contains {len(dataset)} examples at {DATASET_FILE}")