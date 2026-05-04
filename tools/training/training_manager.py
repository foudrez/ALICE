import sys
import os

# Add parent directory to path so we can import from ALICE tools
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from tools.training.dataset_builder import run_harvester
from tools.training.qlora_trainer import run_training

def main_menu():
    while True:
        print("\n" + "="*40)
        print("🛠️  ALICE Fine-Tuning & Training Suite")
        print("="*40)
        print("1. 🧠 Harvest Data (Build Dataset)")
        print("2. 🚀 Train LoRA (Run QLoRA)")
        print("3. ❌ Exit")
        print("="*40)
        
        choice = input("Select an option (1-3): ").strip()
        
        if choice == '1':
            run_harvester()
        elif choice == '2':
            # You can change this to match whatever base model you are using
            run_training(base_model_id="microsoft/Phi-3-mini-4k-instruct") 
        elif choice == '3':
            print("Exiting Training Suite.")
            break
        else:
            print("Invalid selection. Try again.")

if __name__ == "__main__":
    main_menu()