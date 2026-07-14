"""Shared helpers for the curriculum data generator.

Every training example in this pipeline is grounded in a REAL command that
was actually executed inside WSL Kali — no hand-written/hallucinated
command+output pairs. That was the root cause of the tool-path and
hallucinated-result bugs in the previous dataset (see nexus-progress memory).
"""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = ROOT / "tools"
SCRIPTS_DIR = ROOT / "data" / "raw_datasets" / "tool_scripts"
DATAGEN_DIR = ROOT / "datagen"
OUTPUT_DIR = DATAGEN_DIR / "output"
REGISTRY_PATH = DATAGEN_DIR / "registry.json"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

WSL_DISTRO = "kali-linux"


def run_wsl(cmd: str, timeout: int = 60):
    """Run a bash command for real inside WSL Kali and capture actual stdout/stderr/exit code."""
    try:
        proc = subprocess.run(
            ["wsl", "-d", WSL_DISTRO, "-u", "root", "--", "bash", "-c", cmd],
            capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
        )
        return proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as e:
        stdout = (e.stdout or "") if isinstance(e.stdout, str) else (e.stdout or b"").decode("utf-8", "replace")
        stderr = (e.stderr or "") if isinstance(e.stderr, str) else (e.stderr or b"").decode("utf-8", "replace")
        return stdout, stderr + f"\n[TIMEOUT after {timeout}s]", -1


def wsl_which(binary: str) -> str | None:
    out, _, code = run_wsl(f"which {binary} 2>/dev/null")
    out = out.strip()
    return out if code == 0 and out else None


def append_jsonl(path: Path, obj: dict):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def reset_jsonl(path: Path):
    path.write_text("", encoding="utf-8")


def list_categories():
    return sorted(p.name for p in TOOLS_DIR.iterdir() if p.is_dir())


def list_tools(category: str):
    cat_dir = TOOLS_DIR / category
    if not cat_dir.exists():
        return []
    return sorted(p.stem for p in cat_dir.glob("*.py"))


def load_registry():
    if not REGISTRY_PATH.exists():
        raise FileNotFoundError("registry.json belum ada, jalankan build_registry.py dulu")
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def to_wsl_path(win_path: Path) -> str:
    """E:\\agent_cyberhack\\x -> /mnt/e/agent_cyberhack/x"""
    s = str(win_path).replace("\\", "/")
    drive, rest = s.split(":", 1)
    return f"/mnt/{drive.lower()}{rest}"


PIP_NAME_ALIASES = {
    "yaml": "pyyaml", "cv2": "opencv-python", "Crypto": "pycryptodome",
    "dateutil": "python-dateutil", "PIL": "pillow", "bs4": "beautifulsoup4",
    "OpenSSL": "pyopenssl", "usb": "pyusb", "serial": "pyserial",
    "Xlib": "python-xlib", "jwt": "pyjwt", "dns": "dnspython",
    "OneLogin_SAML2": "python3-saml",
}

import re as _re
_MODULE_NOT_FOUND_RE = _re.compile(r"No module named ['\"]([A-Za-z0-9_.]+)['\"]")


def extract_missing_module(text: str):
    m = _MODULE_NOT_FOUND_RE.search(text)
    return m.group(1).split(".")[0] if m else None


def attempt_dependency_fix(cmd: str, stdout: str, stderr: str, code: int,
                            run_timeout: int = 30, max_attempts: int = 4):
    """Real pip-install-and-retry loop. Returns (transcript, resolved, final_stdout, final_stderr, final_code)."""
    transcript = []
    last_stdout, last_stderr, last_code = stdout, stderr, code
    resolved = False

    for attempt in range(max_attempts):
        missing = extract_missing_module(last_stdout + last_stderr)
        if not missing:
            break
        pkg = PIP_NAME_ALIASES.get(missing, missing)
        install_cmd = f"pip3 install --break-system-packages -q {pkg} 2>&1 | tail -n 40"
        install_out, install_err, install_code = run_wsl(install_cmd, timeout=180)
        transcript.append({
            "step": f"pip_install_attempt_{attempt+1}",
            "missing_module": missing,
            "pip_package_tried": pkg,
            "command": install_cmd,
            "stdout": install_out[:2000],
            "stderr": install_err[:1000],
            "exit_code": install_code,
        })
        last_stdout, last_stderr, last_code = run_wsl(cmd, timeout=run_timeout)
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

    return transcript, resolved, last_stdout, last_stderr, last_code
