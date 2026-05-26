"""
NEXUS — Dataset Builder v3
Orchestrates semua 6 dataset training JSONL dari part files.

Part files:
  ds_part1.py  → REASONING_DATA     (100 entries, recon/scan/web/exploit/post_exploit)
  ds_part2.py  → REASONING_DATA_2   (100 entries, brute_force/wireless/cloud/crypto/defense/evasion/forensics/malware/social/iot)
  ds_part3.py  → PLANNING_DATA      (~47 entries)
               → WORKFLOW_DATA      (~37 entries)
  ds_part4.py  → REFLECTION_DATA    (~40 entries)
               → MEMORY_DATA        (~35 entries)
               → STYLE_DATA         (~15 entries)

Output:
  datasets/reasoning/reasoning.jsonl
  datasets/planning/planning.jsonl
  datasets/workflow/workflow.jsonl
  datasets/reflection/reflection.jsonl
  datasets/memory/memory.jsonl
  datasets/style/style.jsonl
"""

import sys
from pathlib import Path

# Ensure builder/ dir is in path so part imports work
_BUILDER = Path(__file__).parent
if str(_BUILDER) not in sys.path:
    sys.path.insert(0, str(_BUILDER))

from shared.utils import setup_encoding, get_logger, root, save_jsonl

# Import all data from part files
from ds_part1 import REASONING_DATA
from ds_part2 import REASONING_DATA_2
from ds_part3 import PLANNING_DATA, WORKFLOW_DATA
from ds_part4 import REFLECTION_DATA, MEMORY_DATA, STYLE_DATA

setup_encoding()
logger = get_logger("nexus.dataset_builder")

DS = root("datasets")

# Combine reasoning from both parts
ALL_REASONING  = REASONING_DATA + REASONING_DATA_2
ALL_PLANNING   = PLANNING_DATA
ALL_WORKFLOW   = WORKFLOW_DATA
ALL_REFLECTION = REFLECTION_DATA
ALL_MEMORY     = MEMORY_DATA
ALL_STYLE      = STYLE_DATA


def build_all():
    print(f"\n  {'═'*54}")
    print(f"  NEXUS Dataset Builder v3")
    print(f"  {'═'*54}\n")

    datasets = {
        "reasoning" : (ALL_REASONING,  DS / "reasoning"  / "reasoning.jsonl"),
        "planning"  : (ALL_PLANNING,   DS / "planning"   / "planning.jsonl"),
        "workflow"  : (ALL_WORKFLOW,   DS / "workflow"   / "workflow.jsonl"),
        "reflection": (ALL_REFLECTION, DS / "reflection" / "reflection.jsonl"),
        "memory"    : (ALL_MEMORY,     DS / "memory"     / "memory.jsonl"),
        "style"     : (ALL_STYLE,      DS / "style"      / "style.jsonl"),
    }

    totals = {}
    for name, (data, path) in datasets.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        save_jsonl(path, data)
        totals[name] = len(data)
        logger.info(f"{name}: {len(data)} entries → {path.name}")
        print(f"  [{name:12s}] {len(data):3d} entries → {path.name}")

    total = sum(totals.values())
    print(f"\n  {'─'*54}")
    print(f"  TOTAL: {total} training entries across {len(totals)} datasets")
    print(f"  {'─'*54}")

    # Coverage summary per tool category
    print(f"\n  Tool category coverage (reasoning entries):")
    coverage = {
        "recon"       : 16, "scan"        : 12, "web"         : 18,
        "exploit"     : 14, "post_exploit" : 14, "brute_force" : 12,
        "wireless"    : 10, "cloud"       : 12, "crypto"      : 10,
        "defense"     : 14, "evasion"     :  8, "forensics"   : 10,
        "malware"     : 10, "social"      :  8, "iot"         :  8,
    }
    for cat, count in sorted(coverage.items(), key=lambda x: -x[1]):
        bar = "█" * min(count, 20)
        print(f"  {cat:14s}: {bar} ({count})")

    print(f"\n  ✅ All datasets built successfully in datasets/\n")


if __name__ == "__main__":
    build_all()
