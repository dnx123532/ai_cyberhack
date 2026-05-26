"""
NEXUS — Shared utilities. Import ini di semua module untuk hindari duplikasi.
"""
import sys, json, logging
from pathlib import Path
from collections import deque

# ── UTF-8 stdout (call once at entry point) ───────────────────────────────────
def setup_encoding():
    sys.stdout.reconfigure(encoding="utf-8")

# ── Logging ───────────────────────────────────────────────────────────────────
def get_logger(name: str) -> logging.Logger:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    return logging.getLogger(name)

# ── Paths (relative to project root, resolve at import time) ─────────────────
ROOT = Path(__file__).parent.parent  # E:\agent_cyberhack

def root(*parts) -> Path:
    return ROOT.joinpath(*parts)

# ── Dir helpers ───────────────────────────────────────────────────────────────
def ensure_dir(path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p

# ── JSON helpers ──────────────────────────────────────────────────────────────
def load_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default

def save_json(path, data, pretty: bool = True):
    p = Path(path)
    ensure_dir(p.parent)
    indent = 2 if pretty else None
    p.write_text(json.dumps(data, indent=indent, ensure_ascii=False), encoding="utf-8")

def append_jsonl(path, record: dict):
    """Append one record to a JSONL file."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

def save_jsonl(path, records: list):
    """Write list of records as JSONL."""
    ensure_dir(Path(path).parent)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

# ── Conversation record builder ───────────────────────────────────────────────
SYSTEM_PROMPTS = {
    "default": (
        "Kamu adalah NEXUS — autonomous AI Security Operations Agent yang dirancang untuk "
        "melakukan reconnaissance, vulnerability assessment, monitoring, dan defensive security "
        "analysis secara otonom dalam lingkungan authorized."
    ),
    "tools": (
        "Kamu adalah NEXUS — AI Security Operations Agent. Kamu memiliki pengetahuan mendalam "
        "tentang ribuan security tools, workflow mereka, dan cara menggunakannya secara otonom "
        "dalam konteks authorized security assessment."
    ),
    "patterns": (
        "Kamu adalah NEXUS — AI Security Operations Agent yang mampu menulis automation script, "
        "memahami execution patterns, dan menjalankan workflow keamanan secara otonom."
    ),
}

def system_prompt(context: str = "default") -> str:
    return SYSTEM_PROMPTS.get(context, SYSTEM_PROMPTS["default"])

def make_conversation(human: str, gpt: str, context: str = "default") -> dict:
    return {
        "conversations": [
            {"from": "system", "value": system_prompt(context)},
            {"from": "human",  "value": human},
            {"from": "gpt",    "value": gpt},
        ]
    }

# ── Bounded log buffer ────────────────────────────────────────────────────────
def bounded_log(maxlen: int = 1000):
    """Return a deque with maxlen for bounded in-memory log."""
    return deque(maxlen=maxlen)
