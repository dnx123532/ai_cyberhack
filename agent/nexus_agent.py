"""NEXUS Agent v2 — Groq (Llama 3.3 70B) + registry-grounded tool execution.

Why this instead of the fine-tuned 7B model: a much larger, already-capable
model can follow a staged reasoning format (Berpikir -> Tool -> Aksi ->
Observasi -> Kesimpulan) from instructions alone, no training needed. The
part that actually matters for correctness — never hallucinating a tool
path — is enforced structurally here, not hoped for from weights: the model
is only ever allowed to name a tool via function-calling (`run_tool`), and
THIS CODE (not the model) resolves that name against datagen/registry.json
and executes the real, verified invoke string in WSL. The model never
writes a path; it can't get one wrong.
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from env import load_env
from registry_lookup import ToolRegistry

import os

load_env()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

import subprocess

WSL_DISTRO = "kali-linux"


def run_wsl(cmd: str, timeout: int = 60):
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


SYSTEM_PROMPT_TEMPLATE = """Kamu adalah NEXUS — AI cyberhack Operations Agent untuk authorized hacking and security \
,attacking, defensive security, dan vulnerability research.

Setiap jawaban WAJIB ngikutin tahapan eksplisit:
[Berpikir] alasan sebelum bertindak — apa yang diminta, tool apa yang relevan, argumen apa yang dibutuhin Untuk cyberhack.
[Tool] tool yang dipilih (harus salah satu dari daftar registry di bawah) — ATAU putusin buat nulis script sendiri kalau emang gak ada yang cocok.
[Aksi] panggil salah satu function di bawah — JANGAN PERNAH nulis path file/command mentah di teks jawaban, itu selalu salah karena kamu gak bisa ngapalin path persis. Panggil function-nya, sistem yang tau path aslinya.
[Observasi] hasil nyata dari eksekusi (dikasih balik lewat function result). Kalau error, boleh coba lagi (benerin lalu panggil function lagi) sampai beres atau emang gak bisa.
[Kesimpulan] jawaban akhir ke user berdasarkan observasi nyata di atas — jangan pernah ngarang hasil.

Ada 2 function buat eksekusi:
1. `run_tool` — buat tool yang UDAH terdaftar di registry di bawah. Selalu coba ini duluan.
2. `run_custom_script` — kalau gak ada tool terdaftar yang cocok buat kebutuhan spesifik ini, tulis Python script sendiri dan jalanin beneran. Kalau error, baca errornya, revisi kodenya, panggil lagi sampai jalan.

Kalau tool yang dibutuhin gak ada di registry DAN gak ada cara nulis script sendiri yang masuk akal, JUJUR bilang gak bisa — jangan ngarang tool atau hasil.

=== REGISTRY TOOLS (ini SEMUA tool yang beneran ada & terverifikasi) ===
{registry_listing}
=== END REGISTRY ===
"""

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "run_tool",
            "description": "Execute a registered security tool for real against a target. "
                            "tool_name must exactly match a name from the registry list in the system prompt.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tool_name": {"type": "string", "description": "Exact registered tool name"},
                    "args": {"type": "string", "description": "Arguments to pass after the tool's invoke command "
                                                                "(e.g. '-d example.com -l 50 -b crtsh')"},
                },
                "required": ["tool_name", "args"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_custom_script",
            "description": "Write and REALLY execute a Python script in the WSL Kali sandbox, for when no "
                            "registered tool covers the need (e.g. brute-forcing a specific parameter value, "
                            "a one-off parsing/analysis task). If it errors, read the real error and call this "
                            "again with a fixed version — iterate until it works or it's genuinely not possible.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Full Python script source code to run"},
                },
                "required": ["code"],
            },
        },
    },
]


def build_registry_listing(registry: ToolRegistry) -> str:
    lines = []
    for entry in sorted(registry.by_norm_name.values(), key=lambda e: (e["category"], e["tool"])):
        lines.append(f"- {entry['tool']} ({entry['category']}, {entry['type']})")
    return "\n".join(lines)


def call_groq(messages, tools=None):
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY belum di-set. Taro di .env: GROQ_API_KEY=gsk_...")
    body = {"model": GROQ_MODEL, "messages": messages, "temperature": 0.3}
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    resp = requests.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
        json=body, timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def execute_registered_tool(registry: ToolRegistry, tool_name: str, args: str):
    entry = registry.resolve(tool_name)
    if entry is None:
        return {
            "found_in_registry": False,
            "message": f"'{tool_name}' TIDAK ADA di registry — ini bukan tool yang terverifikasi, jangan diklaim bisa jalan.",
        }
    cmd = f"{entry['invoke']} {args}".strip()
    stdout, stderr, code = run_wsl(cmd, timeout=60)
    return {
        "found_in_registry": True,
        "real_command_executed": cmd,
        "stdout": stdout[:4000],
        "stderr": stderr[:1000],
        "exit_code": code,
    }


_SCRATCH_DIR = "/root/.nexus_scratch"


def execute_custom_script(code: str, attempt: int = 1):
    run_wsl(f"mkdir -p {_SCRATCH_DIR}", timeout=10)
    write_cmd = f"cat > {_SCRATCH_DIR}/attempt_{attempt}.py << 'NEXUS_EOF'\n{code}\nNEXUS_EOF"
    _, werr, wcode = run_wsl(write_cmd, timeout=15)
    if wcode != 0:
        return {"wrote_file": False, "error": werr}
    stdout, stderr, code_ = run_wsl(f"cd {_SCRATCH_DIR} && python3 attempt_{attempt}.py", timeout=60)
    return {
        "wrote_file": True,
        "real_command_executed": f"python3 {_SCRATCH_DIR}/attempt_{attempt}.py",
        "stdout": stdout[:4000],
        "stderr": stderr[:2000],
        "exit_code": code_,
    }


MAX_TOOL_ROUNDS = 6  # cap iterate-until-it-works loops (Level 5 style) so a stuck model can't loop forever

DIM = "\033[2m"
RESET = "\033[0m"
CYAN = "\033[36m"


def _status(text: str):
    print(f"{DIM}{CYAN}  ⚙ {text}{RESET}")


def ask_nexus(user_message: str, registry: ToolRegistry | None = None, verbose: bool = True):
    registry = registry or ToolRegistry()
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(registry_listing=build_registry_listing(registry))
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    custom_script_attempt = 0
    for round_num in range(MAX_TOOL_ROUNDS):
        response = call_groq(messages, tools=TOOLS_SCHEMA)
        msg = response["choices"][0]["message"]
        messages.append(msg)

        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            return msg.get("content", "")

        for tc in tool_calls:
            fn_name = tc["function"]["name"]
            args = json.loads(tc["function"]["arguments"])

            if fn_name == "run_tool":
                tool_name, tool_args = args.get("tool_name", ""), args.get("args", "")
                if verbose:
                    _status(f"menjalankan {tool_name} {tool_args}".strip())
                result = execute_registered_tool(registry, tool_name, tool_args)
            elif fn_name == "run_custom_script":
                custom_script_attempt += 1
                if verbose:
                    _status(f"nulis & jalanin script custom (percobaan {custom_script_attempt})")
                result = execute_custom_script(args.get("code", ""), custom_script_attempt)
            else:
                result = {"error": f"unknown function {fn_name}"}

            if verbose:
                status_word = "selesai" if result.get("exit_code", 1) == 0 else f"exit {result.get('exit_code')}"
                _status(f"-> {status_word}")
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": json.dumps(result, ensure_ascii=False),
            })

    # hit the round cap without a final answer — ask once more without tools to force a wrap-up
    response = call_groq(messages)
    return response["choices"][0]["message"]["content"]


_STAGE_MARKERS = ("[Berpikir]", "[Tool]", "[Aksi]", "[Observasi]", "[Kesimpulan]")


def format_answer(text: str) -> str:
    """Dim the process stages, keep [Kesimpulan] (or plain prose with no
    stage markers at all) as the prominent final answer — same idea as how
    a 'thinking' block is shown separate from the final response."""
    if not any(m in text for m in _STAGE_MARKERS):
        return text

    import re
    parts = re.split(r"(\[Berpikir\]|\[Tool\]|\[Aksi\]|\[Observasi\]|\[Kesimpulan\])", text)
    out, current_label = [], None
    for chunk in parts:
        if chunk in _STAGE_MARKERS:
            current_label = chunk
            continue
        chunk = chunk.strip()
        if not chunk:
            continue
        if current_label == "[Kesimpulan]":
            out.append(chunk)
        else:
            out.append(f"{DIM}{chunk}{RESET}")
    return "\n\n".join(out)


def _run_one(reg, prompt: str):
    print(f"\n{'='*70}\n❓ {prompt}\n{'='*70}")
    answer = ask_nexus(prompt, reg)
    print(f"\n🤖 {format_answer(answer)}")


if __name__ == "__main__":
    reg = ToolRegistry()

    if len(sys.argv) > 1:
        # one-shot: python nexus_agent.py "lakukan recon pada https://..."
        _run_one(reg, " ".join(sys.argv[1:]))
    else:
        # interactive: keep asking until you type exit/quit
        print("NEXUS Agent (Groq) — ketik pertanyaan/perintah, 'exit' buat keluar\n")
        while True:
            try:
                prompt = input("❓ ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not prompt:
                continue
            if prompt.lower() in ("exit", "quit", "q"):
                break
            answer = ask_nexus(prompt, reg)
            print(f"\n🤖 {format_answer(answer)}\n")
