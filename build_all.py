"""
NEXUS — Master Build Script
Jalankan seluruh pipeline dataset + registry secara berurutan.

Urutan:
  Step 1: analyzer/code_analyzer.py       → analysis_report.json
  Step 2: builder/tool_normalizer.py      → raw_tools.json
  Step 3: builder/registry_builder.py     → registry.json + tool_metadata.jsonl
  Step 4: builder/dataset_builder.py      → reasoning/planning/workflow/etc .jsonl
  Step 5: builder/pattern_extractor.py    → code/workflow/execution_patterns.jsonl

Usage:
  python build_all.py           # run all steps
  python build_all.py --from 3  # resume from step 3
  python build_all.py --step 4  # run only step 4
"""

import sys, time, argparse
from pathlib import Path

# Ensure project root is in sys.path
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from shared.utils import setup_encoding, get_logger

setup_encoding()
logger = get_logger("nexus.build_all")


def run_step(name: str, func, step_num: int, total: int):
    print(f"\n  {'═'*56}")
    print(f"  STEP {step_num}/{total}: {name}")
    print(f"  {'═'*56}")
    t = time.time()
    try:
        func()
        dur = round(time.time() - t, 1)
        print(f"\n  ✅ Step {step_num} done  ({dur}s)")
        return True
    except Exception as e:
        dur = round(time.time() - t, 1)
        print(f"\n  ❌ Step {step_num} FAILED: {e}  ({dur}s)")
        logger.exception(f"Step {step_num} ({name}) failed")
        return False


def main():
    parser = argparse.ArgumentParser(description="NEXUS Master Build")
    group  = parser.add_mutually_exclusive_group()
    group.add_argument("--from", dest="from_step", type=int, default=1,
                       metavar="N", help="Resume from step N")
    group.add_argument("--step", dest="only_step",  type=int, default=None,
                       metavar="N", help="Run only step N")
    args = parser.parse_args()

    # Import lazily so missing deps don't block --help
    from analyzer.code_analyzer    import run_analysis
    from builder.tool_normalizer   import normalize
    from builder.registry_builder  import build_registry
    from builder.dataset_builder   import build_all as build_datasets
    from builder.pattern_extractor import build_datasets as build_patterns

    STEPS = [
        (1, "Code Analyzer      → analysis_report.json",             run_analysis),
        (2, "Tool Normalizer    → raw_tools.json",                    normalize),
        (3, "Registry Builder   → registry.json + tool_metadata",     build_registry),
        (4, "Dataset Builder    → 6× training JSONL",                 build_datasets),
        (5, "Pattern Extractor  → code/workflow/execution patterns",  build_patterns),
    ]
    total = len(STEPS)

    print(f"""
  ╔{'═'*54}╗
  ║   NEXUS — MASTER BUILD PIPELINE                      ║
  ║   Data: data/raw_datasets/tool_scripts/              ║
  ║   15 categories  ·  12,235 Python files              ║
  ╚{'═'*54}╝""")

    start    = time.time()
    failed   = []
    to_run   = (
        [(n, d, f) for n, d, f in STEPS if n == args.only_step]
        if args.only_step else
        [(n, d, f) for n, d, f in STEPS if n >= args.from_step]
    )

    if not to_run:
        print(f"  No steps to run (from={args.from_step}, only={args.only_step})")
        return

    for step_num, desc, func in to_run:
        ok = run_step(desc, func, step_num, total)
        if not ok:
            failed.append(step_num)

    total_dur = round(time.time() - start, 1)
    print(f"\n  {'═'*56}")
    print(f"  BUILD COMPLETE  ({total_dur}s)")
    if failed:
        print(f"  ❌ Failed steps: {failed}")
        print(f"  Resume with: python build_all.py --from {min(failed)}")
    else:
        print(f"  ✅ All {len(to_run)} steps succeeded")
    print(f"  {'═'*56}\n")


if __name__ == "__main__":
    main()
