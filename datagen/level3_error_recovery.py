"""Level 3 — Error Recovery.

Builds on Level 2 directly: reuses the already-verified CORRECT command +
real output for each tool, and pairs it with a freshly, REALLY executed
BROKEN invocation (the tool's own invoke string called with no target
arguments at all). The model sees: real mistake -> real error message ->
real correct command -> real correct output, all four grounded in actual
execution, no step written by hand.

This is deliberately the simplest possible mistake (missing required
arg) because it's the one every one of these tools can demonstrate without
per-tool special-casing, and it's the single most common failure mode
described in the nexus-progress bug list (model calling tools with
incomplete/incorrect args).
"""
import json

from common import OUTPUT_DIR, run_wsl, reset_jsonl, append_jsonl

IN_PATH = OUTPUT_DIR / "level2_basic_exec.jsonl"
OUT_PATH = OUTPUT_DIR / "level3_error_recovery.jsonl"


def bare_invoke(full_cmd: str) -> str:
    """Strip everything after the invoke itself -> just the bare tool call with no args."""
    # entries store the full "invoke args..." command; the invoke portion is
    # reconstructed from the known prefix patterns (system binary, or `python3 <path>`).
    parts = full_cmd.split()
    if parts[0] == "python3":
        return " ".join(parts[:2])  # python3 <script.py>
    return parts[0]


def main():
    entries = [json.loads(l) for l in IN_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
    executed = [e for e in entries if e.get("stage") == "basic_execution" and e["exit_code"] == 0]

    reset_jsonl(OUT_PATH)
    demonstrates_failure, ran_fine_anyway = 0, 0

    for i, entry in enumerate(executed):
        category, tool = entry["category"], entry["tool"]
        broken_cmd = bare_invoke(entry["command"])
        stdout, stderr, code = run_wsl(broken_cmd, timeout=20)

        broke = code != 0 or not (stdout + stderr).strip() or (stdout + stderr).strip() != entry["stdout"].strip()
        # Heuristic: if calling with zero args produced a *different, worse* result than
        # the real correct call, treat it as a genuine mistake example.
        is_error_example = code != 0

        example = {
            "level": 3,
            "stage": "error_recovery",
            "category": category,
            "tool": tool,
            "mistake": {
                "command": broken_cmd,
                "stdout": stdout[:3000],
                "stderr": stderr[:1000],
                "exit_code": code,
                "diagnosis": "argumen wajib gak dikasih (dijalanin tanpa target)" if is_error_example
                             else "ternyata tool ini tetep jalan tanpa argumen tambahan (semua opsional)",
            },
            "fix": {
                "command": entry["command"],
                "stdout": entry["stdout"],
                "stderr": entry["stderr"],
                "exit_code": entry["exit_code"],
            },
            "verified_real_execution": True,
        }
        append_jsonl(OUT_PATH, example)
        if is_error_example:
            demonstrates_failure += 1
        else:
            ran_fine_anyway += 1
        print(f"[{i+1}/{len(executed)}] {category}/{tool} -> {'real error captured' if is_error_example else 'ran fine bare (no error to recover from)'}")

    print(f"\nDemonstrates real error->fix: {demonstrates_failure}")
    print(f"Ran fine even bare (kept as honest 'args are optional' note): {ran_fine_anyway}")
    print(f"Saved -> {OUT_PATH}")


if __name__ == "__main__":
    main()
