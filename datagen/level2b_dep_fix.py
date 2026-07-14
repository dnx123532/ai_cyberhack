"""Level 2b — Dependency Auto-Recovery for real-argument runs.

Same idea as Level 1b, applied to Level 2's failures: a tool that answers
`-h` fine can still hit a missing module deeper in its real code path
(e.g. dirsearch's csv report only imports `defusedcsv` once a scan
actually starts). Real pip install, real retry, honest outcome.
"""
import json

from common import OUTPUT_DIR, run_wsl, reset_jsonl, append_jsonl, attempt_dependency_fix

IN_PATH = OUTPUT_DIR / "level2_basic_exec.jsonl"
OUT_PATH = OUTPUT_DIR / "level2b_dep_fix.jsonl"


def main():
    entries = [json.loads(l) for l in IN_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
    failures = [e for e in entries if e.get("stage") == "basic_execution" and e["exit_code"] not in (0,)]

    reset_jsonl(OUT_PATH)
    fixed, still_broken, no_known_fix = 0, 0, 0

    for i, entry in enumerate(failures):
        category, tool, cmd = entry["category"], entry["tool"], entry["command"]
        transcript, resolved, last_out, last_err, last_code = attempt_dependency_fix(
            cmd, entry["stdout"], entry["stderr"], entry["exit_code"], run_timeout=60,
        )

        if resolved:
            fixed += 1
            status = "FIXED"
        elif transcript:
            still_broken += 1
            status = "STILL BROKEN after fix attempts"
        else:
            no_known_fix += 1
            status = "no known auto-fix (not a missing-module error)"

        example = {
            "level": "2b",
            "stage": "dependency_recovery",
            "category": category,
            "tool": tool,
            "resolved": resolved,
            "initial": {"command": cmd, "stdout": entry["stdout"], "stderr": entry["stderr"], "exit_code": entry["exit_code"]},
            "transcript": transcript,
            "verified_real_execution": True,
        }
        append_jsonl(OUT_PATH, example)
        print(f"[{i+1}/{len(failures)}] {category}/{tool} -> {status}")

    print("\n=== Level 2b summary ===")
    print(json.dumps({"fixed": fixed, "still_broken": still_broken, "no_known_fix": no_known_fix}, indent=2))
    print(f"Saved -> {OUT_PATH}")


if __name__ == "__main__":
    main()
