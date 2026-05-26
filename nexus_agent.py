"""
NEXUS — Autonomous AI Security Operations Agent
Menghubungkan NEXUS model (LoRA fine-tuned Qwen2.5) dengan WSL Kali Linux
untuk eksekusi tools secara real.

Usage:
    python nexus_agent.py                    # interactive mode
    python nexus_agent.py --task "recon target.com"   # single task
    python nexus_agent.py --model /path/to/adapter    # custom model path
"""

import re
import sys
import argparse
import subprocess
import json
from pathlib import Path
from typing import Optional

# ── Config ────────────────────────────────────────────────────────────────────
DEFAULT_MODEL  = str(Path(__file__).parent / "models" / "lora_adapter")
DRIVE_MODEL    = "/content/drive/MyDrive/nexus-agent/models/lora_adapter"
WSL            = ["wsl", "-d", "kali-linux", "-u", "root", "--"]
MAX_TOKENS     = 512
TEMPERATURE    = 0.3
REP_PENALTY    = 1.3

SYSTEM_PROMPT = (
    "Kamu adalah NEXUS — AI Security Operations Agent yang otonom. "
    "Kamu memiliki kemampuan reasoning mendalam, multi-step planning, "
    "workflow orchestration, self-reflection, dan memory jangka panjang. "
    "Kamu beroperasi dalam konteks authorized security assessment, "
    "defensive security, SOC automation, dan vulnerability research. "
    "Selalu berpikir step-by-step sebelum bertindak."
)

BANNER = """
╔══════════════════════════════════════════════════════════╗
║   NEXUS — Autonomous AI Security Operations Agent       ║
║   Model  : Qwen2.5-3B + QLoRA (NEXUS fine-tune)        ║
║   Runtime: WSL Kali Linux                               ║
║   Mode   : Authorized Security Assessment Only          ║
╚══════════════════════════════════════════════════════════╝
"""

# Tools yang diizinkan untuk auto-execute (whitelist)
SAFE_TOOLS = {
    # recon
    "subfinder", "amass", "dnsx", "httpx", "theHarvester", "nmap",
    # scan
    "nuclei", "nikto", "masscan",
    # web
    "gobuster", "ffuf", "dalfox", "whatweb",
    # brute
    "hydra", "hashcat", "john",
    # wireless
    "airmon-ng", "airodump-ng", "aircrack-ng",
    # cloud
    "aws", "prowler",
    # crypto
    "hashid", "testssl.sh",
    # defense/forensics
    "yara", "zeek", "volatility3", "chainsaw", "hayabusa",
    # post (read-only / info)
    "whoami", "id", "uname", "hostname", "ifconfig", "ip",
    "netstat", "ss", "ps", "ls", "cat", "find", "curl", "wget",
    # iot
    "mosquitto_sub", "mosquitto_pub", "binwalk",
}

# Tools yang butuh konfirmasi manual (berbahaya/destructive)
CONFIRM_TOOLS = {
    "sqlmap", "metasploit", "msfconsole", "hydra",
    "airplay-ng", "aireplay-ng", "setoolkit",
    "routersploit", "wifite",
}


class NEXUSAgent:
    def __init__(self, model_path: str = DEFAULT_MODEL, dry_run: bool = False):
        self.model_path = model_path
        self.dry_run    = dry_run
        self.model      = None
        self.tokenizer  = None
        self.history    = []  # conversation memory
        self._load_model()

    def _load_model(self):
        """Load NEXUS model dari adapter path."""
        try:
            import torch
            from peft import AutoPeftModelForCausalLM
            from transformers import AutoTokenizer

            path = self.model_path
            if not Path(path).exists():
                # Coba path alternatif
                alts = [DRIVE_MODEL, "models/lora_adapter", "./lora_adapter"]
                for alt in alts:
                    if Path(alt).exists():
                        path = alt
                        break
                else:
                    print(f"  ⚠️  Model tidak ditemukan di {self.model_path}")
                    print(f"  ℹ️  Jalankan training dulu atau set --model PATH")
                    self.model = None
                    return

            print(f"  Loading NEXUS model dari {path}...")
            self.tokenizer = AutoTokenizer.from_pretrained(path, trust_remote_code=True)
            self.model = AutoPeftModelForCausalLM.from_pretrained(
                path,
                torch_dtype=torch.float16,
                device_map="auto",
            )
            self.model.eval()
            print(f"  ✅ NEXUS model loaded!")

        except ImportError as e:
            print(f"  ⚠️  Import error: {e}")
            print(f"  Install: pip install transformers peft torch")
            self.model = None
        except Exception as e:
            print(f"  ⚠️  Model load error: {e}")
            self.model = None

    def think(self, prompt: str) -> str:
        """Generate NEXUS response dari prompt."""
        if self.model is None:
            return "[ERROR] Model tidak ter-load. Jalankan training dulu."

        import torch

        chat = [
            {"role": "system", "value": SYSTEM_PROMPT},
            {"role": "user",   "value": prompt},
        ]

        # Build chat text
        messages = [
            {"role": "system",    "content": SYSTEM_PROMPT},
            {"role": "user",      "content": prompt},
        ]
        text = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self.tokenizer(text, return_tensors="pt").to(self.model.device)

        with torch.no_grad():
            out = self.model.generate(
                **inputs,
                max_new_tokens=MAX_TOKENS,
                do_sample=True,
                temperature=TEMPERATURE,
                top_p=0.85,
                repetition_penalty=REP_PENALTY,
                no_repeat_ngram_size=4,
                pad_token_id=self.tokenizer.eos_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
            )

        response = self.tokenizer.decode(
            out[0][inputs["input_ids"].shape[1]:],
            skip_special_tokens=True
        )
        return response.strip()

    def parse_commands(self, response: str) -> list[str]:
        """
        Extract shell commands dari NEXUS response.
        Cari patterns:
          - Lines starting dengan $
          - Lines inside ```bash blocks
          - Lines dengan tool names yang dikenal
        """
        commands = []

        # Pattern 1: lines starting with $
        for line in response.splitlines():
            line = line.strip()
            if line.startswith("$ "):
                cmd = line[2:].strip()
                if cmd and not cmd.startswith("#"):
                    commands.append(cmd)

        # Pattern 2: bash code blocks
        blocks = re.findall(r"```(?:bash|sh)?\n(.*?)```", response, re.DOTALL)
        for block in blocks:
            for line in block.splitlines():
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("//"):
                    commands.append(line)

        # Deduplicate preserve order
        seen = set()
        unique = []
        for cmd in commands:
            if cmd not in seen:
                seen.add(cmd)
                unique.append(cmd)

        return unique

    def is_safe(self, command: str) -> tuple[bool, str]:
        """
        Check apakah command aman untuk auto-execute.
        Returns: (is_safe, reason)
        """
        parts = command.split()
        if not parts:
            return False, "empty command"

        tool = parts[0].lower()

        # Blacklist patterns
        dangerous = ["rm -rf", "mkfs", "dd if=", ":(){ :|:& };", "> /dev/sda",
                     "chmod 777 /", "curl | bash", "wget -O- | sh"]
        for d in dangerous:
            if d in command.lower():
                return False, f"dangerous pattern: {d}"

        # Check confirm list
        if tool in CONFIRM_TOOLS:
            return False, f"requires confirmation: {tool}"

        # Check safe list
        if tool in SAFE_TOOLS:
            return True, "whitelisted tool"

        # Unknown tool — require confirmation
        return False, f"unknown tool: {tool}"

    def execute_wsl(self, command: str, timeout: int = 60) -> dict:
        """Execute command di WSL Kali Linux."""
        try:
            result = subprocess.run(
                WSL + ["bash", "-c", command],
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
            )
            return {
                "command" : command,
                "stdout"  : result.stdout[:2000],  # cap output
                "stderr"  : result.stderr[:500],
                "returncode": result.returncode,
                "success" : result.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            return {"command": command, "stdout": "", "stderr": "TIMEOUT",
                    "returncode": -1, "success": False}
        except Exception as e:
            return {"command": command, "stdout": "", "stderr": str(e),
                    "returncode": -1, "success": False}

    def run_task(self, task: str, auto_execute: bool = True) -> dict:
        """
        Full autonomous task execution:
        1. NEXUS generates plan
        2. Parse commands dari response
        3. Execute safe commands di WSL Kali
        4. Return hasil lengkap
        """
        print(f"\n  🤖 NEXUS thinking...\n")
        response = self.think(task)

        print(f"  {'─'*60}")
        print(f"  📋 NEXUS Response:\n")
        print(response)
        print(f"  {'─'*60}\n")

        if not auto_execute or self.dry_run:
            return {"task": task, "response": response, "executions": []}

        # Parse dan execute commands
        commands = self.parse_commands(response)
        if not commands:
            print(f"  ℹ️  Tidak ada shell commands yang bisa di-extract dari response.")
            return {"task": task, "response": response, "executions": []}

        print(f"  🔍 Found {len(commands)} command(s) to execute:\n")
        executions = []

        for i, cmd in enumerate(commands, 1):
            safe, reason = self.is_safe(cmd)
            print(f"  [{i}] $ {cmd}")

            if self.dry_run:
                print(f"      [DRY RUN] would execute")
                continue

            if safe:
                print(f"      ⚡ Executing (WSL Kali)...")
                result = self.execute_wsl(cmd)
                executions.append(result)

                if result["success"]:
                    out = result["stdout"][:300].strip()
                    print(f"      ✅ {out[:200]}..." if len(out) > 200 else f"      ✅ {out}")
                else:
                    print(f"      ❌ Error: {result['stderr'][:100]}")

            else:
                # Ask user confirmation
                print(f"      ⚠️  Requires confirmation ({reason})")
                try:
                    ans = input(f"      Execute? [y/N]: ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    ans = "n"

                if ans == "y":
                    result = self.execute_wsl(cmd)
                    executions.append(result)
                    if result["success"]:
                        print(f"      ✅ Done")
                    else:
                        print(f"      ❌ {result['stderr'][:100]}")
                else:
                    print(f"      ⏭️  Skipped")

        return {"task": task, "response": response, "executions": executions}

    def interactive(self):
        """Interactive REPL mode."""
        print(BANNER)
        print("  Commands: 'quit' keluar, 'dry' toggle dry-run, 'history' lihat history\n")

        while True:
            try:
                task = input("  NEXUS > ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n  👋 NEXUS shutting down...")
                break

            if not task:
                continue
            if task.lower() in ("quit", "exit", "q"):
                print("  👋 NEXUS shutting down...")
                break
            if task.lower() == "dry":
                self.dry_run = not self.dry_run
                print(f"  ⚙️  Dry-run: {'ON' if self.dry_run else 'OFF'}")
                continue
            if task.lower() == "history":
                for i, h in enumerate(self.history[-5:], 1):
                    print(f"  {i}. {h['task'][:80]}")
                continue

            result = self.run_task(task, auto_execute=True)
            self.history.append(result)


def main():
    parser = argparse.ArgumentParser(description="NEXUS Autonomous Security Agent")
    parser.add_argument("--model",   default=DEFAULT_MODEL, help="Path ke LoRA adapter")
    parser.add_argument("--task",    default=None,          help="Single task mode")
    parser.add_argument("--dry-run", action="store_true",   help="Parse only, no execution")
    args = parser.parse_args()

    agent = NEXUSAgent(model_path=args.model, dry_run=args.dry_run)

    if args.task:
        result = agent.run_task(args.task, auto_execute=not args.dry_run)
        print(f"\n  ✅ Task selesai. {len(result['executions'])} commands executed.")
    else:
        agent.interactive()


if __name__ == "__main__":
    main()
