"""Level 1 — Tool Discovery.

The simplest possible skill: given a tool name, know how to invoke it and
see what it actually prints for `-h`/`--help`. No target, no arguments to
get wrong, no reasoning about workflow — just "this is how you ask this
tool what it does" grounded in a REAL command run against the REAL binary
or script that exists on this machine right now.

This is the foundation level 2+ build on: level 2 reuses the exact same
invoke string learned here, just with real arguments added.
"""
import json

from common import OUTPUT_DIR, load_registry, run_wsl, reset_jsonl, append_jsonl

OUT_PATH = OUTPUT_DIR / "level1_discovery.jsonl"

INSTRUCTION_TEMPLATES = [
    "ada tool {tool} di kategori {category}, cara pakenya gimana?",
    "gw mau tau {tool} itu tool apa dan opsi apa aja yang ada, tolong cek",
    "munculin help/usage buat {tool} dong",
    "sebelum eksekusi, cek dulu {tool} punya flag apa aja",
]


def try_help(invoke: str, tool: str):
    """Try -h then --help, keep whichever actually produced real output."""
    for flag in ("-h", "--help"):
        cmd = f"{invoke} {flag}"
        stdout, stderr, code = run_wsl(cmd, timeout=30)
        combined = (stdout + stderr).strip()
        if combined:
            return cmd, stdout, stderr, code
    # neither flag produced output — still record the last attempt as honest signal
    return cmd, stdout, stderr, code


def main():
    registry = load_registry()
    runnable = [e for e in registry if e["type"] in ("system", "local")]

    reset_jsonl(OUT_PATH)
    results = {"ok": 0, "empty_or_error": 0}

    for i, entry in enumerate(runnable):
        category, tool, invoke = entry["category"], entry["tool"], entry["invoke"]
        cmd, stdout, stderr, code = try_help(invoke, tool)

        has_output = bool((stdout + stderr).strip())
        looks_ok = has_output and code == 0
        results["ok" if looks_ok else "empty_or_error"] += 1

        example = {
            "level": 1,
            "stage": "tool_discovery",
            "category": category,
            "tool": tool,
            "tool_type": entry["type"],
            "instruction": INSTRUCTION_TEMPLATES[i % len(INSTRUCTION_TEMPLATES)].format(tool=tool, category=category),
            "command": cmd,
            "stdout": stdout[:6000],
            "stderr": stderr[:2000],
            "exit_code": code,
            "verified_real_execution": True,
        }
        append_jsonl(OUT_PATH, example)
        status = "OK" if looks_ok else f"EXIT={code} (no clean help output)"
        print(f"[{i+1}/{len(runnable)}] {category}/{tool} -> {status}")

    print("\n=== Level 1 summary ===")
    print(json.dumps(results, indent=2))
    print(f"Saved -> {OUT_PATH}")


if __name__ == "__main__":
    main()
