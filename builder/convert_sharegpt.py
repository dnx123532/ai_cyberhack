"""
NEXUS — Convert & Merge all datasets → ShareGPT format
Input : datasets/{reasoning,planning,workflow,reflection,memory,style}/*.jsonl
        datasets/tool_metadata/tool_metadata.jsonl   (already ShareGPT)
Output: data/jsonl/nexus_v2_sharegpt_train.jsonl  (90%)
        data/jsonl/nexus_v2_sharegpt_val.jsonl     (10%)

ShareGPT format yang dipakai train.py:
{
  "conversations": [
    {"from": "system", "value": "..."},
    {"from": "human",  "value": "..."},
    {"from": "gpt",    "value": "..."}
  ]
}
"""

import json, random, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT    = Path(__file__).parent.parent
DS      = ROOT / "datasets"
OUT_DIR = ROOT / "data" / "jsonl"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SYSTEM_PROMPT = (
    "Kamu adalah NEXUS — AI Security Operations Agent yang otonom. "
    "Kamu memiliki kemampuan reasoning mendalam, multi-step planning, "
    "workflow orchestration, self-reflection, dan memory jangka panjang. "
    "Kamu beroperasi dalam konteks authorized security assessment, "
    "defensive security, SOC automation, dan vulnerability research. "
    "Selalu berpikir step-by-step sebelum bertindak."
)


def nexus_to_sharegpt(entry: dict, dataset_type: str) -> dict:
    """
    Konversi satu entry NEXUS format → ShareGPT format.
    Response mencakup reasoning + planning + workflow + jawaban akhir
    supaya model belajar chain-of-thought lengkap.
    """
    instruction = entry.get("instruction", "")
    response    = entry.get("response", "")
    reasoning   = entry.get("reasoning", [])
    planning    = entry.get("planning", [])
    workflow    = entry.get("workflow", [])
    tools       = entry.get("tools", [])
    reflection  = entry.get("reflection", "")
    memory      = entry.get("memory", "")

    # Build full CoT response
    parts = []

    if reasoning:
        steps = "\n".join(f"  {i+1}. {r}" for i, r in enumerate(reasoning))
        parts.append(f"**[Reasoning]**\n{steps}")

    if planning:
        steps = "\n".join(f"  {i+1}. {p}" for i, p in enumerate(planning))
        parts.append(f"**[Planning]**\n{steps}")

    if workflow:
        cmds = "\n".join(f"  $ {w}" for w in workflow)
        parts.append(f"**[Workflow]**\n{cmds}")

    if tools:
        tool_list = "\n".join(
            f"  • {t['tool']}: {t['purpose']}"
            if isinstance(t, dict) else f"  • {t}"
            for t in tools
        )
        parts.append(f"**[Tools]**\n{tool_list}")

    if response:
        parts.append(f"**[Action]**\n{response}")

    if reflection:
        parts.append(f"**[Reflection]**\n{reflection}")

    if memory:
        parts.append(f"**[Memory]**\n{memory}")

    full_response = "\n\n".join(parts) if parts else response

    return {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {"from": "human",  "value": instruction},
            {"from": "gpt",    "value": full_response},
        ]
    }


def load_nexus_jsonl(path: Path, dataset_type: str) -> list:
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            # tool_metadata sudah dalam format ShareGPT — skip convert
            if "conversations" in entry:
                entries.append(entry)
            else:
                entries.append(nexus_to_sharegpt(entry, dataset_type))
        except json.JSONDecodeError as e:
            print(f"  ⚠️  JSON error in {path.name}: {e}")
    return entries


def main():
    print(f"\n  {'═'*54}")
    print(f"  NEXUS — Convert & Merge → ShareGPT")
    print(f"  {'═'*54}\n")

    # Semua dataset files yang mau digabung
    dataset_files = [
        (DS / "reasoning"    / "reasoning.jsonl",         "reasoning"),
        (DS / "planning"     / "planning.jsonl",           "planning"),
        (DS / "workflow"     / "workflow.jsonl",           "workflow"),
        (DS / "reflection"   / "reflection.jsonl",         "reflection"),
        (DS / "memory"       / "memory.jsonl",             "memory"),
        (DS / "style"        / "style.jsonl",              "style"),
        (DS / "extra"        / "extra.jsonl",              "extra"),       # ds_part5 + ds_part6
        (DS / "tool_metadata"/ "tool_metadata.jsonl",      "tools"),
        (DS / "final_merged" / "final_merged.jsonl",       "final_merged"),
    ]

    all_entries = []
    for path, dtype in dataset_files:
        if not path.exists():
            print(f"  ⚠️  Skip (not found): {path.name}")
            continue
        entries = load_nexus_jsonl(path, dtype)
        all_entries.extend(entries)
        print(f"  [{dtype:14s}] {len(entries):3d} entries ← {path.name}")

    print(f"\n  Total sebelum split: {len(all_entries)} entries")

    # Shuffle dengan fixed seed untuk reproducibility
    random.seed(42)
    random.shuffle(all_entries)

    # Split 90% train / 10% val
    split_idx = int(len(all_entries) * 0.9)
    train_set = all_entries[:split_idx]
    val_set   = all_entries[split_idx:]

    # Save
    def save_jsonl(path: Path, data: list):
        with open(path, "w", encoding="utf-8") as f:
            for entry in data:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    train_path = OUT_DIR / "nexus_v2_sharegpt_train.jsonl"
    val_path   = OUT_DIR / "nexus_v2_sharegpt_val.jsonl"

    save_jsonl(train_path, train_set)
    save_jsonl(val_path,   val_set)

    print(f"\n  {'─'*54}")
    print(f"  Train : {len(train_set):4d} entries → {train_path.name}")
    print(f"  Val   : {len(val_set):4d} entries → {val_path.name}")
    print(f"  {'─'*54}")
    print(f"\n  ✅ Siap untuk training! Jalankan di Colab:")
    print(f"     !python training/train.py\n")


if __name__ == "__main__":
    main()
