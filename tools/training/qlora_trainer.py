import os

def run_training(base_model_id="google/gemma-4-e2b-it"):
    print("\n=== 🚀 Initiating CPU-Only LoRA Training ===")
    print("⚠️ WARNING: You are training on a CPU without 4-bit quantization.")
    print("⚠️ WARNING: This will use a massive amount of System RAM and take a very long time.")
    
    dataset_path = "tools/training/alice_dataset.jsonl"
    output_dir = "models/llm/alice_adapter"
    
    if not os.path.exists(dataset_path):
        print(f"[❌ Error] No dataset found at {dataset_path}. Run the Harvester first!")
        return

    try:
        import torch
        from datasets import load_dataset
        from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
        from peft import LoraConfig, get_peft_model
        from trl import SFTTrainer
    except ImportError:
        print("[❌ Error] Missing training libraries. Run: uv pip install torch transformers peft trl datasets")
        return

    print("[+] Loading Dataset...")
    dataset = load_dataset("json", data_files=dataset_path, split="train")

    print(f"[+] Loading Base Model ({base_model_id}) into CPU RAM...")
    
    # 1. NO BitsAndBytes! Force CPU loading in standard float32 precision
    model = AutoModelForCausalLM.from_pretrained(
        base_model_id, 
        device_map="cpu", 
        torch_dtype=torch.float32 
    )
    
    tokenizer = AutoTokenizer.from_pretrained(base_model_id)
    tokenizer.pad_token = tokenizer.eos_token

    print("[+] Configuring LoRA Adapters...")
    
    peft_config = LoraConfig(
        r=8, 
        lora_alpha=16, 
        lora_dropout=0.05, 
        bias="none",
        task_type="CAUSAL_LM", 
        # --- THE FIX: Use Phi-3's specific layer names ---
        target_modules=["qkv_proj", "o_proj"] 
    )
    model = get_peft_model(model, peft_config)

    # 3. CPU-Optimized Training Arguments
    # --- ULTRA-LOW RAM TRAINING SETTINGS ---
    training_args = TrainingArguments(
        output_dir=output_dir,
        
        # 1. Shrink batch size to the absolute minimum
        per_device_train_batch_size=1, 
        
        # 2. Accumulate steps to simulate a batch size of 8
        gradient_accumulation_steps=8, 
        
        # 3. Enable Gradient Checkpointing (Trades time for RAM)
        gradient_checkpointing=True,
        
        learning_rate=2e-4,
        logging_steps=5,
        max_steps=50, 
        optim="adamw_torch",
        use_cpu=True,
    )

    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset,
        peft_config=peft_config,
        dataset_text_field="text", 
        
        # 4. Strictly limit how many words it reads at once
        max_seq_length=256, 
        
        tokenizer=tokenizer,
        args=training_args,
    )

    print("[+] Beginning CPU Training Loop. Go make some coffee... ☕")
    trainer.train()

    print(f"[+] Saving new LoRA Adapter to {output_dir}...")
    trainer.model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    print("✅ Training Complete!")