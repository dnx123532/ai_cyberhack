"""Level 1b — Dependency Auto-Recovery.

Takes every Level 1 failure, actually diagnoses WHY it failed, and (when
it's a missing Python package) actually runs `pip3 install` for real and
re-tries — capturing the full multi-turn transcript: broken -> diagnose ->
fix -> re-run -> real outcome.

This is the first "error recovery" skill: recognizing "this isn't a wrong
command, the environment is missing a dependency" and fixing it for real,
not guessing. Tools that fail for other reasons (no pip-installable fix
found) are left as honest unresolved examples — we don't fake a fix.
"""
import json
import re

from common import OUTPUT_DIR, run_wsl, reset_jsonl, append_jsonl

IN_PATH = OUTPUT_DIR / "level1_discovery.jsonl"
OUT_PATH = OUTPUT_DIR / "level1b_dep_fix.jsonl"

MAX_FIX_ATTEMPTS = 4

# Common cases where the pip package name doesn't match the `import` name.
PIP_NAME_ALIASES = {
    "yaml": "pyyaml",
    "cv2": "opencv-python",
    "Crypto": "pycryptodome",
    "dateutil": "python-dateutil",
    "PIL": "pillow",
    "bs4": "beautifulsoup4",
    "OpenSSL": "pyopenssl",
    "usb": "pyusb",
    "serial": "pyserial",
    "Xlib": "python-xlib",
    "jwt": "pyjwt",
    "dns": "dnspython",
    "OneLogin_SAML2": "python3-saml",
}

MODULE_NOT_FOUND_RE = re.compile(r"No module named ['\"]([A-Za-z0-9_.]+)['\"]")


def extract_missing_module(text: str):
    m = MODULE_NOT_FOUND_RE.search(text)
    if not m:
        return None
    return m.group(1).split(".")[0]


def pip_install(module: str):
    pkg = PIP_NAME_ALIASES.get(module, module)
    cmd = f"pip3 install --break-system-packages -q {pkg} 2>&1 | tail -n 40"
    stdout, stderr, code = run_wsl(cmd, timeout=180)
    return pkg, cmd, stdout, stderr, code


def main():
    entries = [json.loads(l) for l in IN_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
    failures = [e for e in entries if e["exit_code"] != 0]

    reset_jsonl(OUT_PATH)
    fixed, still_broken, no_known_fix = 0, 0, 0

    for i, entry in enumerate(failures):
        category, tool, cmd = entry["category"], entry["tool"], entry["command"]
        transcript = [{
            "step": "initial_run",
            "command": cmd,
            "stdout": entry["stdout"],
            "stderr": entry["stderr"],
            "exit_code": entry["exit_code"],
        }]

        last_stdout, last_stderr, last_code = entry["stdout"], entry["stderr"], entry["exit_code"]
        resolved = False

        for attempt in range(MAX_FIX_ATTEMPTS):
            missing = extract_missing_module(last_stdout + last_stderr)
            if not missing:
                break  # not a missing-module error we know how to fix

            pkg, install_cmd, install_out, install_err, install_code = pip_install(missing)
            transcript.append({
                "step": f"pip_install_attempt_{attempt+1}",
                "missing_module": missing,
                "pip_package_tried": pkg,
                "command": install_cmd,
                "stdout": install_out[:2000],
                "stderr": install_err[:1000],
                "exit_code": install_code,
            })

            last_stdout, last_stderr, last_code = run_wsl(cmd, timeout=30)
            transcript.append({
                "step": f"retry_run_{attempt+1}",
                "command": cmd,
                "stdout": last_stdout[:6000],
                "stderr": last_stderr[:2000],
                "exit_code": last_code,
            })

            if last_code == 0 and (last_stdout + last_stderr).strip():
                resolved = True
                break

        if resolved:
            fixed += 1
            status = "FIXED"
        elif len(transcript) > 1:
            still_broken += 1
            status = "STILL BROKEN after fix attempts"
        else:
            no_known_fix += 1
            status = "no known auto-fix (not a missing-module error)"

        example = {
            "level": "1b",
            "stage": "dependency_recovery",
            "category": category,
            "tool": tool,
            "resolved": resolved,
            "transcript": transcript,
            "verified_real_execution": True,
        }
        append_jsonl(OUT_PATH, example)
        print(f"[{i+1}/{len(failures)}] {category}/{tool} -> {status}")

    print("\n=== Level 1b summary ===")
    print(json.dumps({"fixed": fixed, "still_broken": still_broken, "no_known_fix": no_known_fix}, indent=2))
    print(f"Saved -> {OUT_PATH}")


if __name__ == "__main__":
    main()
