"""Level 0 — build a real, verified tool registry.

For every tool listed under tools/<category>/<Tool>.py, figure out how it is
ACTUALLY invoked on this machine right now:
  - "system"  -> installed binary found via `which` in WSL Kali
  - "local"   -> a runnable .py entrypoint found inside data/raw_datasets/tool_scripts
  - "unknown" -> neither found; this is real signal, not something to hide.
                 These become Level 5 candidates (tool doesn't exist -> build it).

Nothing here is guessed by hand — every entry is checked live against the
filesystem / WSL PATH so the registry can't drift from reality like the old
tool_registry/ did.
"""
import json
import re

from common import ROOT, SCRIPTS_DIR, REGISTRY_PATH, list_categories, list_tools, run_wsl, wsl_which, to_wsl_path


def normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def candidate_binaries(tool: str):
    """Reasonable real-world binary names to try, exact case first (matters:
    e.g. `theharvester` is a deprecated alias in Kali, `theHarvester` is real)."""
    ordered = [tool, tool.lower(), tool.replace("-", "").lower(), tool.replace("_", "-").lower()]
    seen = []
    for cand in ordered:
        if cand not in seen:
            seen.append(cand)
    return seen


SKIP_DIRS = {".git", "__pycache__", "tests", "test", "docs", "doc", "wodles", "venv", ".venv"}


def find_repo_dir(category: str, tool: str):
    cat_dir = SCRIPTS_DIR / category
    if not cat_dir.exists():
        return None
    target = normalize(tool)
    for child in cat_dir.iterdir():
        if child.is_dir() and normalize(child.name) == target:
            return child
    return None


def find_local_entrypoint(category: str, tool: str):
    """Search data/raw_datasets/tool_scripts/<category>/ for a matching repo + entrypoint .py.

    1st pass: score .py files up to depth 3 by filename match / cli-main convention.
    2nd pass (fallback): grep the repo's README for a real `python3 X.py` usage line —
    catches non-obvious entrypoint names (e.g. RouterSploit's rsf.py).
    """
    repo_dir = find_repo_dir(category, tool)
    if repo_dir is None:
        return None
    target = normalize(tool)

    candidates = []
    for p in repo_dir.rglob("*.py"):
        rel_parts = p.relative_to(repo_dir).parts
        if any(part in SKIP_DIRS for part in rel_parts):
            continue
        if len(rel_parts) > 3:
            continue
        candidates.append(p)

    def score(p):
        stem = normalize(p.stem)
        s = 0
        min_len = min(len(stem), len(target))
        if stem == target:
            s += 100
        elif min_len >= 4 and (
            stem.startswith(target) or target.startswith(stem)
            or stem.endswith(target) or target.endswith(stem)
        ):
            s += 50
        if p.stem.lower() in ("main", "cli", "__main__"):
            s += 40
        s -= (len(p.relative_to(repo_dir).parts) - 1) * 5  # prefer shallow
        return s

    if candidates:
        candidates.sort(key=score, reverse=True)
        best = candidates[0]
        if score(best) >= 20:
            return best

    # Fallback: grep README for a real "python3 something.py" usage example
    for readme_name in ("README.md", "readme.md", "README.rst", "README"):
        readme = repo_dir / readme_name
        if readme.exists():
            try:
                text = readme.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for m in re.finditer(r"python3?\s+([A-Za-z0-9_\-./]+\.py)", text):
                rel = m.group(1).lstrip("./")
                candidate = repo_dir / rel
                if candidate.exists():
                    return candidate
            break

    return None


# Heuristic scoring can't be perfect for every repo layout. These are cases
# manually verified by inspection: either the auto-picked file was clearly
# the wrong one (internal helper, not the real entrypoint), or a well-known
# correct entrypoint that scoring missed. Confirmed matches noted where they
# line up with prior verified paths in nexus-progress memory.
MANUAL_OVERRIDES = {
    ("forensics", "volatility3"): "forensics/volatility3/vol.py",  # confirmed correct (nexus-progress memory)
    ("defense", "Wazuh"): None,       # full SIEM platform, no single CLI entrypoint
    ("defense", "Zeek"): None,        # compiled C++ binary, not installed, no .py entrypoint
    ("defense", "sigma"): None,       # rule spec/converter, matched file is just a doc checker
    ("malware", "CAPEv2"): None,      # full sandbox platform, not a standalone script
    ("scan", "Legion"): None,         # PyQt GUI tool, not headless-runnable
    ("exploit", "impacket"): None,    # library with many example scripts, no single entrypoint
    ("exploit", "pwntools"): None,    # library, not a standalone CLI tool
    ("post_exploit", "LinPEAS"): None,  # matched file was the .sh builder, not the real scanner
}


def main():
    registry = []
    for category in list_categories():
        for tool in list_tools(category):
            entry = {"category": category, "tool": tool, "type": "unknown", "invoke": None, "path": None}

            found_binary = None
            for cand in candidate_binaries(tool):
                path = wsl_which(cand)
                if path:
                    found_binary = cand
                    break

            override_key = (category, tool)
            if found_binary:
                entry["type"] = "system"
                entry["invoke"] = found_binary
                entry["path"] = None
            elif override_key in MANUAL_OVERRIDES:
                override_rel = MANUAL_OVERRIDES[override_key]
                if override_rel:
                    local = SCRIPTS_DIR / override_rel
                    entry["type"] = "local"
                    wsl_path = to_wsl_path(local)
                    entry["invoke"] = f"python3 {wsl_path}"
                    entry["path"] = wsl_path
                # else: stays "unknown" by design (see MANUAL_OVERRIDES comment)
            else:
                local = find_local_entrypoint(category, tool)
                if local:
                    entry["type"] = "local"
                    wsl_path = to_wsl_path(local)
                    entry["invoke"] = f"python3 {wsl_path}"
                    entry["path"] = wsl_path

            registry.append(entry)
            print(f"[{entry['type']:7s}] {category:12s} {tool:20s} -> {entry['invoke']}")

    REGISTRY_PATH.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")

    counts = {}
    for e in registry:
        counts[e["type"]] = counts.get(e["type"], 0) + 1
    print("\n=== Summary ===")
    for t, c in counts.items():
        print(f"{t}: {c}")
    print(f"Total: {len(registry)}")
    print(f"\nSaved -> {REGISTRY_PATH}")


if __name__ == "__main__":
    main()
