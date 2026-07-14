"""
NEXUS AI Agent — QLoRA Training Script
Target: Google Colab T4 (16GB VRAM)
Model : teknium/OpenHermes-2.5-Mistral-7B (Apache 2.0, no usage-policy restrictions)
Method: QLoRA 4-bit + LoRA adapter via PEFT/TRL
"""

import os, sys, gc, shutil, torch
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# Use the accelerated Rust downloader (chunked, resumable, real timeouts) so a
# stalled connection to the HF CDN errors/retries instead of hanging forever.
os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "1")
os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "30")

# ── Paths ─────────────────────────────────────────────────────────────────────
COLAB_ROOT  = "/content/ai_cyberhack"
DRIVE_ROOT  = "/content/drive/MyDrive/nexus-agent"

DATASET_TRAIN = f"{COLAB_ROOT}/data/jsonl/nexus_v2_sharegpt_train.jsonl"
DATASET_VAL   = f"{COLAB_ROOT}/data/jsonl/nexus_v2_sharegpt_val.jsonl"
OUTPUT_DIR    = f"{COLAB_ROOT}/checkpoints"
LOGGING_DIR   = f"{COLAB_ROOT}/logs/training"
MODEL_DIR     = f"{COLAB_ROOT}/models/lora_adapter"

MODEL_ID = "teknium/OpenHermes-2.5-Mistral-7B"
# Jika VRAM < 14GB, pakai model Mistral yang lebih kecil / quantized lebih agresif

# ── Imports (setelah pip install) ─────────────────────────────────────────────
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, TrainingArguments
from peft import LoraConfig, TaskType, get_peft_model, prepare_model_for_kbit_training
from trl import SFTTrainer
from datasets import load_dataset
from monitor import NEXUSMonitorCallback

# ── QLoRA config ──────────────────────────────────────────────────────────────
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True, bnb_4bit_use_double_quant=True,
    bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.float16,
)

lora_config = LoraConfig(
    task_type=TaskType.CAUSAL_LM, r=64, lora_alpha=128,
    lora_dropout=0.05, bias="none",
    target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"],
)

training_args = TrainingArguments(
    output_dir=OUTPUT_DIR, num_train_epochs=3,
    per_device_train_batch_size=1, per_device_eval_batch_size=1,
    gradient_accumulation_steps=8,
    learning_rate=2e-4, lr_scheduler_type="cosine", warmup_ratio=0.05,
    fp16=True, bf16=False, gradient_checkpointing=True,
    optim="paged_adamw_8bit", weight_decay=0.01, max_grad_norm=1.0,
    eval_strategy="steps", eval_steps=100, save_strategy="steps",
    save_steps=100, save_total_limit=3, load_best_model_at_end=True,
    metric_for_best_model="eval_loss", greater_is_better=False,
    logging_dir=LOGGING_DIR, logging_steps=10, report_to=["tensorboard"],
    seed=42, data_seed=42,
)

# ── Format ShareGPT → ChatML ──────────────────────────────────────────────────
def format_sharegpt(example):
    text = ""
    for turn in example.get("conversations", []):
        role, val = turn.get("from",""), turn.get("value","")
        if role == "system":   text += f"<|im_start|>system\n{val}<|im_end|>\n"
        elif role == "human":  text += f"<|im_start|>user\n{val}<|im_end|>\n"
        elif role == "gpt":    text += f"<|im_start|>assistant\n{val}<|im_end|>\n"
    return {"text": text}

# ── Main ──────────────────────────────────────────────────────────────────────
def train():
    print("\n" + "="*55)
    print("  NEXUS AI Agent — QLoRA Training")
    print("="*55)

    if torch.cuda.is_available():
        gpu  = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / 1e9
        print(f"  GPU  : {gpu}  ({vram:.1f} GB)")
    else:
        print("  ⚠️  No GPU detected!")

    # Load tokenizer + model
    print(f"\n  Loading {MODEL_ID}...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True, padding_side="right")
    if tokenizer.pad_token is None: tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, quantization_config=bnb_config, device_map="auto",
        trust_remote_code=True, torch_dtype=torch.float16, attn_implementation="eager",
    )
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # Load dataset
    train_raw = load_dataset("json", data_files=DATASET_TRAIN, split="train")
    val_raw   = load_dataset("json", data_files=DATASET_VAL,   split="train")
    train_ds  = train_raw.map(format_sharegpt, remove_columns=train_raw.column_names)
    val_ds    = val_raw.map(format_sharegpt,   remove_columns=val_raw.column_names)
    print(f"  Train: {len(train_ds)}  Val: {len(val_ds)}")

    # Trainer
    trainer = SFTTrainer(
        model=model, tokenizer=tokenizer,
        train_dataset=train_ds, eval_dataset=val_ds,
        args=training_args, dataset_text_field="text",
        max_seq_length=1024, packing=False,
        callbacks=[NEXUSMonitorCallback()],
    )

    print("\n  🚀 Training started...\n")
    trainer.train()

    # Save adapter
    Path(MODEL_DIR).mkdir(parents=True, exist_ok=True)
    trainer.save_model(MODEL_DIR)
    tokenizer.save_pretrained(MODEL_DIR)
    print(f"\n  ✅ Adapter saved: {MODEL_DIR}")

    # Backup to Drive
    drive_dst = f"{DRIVE_ROOT}/models/lora_adapter"
    shutil.copytree(MODEL_DIR, drive_dst, dirs_exist_ok=True)
    print(f"  ✅ Backed up to Drive: {drive_dst}")

if __name__ == "__main__":
    train()
