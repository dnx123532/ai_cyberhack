"""Level 5 — Forge a new tool when nothing existing covers the need.

Scenario grounded in a REAL registry gap: none of the 40 tools in
registry.json (checked in Level 0) is a generic HTTP GET-parameter VALUE
brute-forcer (hydra/patator are protocol-specific, not in our registry at
all). Given a known param name ("token", discovered the same way Level 4
discovers real params), there is genuinely no existing tool to reach for.

So: write a script -> run it for real -> observe the REAL failure ->
fix -> run again -> REAL wrong-but-not-crashing result -> fix the actual
logic -> run again -> REAL success. Three real attempts, three real
outcomes, nothing here is narrated — every stdout/stderr/exit_code comes
from an actual `python3` invocation in WSL.
"""
import json
from pathlib import Path

from common import DATAGEN_DIR, OUTPUT_DIR, run_wsl, reset_jsonl, append_jsonl, to_wsl_path

FORGE_DIR = DATAGEN_DIR / "level5_forge"
OUT_PATH = OUTPUT_DIR / "level5_forge.jsonl"

ATTEMPTS = [
    ("attempt1_buggy_typo.py", "nulis requests.get tapi kepencet 'request.get' (typo umum, ketuker sama modul builtin)"),
    ("attempt2_logic_bug.py", "typo udah bener, tapi salah nentuin kondisi sukses (cek status_code==200 padahal endpoint ini SELALU return 200 apapun tokennya)"),
    ("attempt3_fixed.py", "fix beneran: cek isi response text buat 'welcome back', bukan status code"),
]


def main():
    reset_jsonl(OUT_PATH)
    transcript = []
    final_success = False

    for i, (filename, note) in enumerate(ATTEMPTS, start=1):
        script_path = FORGE_DIR / filename
        wsl_path = to_wsl_path(script_path)
        cmd = f"cd {to_wsl_path(FORGE_DIR)} && python3 {filename}"
        stdout, stderr, code = run_wsl(cmd, timeout=30)
        code_text = script_path.read_text(encoding="utf-8")

        step = {
            "attempt": i,
            "note": note,
            "code": code_text,
            "command": cmd,
            "stdout": stdout.strip(),
            "stderr": stderr.strip(),
            "exit_code": code,
        }
        transcript.append(step)
        print(f"[attempt {i}] {filename} -> exit={code}, stdout={stdout.strip()!r}")

        if "FOUND: letmein" in stdout:
            final_success = True

    example = {
        "level": 5,
        "stage": "forge_new_tool",
        "scenario": "gak ada tool di registry buat brute-force VALUE dari parameter GET yang namanya udah diketahui (token)",
        "registry_gap_confirmed": "hydra/patator gak ada di registry.json (level 0), keduanya juga protocol-specific bukan generic HTTP param value guesser",
        "instruction": "param 'token' di /profile udah ketemu namanya (dari Arjun-style discovery), tapi valuenya belum. Gak ada tool siap pakai, tulis sendiri, jalanin, benerin sampe beneran nemu.",
        "transcript": transcript,
        "final_success": final_success,
        "verified_real_execution": True,
    }
    append_jsonl(OUT_PATH, example)
    print(f"\nFinal success: {final_success}")
    print(f"Saved -> {OUT_PATH}")


if __name__ == "__main__":
    main()
