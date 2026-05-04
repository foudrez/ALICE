import csv
import json
import os

def convert_csv_to_jsonl(csv_filepath, jsonl_filepath):
    print(f"=== 🔄 ALICE Dataset Converter ===")
    print(f"Reading from: {csv_filepath}")
    
    if not os.path.exists(csv_filepath):
        print("[❌ Error] CSV file not found!")
        return

    dataset = []
    
    # Read the CSV file
    with open(csv_filepath, mode='r', encoding='utf-8-sig') as csv_file:
        # Assumes your columns are exactly: "System Prompt", "Human Input", "GPT Response"
        reader = csv.DictReader(csv_file)
        
        for row in reader:
            # Skip empty rows
            if not row.get("Human Input") or not row.get("GPT Response"):
                continue
                
            # Create the ShareGPT format
            example = {
                "conversations": [
                    {"from": "system", "value": row.get("System Prompt", "You are ALICE, a highly responsive AI VTuber.").strip()},
                    {"from": "human", "value": row.get("Human Input", "").strip()},
                    {"from": "gpt", "value": row.get("GPT Response", "").strip()}
                ]
            }
            dataset.append(example)

    # Write the JSONL file
    with open(jsonl_filepath, mode='w', encoding='utf-8') as jsonl_file:
        for entry in dataset:
            jsonl_file.write(json.dumps(entry, ensure_ascii=False) + '\n')

    print(f"✅ Successfully converted {len(dataset)} examples!")
    print(f"Saved to: {jsonl_filepath}")

if __name__ == "__main__":
    # Example usage:
    # 1. Create a file named 'alice_raw_data.csv' in your models/lora folder
    # 2. Run this script!
    
    CSV_INPUT = "tools\\training\\data.csv"  # Change this to your actual CSV path
    JSONL_OUTPUT = "tools\\training\\alice_dataset.jsonl"
    
    convert_csv_to_jsonl(CSV_INPUT, JSONL_OUTPUT)