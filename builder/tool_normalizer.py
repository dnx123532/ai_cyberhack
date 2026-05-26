"""
NEXUS — Tool Normalizer
Step 3: Baca analysis_report.json → kategorikan → deduplicate → buat raw_tools.json
        + salin/symlink script terbaik per tool ke tools/{category}/

Output: tool_registry/raw_tools.json   (input untuk registry_builder.py)
        tool_registry/duplicates.json  (tools yang di-deduplicate)
        tools/{category}/              (normalized tool wrappers)
"""

import sys, shutil
from pathlib import Path
from collections import defaultdict

from shared.utils import setup_encoding, get_logger, root, load_json, save_json

setup_encoding()
logger = get_logger("nexus.normalizer")

ANALYSIS_JSON = root("analyzer", "output", "analysis_report.json")
REGISTRY_DIR  = root("tool_registry")
TOOLS_DIR     = root("tools")
DATARAW_DIR   = root("data", "raw_datasets", "tool_scripts")

# 1:1 mapping — kategori asli → subfolder tools/
# (sama persis dengan folder di data/raw_datasets/tool_scripts/)
CAT_TO_FOLDER = {
    "recon"       : "recon",
    "scan"        : "scan",
    "web"         : "web",
    "exploit"     : "exploit",
    "post_exploit": "post_exploit",
    "brute_force" : "brute_force",
    "wireless"    : "wireless",
    "cloud"       : "cloud",
    "crypto"      : "crypto",
    "defense"     : "defense",
    "evasion"     : "evasion",
    "forensics"   : "forensics",
    "malware"     : "malware",
    "social"      : "social",
    "iot"         : "iot",
    # fallback untuk file yang tidak terdeteksi
    "utilities"   : "utilities",
}

# Folders under tools/ — 15 kategori + utilities
TOOL_FOLDERS = [
    "recon","scan","web","exploit","post_exploit","brute_force",
    "wireless","cloud","crypto","defense","evasion","forensics",
    "malware","social","iot","utilities",
]


def normalize():
    logger.info("Tool Normalizer starting")

    # Ensure tools/ subfolders exist
    for folder in TOOL_FOLDERS:
        (TOOLS_DIR / folder).mkdir(parents=True, exist_ok=True)

    analysis = load_json(ANALYSIS_JSON, default=[])
    if not analysis:
        logger.error("analysis_report.json not found.")
        logger.info("Run: python analyzer/code_analyzer.py first")
        logger.info(f"Data expected at: data/raw_datasets/tool_scripts/")
        return

    logger.info(f"Loaded {len(analysis)} analyzed files")

    # Group files by tool name (stem) to detect duplicates
    by_name: dict[str, list] = defaultdict(list)
    for entry in analysis:
        if not entry.get("parse_error"):
            by_name[entry["name"]].append(entry)

    normalized  = []
    duplicates  = []
    copy_errors = []

    for tool_name, entries in by_name.items():
        # Pick best representative: prefer larger file (more complete), no parse errors
        best = max(entries, key=lambda e: e.get("size_kb", 0))
        dups = [e for e in entries if e is not best]

        category = best.get("category", "utilities")
        folder   = CAT_TO_FOLDER.get(category, "utilities")

        # Build normalized metadata entry
        normalized.append({
            "name"          : tool_name,
            "category"      : category,
            "folder"        : folder,
            "purpose"       : _infer_purpose(best),
            "source_file"   : best["file"],
            "size_kb"       : best["size_kb"],
            "functions"     : best.get("functions", [])[:10],
            "imports"       : best.get("imports", []),
            "execution"     : _infer_execution(best),
            "supports_async": best.get("is_async", False),
            "has_retry"     : best.get("has_retry", False),
            "has_logging"   : best.get("has_logging", False),
        })

        if dups:
            duplicates.append({
                "tool"      : tool_name,
                "kept"      : best["file"],
                "duplicates": [d["file"] for d in dups],
            })

        # Copy best script to tools/{folder}/{tool_name}.py
        src = DATARAW_DIR / best["file"]
        dst = TOOLS_DIR / folder / f"{tool_name}.py"
        if src.exists() and not dst.exists():
            try:
                shutil.copy2(src, dst)
            except OSError as e:
                copy_errors.append({"tool": tool_name, "error": str(e)})

    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    save_json(REGISTRY_DIR / "raw_tools.json",   normalized)
    save_json(REGISTRY_DIR / "duplicates.json",  duplicates)

    # Print summary
    by_folder = defaultdict(int)
    for t in normalized:
        by_folder[t["folder"]] += 1

    print(f"\n  NORMALIZATION COMPLETE")
    print(f"  {'─'*45}")
    print(f"  Total unique tools : {len(normalized)}")
    print(f"  Duplicates removed : {len(duplicates)}")
    print(f"  Copy errors        : {len(copy_errors)}")
    print(f"\n  BY FOLDER:")
    for folder, count in sorted(by_folder.items(), key=lambda x: -x[1]):
        bar = "█" * min(count // 5, 30)
        print(f"  {folder:14s}: {count:4d}  {bar}")
    print(f"\n  ✅ raw_tools.json ready → run builder/registry_builder.py next\n")


def _infer_purpose(entry: dict) -> str:
    """Infer tool purpose from function names + imports."""
    funcs   = " ".join(entry.get("functions", [])).lower()
    imports = " ".join(entry.get("imports",   [])).lower()
    text    = funcs + " " + imports

    hints = [
        ("scan",      "network/port scanning"),
        ("enum",      "enumeration"),
        ("recon",     "reconnaissance"),
        ("fuzz",      "fuzzing"),
        ("crack",     "password cracking"),
        ("exploit",   "exploitation"),
        ("report",    "reporting"),
        ("monitor",   "monitoring"),
        ("parse",     "output parsing"),
        ("async",     "async automation"),
        ("brute",     "brute forcing"),
        ("dump",      "data extraction"),
    ]
    for keyword, purpose in hints:
        if keyword in text:
            return purpose
    return "security utility"


def _infer_execution(entry: dict) -> str:
    if entry.get("is_async") and entry.get("subprocess"):
        return "async_subprocess"
    if entry.get("subprocess"):
        return "subprocess"
    if entry.get("api_calls"):
        return "api"
    return "cli"


if __name__ == "__main__":
    normalize()
