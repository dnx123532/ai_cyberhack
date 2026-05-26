"""
NEXUS — Autonomous AI Security Operations Agent
Menghubungkan NEXUS model (LoRA fine-tuned Qwen2.5) dengan WSL Kali Linux
untuk eksekusi tools secara real + browser automation.

Usage:
    python nexus_agent.py                          # interactive mode
    python nexus_agent.py --task "recon target.com"  # single task
    python nexus_agent.py --dry-run                # tanpa eksekusi
"""

import re
import sys
import argparse
import subprocess
import json
import time
import webbrowser
import urllib.parse
from pathlib import Path
from typing import Optional

# Tambah project root ke sys.path agar runtime/ bisa di-import
_ROOT = Path(__file__).parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ── Rich UI ───────────────────────────────────────────────────────────────────
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.syntax import Syntax
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.prompt import Prompt, Confirm
    from rich.text import Text
    from rich.rule import Rule
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

console = Console() if HAS_RICH else None

def cprint(msg, style=""):
    if HAS_RICH:
        console.print(msg, style=style)
    else:
        print(msg)

# ── Config ────────────────────────────────────────────────────────────────────
DEFAULT_MODEL = str(Path(__file__).parent / "models" / "lora_adapter")
DRIVE_MODEL   = "/content/drive/MyDrive/nexus-agent/models/lora_adapter"
WSL           = ["wsl", "-d", "kali-linux", "-u", "root", "--"]
MAX_TOKENS    = 512
TEMPERATURE   = 0.3
REP_PENALTY   = 1.3

SYSTEM_PROMPT = (
    "Kamu adalah NEXUS — AI Security Operations Agent yang otonom. "
    "Kamu memiliki kemampuan reasoning mendalam, multi-step planning, "
    "workflow orchestration, self-reflection, dan memory jangka panjang. "
    "Kamu beroperasi dalam konteks authorized security assessment, "
    "defensive security, SOC automation, dan vulnerability research. "
    "Selalu berpikir step-by-step sebelum bertindak."
)

BANNER = """
███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗
████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝
██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗
██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║
██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝███████║
╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝
  Autonomous AI Security Operations Agent
  Model: Qwen2.5-3B + QLoRA  |  Runtime: WSL Kali Linux
"""

# ── Tool Whitelist ────────────────────────────────────────────────────────────
SAFE_TOOLS = {
    "subfinder","amass","dnsx","httpx","theHarvester","nmap","masscan",
    "nuclei","nikto","whatweb","gobuster","ffuf","dalfox",
    "hashid","haiti","testssl.sh","testssl",
    "yara","zeek","chainsaw","hayabusa",
    "mosquitto_sub","mosquitto_pub","binwalk",
    "aws","prowler","kubectl",
    "whoami","id","uname","hostname","ifconfig","ip","netstat","ss",
    "ps","ls","cat","find","curl","wget","dig","nslookup","ping",
    "strings","file","md5sum","sha256sum","exiftool","objdump",
}

CONFIRM_TOOLS = {
    "sqlmap","hydra","medusa","hashcat","john",
    "airmon-ng","airodump-ng","aireplay-ng","aircrack-ng","wifite",
    "metasploit","msfconsole","msfvenom",
    "setoolkit","gophish","evilginx2",
    "routersploit","volatility3","mimikatz",
    "linpeas","winpeas",
}

BROWSER_SHORTCUTS = {
    "shodan"    : "https://www.shodan.io/search?query={}",
    "cve"       : "https://nvd.nist.gov/vuln/detail/{}",
    "exploit-db": "https://www.exploit-db.com/search?q={}",
    "crt.sh"    : "https://crt.sh/?q={}",
    "whois"     : "https://who.is/whois/{}",
    "virustotal": "https://www.virustotal.com/gui/search/{}",
}


class NEXUSAgent:
    def __init__(self, model_path: str = DEFAULT_MODEL, dry_run: bool = False,
                 dashboard: bool = True):
        self.model_path = model_path
        self.dry_run    = dry_run
        self.model      = None
        self.tokenizer  = None
        self.history    = []
        self._dashboard = None
        self._print_banner()
        if dashboard:
            self._start_dashboard()
        self._load_model()

    def _print_banner(self):
        if HAS_RICH:
            console.print(BANNER, style="bold green")
            console.print(Rule(style="green"))
        else:
            print(BANNER)

    def _start_dashboard(self):
        """Launch SOC dashboard di browser."""
        try:
            from runtime.dashboard_launcher import dashboard
            ok = dashboard.start(port=8080, open_browser=True)
            if ok:
                cprint(f"  [bold cyan]🖥️  SOC Dashboard → http://localhost:8080[/]")
            self._dashboard = dashboard
        except Exception as e:
            cprint(f"  [dim]ℹ️  Dashboard tidak tersedia: {e}[/]")
            self._dashboard = None

    def _push_to_dashboard(self, record: dict):
        """Push execution record ke dashboard log."""
        try:
            from shared.utils import append_jsonl, root
            append_jsonl(root("logs", "runtime", "executions.jsonl"), record)
        except Exception:
            pass

    def _load_model(self):
        if HAS_RICH:
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold green]{task.description}"),
                transient=True,
            ) as progress:
                progress.add_task("Loading NEXUS model...", total=None)
                self._do_load()
        else:
            print("  Loading NEXUS model...")
            self._do_load()

    def _do_load(self):
        try:
            import torch
            from peft import AutoPeftModelForCausalLM
            from transformers import AutoTokenizer

            path = self.model_path
            if not Path(path).exists():
                for alt in [DRIVE_MODEL, "models/lora_adapter", "./lora_adapter"]:
                    if Path(alt).exists():
                        path = alt
                        break
                else:
                    cprint(f"  [yellow]⚠️  Model tidak ditemukan: {self.model_path}[/]")
                    cprint("  [dim]Jalankan training dulu atau set --model PATH[/]")
                    return

            self.tokenizer = AutoTokenizer.from_pretrained(path, trust_remote_code=True)
            self.model = AutoPeftModelForCausalLM.from_pretrained(
                path, torch_dtype=torch.float16, device_map="auto"
            )
            self.model.eval()
            cprint(f"  [bold green]✅ NEXUS model loaded dari {path}[/]")

        except ImportError as e:
            cprint(f"  [red]⚠️  Import error: {e}[/]")
            cprint("  Install: pip install transformers peft torch")
        except Exception as e:
            cprint(f"  [red]⚠️  Model error: {e}[/]")

    # ── AI Core ───────────────────────────────────────────────────────────────

    def think(self, prompt: str) -> str:
        if self.model is None:
            return "[ERROR] Model belum ter-load."

        import torch

        messages = [
            {"role": "system",    "content": SYSTEM_PROMPT},
            {"role": "user",      "content": prompt},
        ]
        text   = self.tokenizer.apply_chat_template(
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
        return self.tokenizer.decode(
            out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True
        ).strip()

    # ── Command Parser ────────────────────────────────────────────────────────

    def parse_commands(self, response: str) -> list:
        commands = []
        # $ prefix lines
        for line in response.splitlines():
            line = line.strip()
            if line.startswith("$ "):
                cmd = line[2:].strip()
                if cmd and not cmd.startswith("#"):
                    commands.append(cmd)
        # ```bash blocks
        for block in re.findall(r"```(?:bash|sh)?\n(.*?)```", response, re.DOTALL):
            for line in block.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    commands.append(line)
        # deduplicate
        seen, unique = set(), []
        for c in commands:
            if c not in seen:
                seen.add(c)
                unique.append(c)
        return unique

    def is_safe(self, command: str) -> tuple:
        parts = command.split()
        if not parts:
            return False, "empty"
        tool = parts[0].lower()

        for dangerous in ["rm -rf /", "mkfs", "dd if=/dev", ":(){ :|:& };",
                          "curl | bash", "wget -O- | sh", "> /dev/sda"]:
            if dangerous in command.lower():
                return False, f"dangerous: {dangerous}"

        if tool in CONFIRM_TOOLS:
            return False, f"confirm required"
        if tool in SAFE_TOOLS:
            return True, "whitelisted"
        return False, f"unknown tool"

    # ── Terminal (WSL Kali) ───────────────────────────────────────────────────

    def execute_wsl(self, command: str, timeout: int = 60) -> dict:
        try:
            result = subprocess.run(
                WSL + ["bash", "-c", command],
                capture_output=True, text=True,
                timeout=timeout, encoding="utf-8", errors="replace",
            )
            return {
                "command"   : command,
                "stdout"    : result.stdout[:3000],
                "stderr"    : result.stderr[:500],
                "returncode": result.returncode,
                "success"   : result.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            return {"command": command, "stdout": "", "stderr": "TIMEOUT",
                    "returncode": -1, "success": False}
        except Exception as e:
            return {"command": command, "stdout": "", "stderr": str(e),
                    "returncode": -1, "success": False}

    def _show_result(self, result: dict):
        if not HAS_RICH:
            status = "✅" if result["success"] else "❌"
            print(f"      {status} {result['stdout'][:300]}")
            return

        if result["success"]:
            out = result["stdout"].strip()[:600]
            if out:
                console.print(
                    Panel(out, title="[green]Output[/]", border_style="green", expand=False)
                )
            else:
                cprint("      [green]✅ Done (no output)[/]")
        else:
            err = result["stderr"].strip()[:300]
            cprint(f"      [red]❌ Error: {err}[/]")

    # ── Browser ───────────────────────────────────────────────────────────────

    def open_browser(self, target: str, mode: str = "url"):
        """
        Open Chrome/browser.
        mode: 'url' langsung buka URL
              'shodan' search di shodan
              'cve' buka NVD page
              'exploit-db', 'crt.sh', 'whois', 'virustotal'
        """
        if mode in BROWSER_SHORTCUTS:
            url = BROWSER_SHORTCUTS[mode].format(urllib.parse.quote(target))
        elif target.startswith(("http://", "https://")):
            url = target
        else:
            url = f"https://{target}"

        cprint(f"\n  [cyan]🌐 Opening browser: {url}[/]")
        webbrowser.open(url)
        return url

    def screenshot_wsl(self, url: str, out_path: str = "/tmp/nexus_shot.png") -> dict:
        """Screenshot URL via headless Chromium di WSL Kali."""
        cmd = (
            f"chromium --headless --disable-gpu --no-sandbox "
            f"--disable-dev-shm-usage --screenshot={out_path} {url} 2>/dev/null || "
            f"chromium-browser --headless --disable-gpu --no-sandbox "
            f"--screenshot={out_path} {url} 2>/dev/null"
        )
        result = self.execute_wsl(cmd, timeout=30)
        result["screenshot"] = out_path
        return result

    # ── Task Runner ───────────────────────────────────────────────────────────

    def run_task(self, task: str, auto_execute: bool = True) -> dict:
        # 1. NEXUS think
        if HAS_RICH:
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold cyan]NEXUS sedang berpikir..."),
                transient=True,
            ) as p:
                p.add_task("", total=None)
                response = self.think(task)
        else:
            print("\n  🤖 NEXUS thinking...\n")
            response = self.think(task)

        # 2. Show response
        if HAS_RICH:
            console.print()
            console.print(Rule("[bold cyan]📋 NEXUS Response", style="cyan"))
            # Color-code sections
            colored = response
            for tag in ["Reasoning","Planning","Workflow","Tools","Action",
                        "Reflection","Memory","Solution","Security"]:
                colored = colored.replace(f"**[{tag}]**", f"[bold yellow]▶ [{tag}][/bold yellow]")
            console.print(colored)
            console.print(Rule(style="cyan"))
        else:
            print(f"\n{'─'*60}")
            print(response)
            print(f"{'─'*60}\n")

        # 3. Auto-detect browser actions
        self._auto_browser(task, response)

        if not auto_execute or self.dry_run:
            return {"task": task, "response": response, "executions": []}

        # 4. Parse commands
        commands = self.parse_commands(response)
        if not commands:
            cprint("\n  [dim]ℹ️  Tidak ada shell commands di response.[/]")
            return {"task": task, "response": response, "executions": []}

        # 5. Show command table
        if HAS_RICH:
            table = Table(title="Commands to Execute", box=box.ROUNDED,
                          border_style="cyan", show_lines=True)
            table.add_column("#",       style="dim", width=4)
            table.add_column("Command", style="bold white")
            table.add_column("Status",  style="green", width=20)
            for i, cmd in enumerate(commands, 1):
                safe, reason = self.is_safe(cmd)
                status = "[green]auto-exec[/]" if safe else f"[yellow]{reason}[/]"
                table.add_row(str(i), cmd, status)
            console.print()
            console.print(table)

        # 6. Execute
        executions = []
        for i, cmd in enumerate(commands, 1):
            safe, reason = self.is_safe(cmd)
            cprint(f"\n  [bold]\\[{i}][/] [cyan]$ {cmd}[/]")

            if self.dry_run:
                cprint("      [dim][DRY RUN] skipped[/]")
                continue

            if safe:
                cprint("      [green]⚡ Executing di WSL Kali...[/]")
                result = self.execute_wsl(cmd)
                executions.append(result)
                self._push_to_dashboard({**result, "tool": cmd.split()[0]})
                self._show_result(result)
            else:
                cprint(f"      [yellow]⚠️  {reason}[/]")
                if HAS_RICH:
                    confirm = Confirm.ask("      Execute?", default=False)
                else:
                    confirm = input("      Execute? [y/N]: ").strip().lower() == "y"

                if confirm:
                    result = self.execute_wsl(cmd)
                    executions.append(result)
                    self._push_to_dashboard({**result, "tool": cmd.split()[0]})
                    self._show_result(result)
                else:
                    cprint("      [dim]⏭️  Skipped[/]")

        # 7. Summary
        if executions and HAS_RICH:
            ok  = sum(1 for e in executions if e["success"])
            fail = len(executions) - ok
            console.print()
            console.print(Panel(
                f"[green]✅ Success: {ok}[/]   [red]❌ Failed: {fail}[/]   "
                f"[cyan]Total: {len(executions)}[/]",
                title="Execution Summary", border_style="cyan"
            ))

        return {"task": task, "response": response, "executions": executions}

    def _auto_browser(self, task: str, response: str):
        """Auto-buka browser berdasarkan keyword di task/response."""
        task_l = task.lower()
        # Auto Shodan
        if "shodan" in task_l or "shodan" in response.lower():
            domain = re.search(r'[\w.-]+\.(com|id|net|org|io)', task)
            if domain:
                self.open_browser(domain.group(), mode="shodan")
        # Auto CVE
        cves = re.findall(r'CVE-\d{4}-\d+', response, re.IGNORECASE)
        for cve in cves[:2]:  # max 2 CVE tabs
            self.open_browser(cve, mode="cve")
        # Auto crt.sh untuk subdomain
        if "crt.sh" in response or "certificate transparency" in task_l:
            domain = re.search(r'[\w.-]+\.(com|id|net|org|io)', task)
            if domain:
                self.open_browser(domain.group(), mode="crt.sh")

    # ── Interactive REPL ──────────────────────────────────────────────────────

    def interactive(self):
        if HAS_RICH:
            console.print(Panel(
                "[bold]Commands:[/]\n"
                "  [cyan]quit[/]       — keluar\n"
                "  [cyan]dry[/]        — toggle dry-run mode\n"
                "  [cyan]history[/]    — lihat task history\n"
                "  [cyan]browser URL[/] — buka URL di Chrome\n"
                "  [cyan]shodan X[/]   — search Shodan\n"
                "  [cyan]cve CVE-ID[/] — buka NVD CVE page\n"
                "  [cyan]shot URL[/]   — screenshot URL via WSL Chromium",
                title="[bold green]NEXUS Interactive Mode[/]",
                border_style="green"
            ))
        else:
            print("\nCommands: quit, dry, history, browser URL, shodan X, cve ID, shot URL\n")

        while True:
            try:
                if HAS_RICH:
                    task = Prompt.ask(
                        f"\n  [bold green]NEXUS[/] "
                        f"[dim]({'DRY' if self.dry_run else 'LIVE'})[/]"
                    )
                else:
                    task = input(f"\n  NEXUS ({'DRY' if self.dry_run else 'LIVE'}) > ").strip()
            except (EOFError, KeyboardInterrupt):
                cprint("\n  [yellow]👋 NEXUS shutting down...[/]")
                break

            if not task:
                continue

            parts = task.split(maxsplit=1)
            cmd   = parts[0].lower()
            arg   = parts[1] if len(parts) > 1 else ""

            # Built-in commands
            if cmd in ("quit", "exit", "q"):
                cprint("  [yellow]👋 NEXUS shutting down...[/]")
                break
            elif cmd == "dry":
                self.dry_run = not self.dry_run
                cprint(f"  [cyan]⚙️  Dry-run: {'ON' if self.dry_run else 'OFF'}[/]")
            elif cmd == "history":
                self._show_history()
            elif cmd == "browser":
                self.open_browser(arg or "https://google.com")
            elif cmd == "shodan":
                self.open_browser(arg, mode="shodan")
            elif cmd == "cve":
                self.open_browser(arg, mode="cve")
            elif cmd == "shot":
                r = self.screenshot_wsl(arg)
                cprint(f"  [green]✅ Screenshot: {r['screenshot']}[/]" if r["success"]
                       else f"  [red]❌ {r['stderr']}[/]")
            elif cmd == "exploit-db":
                self.open_browser(arg, mode="exploit-db")
            elif cmd == "vt":
                self.open_browser(arg, mode="virustotal")
            elif cmd == "whois":
                self.open_browser(arg, mode="whois")
            else:
                # Normal task → NEXUS AI
                result = self.run_task(task, auto_execute=True)
                self.history.append({
                    "task"       : task,
                    "executions" : len(result["executions"]),
                    "timestamp"  : time.strftime("%H:%M:%S"),
                })

    def _show_history(self):
        if not self.history:
            cprint("  [dim]Belum ada history.[/]")
            return
        if HAS_RICH:
            t = Table(title="Task History", box=box.SIMPLE, border_style="dim")
            t.add_column("#",    style="dim", width=4)
            t.add_column("Time", style="cyan", width=10)
            t.add_column("Task", style="white")
            t.add_column("Cmds", style="green", width=6)
            for i, h in enumerate(self.history[-10:], 1):
                t.add_row(str(i), h["timestamp"], h["task"][:60], str(h["executions"]))
            console.print(t)
        else:
            for i, h in enumerate(self.history[-10:], 1):
                print(f"  {i}. [{h['timestamp']}] {h['task'][:60]}")


def main():
    parser = argparse.ArgumentParser(description="NEXUS Autonomous Security Agent")
    parser.add_argument("--model",        default=DEFAULT_MODEL, help="Path ke LoRA adapter")
    parser.add_argument("--task",         default=None,          help="Single task mode")
    parser.add_argument("--dry-run",      action="store_true",   help="No execution, parse only")
    parser.add_argument("--no-dashboard", action="store_true",   help="Skip SOC dashboard")
    args = parser.parse_args()

    # Install rich jika belum ada
    if not HAS_RICH:
        print("  Installing rich untuk tampilan lebih bagus...")
        subprocess.run([sys.executable, "-m", "pip", "install", "rich", "-q"])
        print("  Restart script untuk aktifkan rich UI.")

    agent = NEXUSAgent(
        model_path=args.model,
        dry_run=args.dry_run,
        dashboard=not args.no_dashboard,
    )

    if args.task:
        result = agent.run_task(args.task, auto_execute=not args.dry_run)
        n = len(result["executions"])
        cprint(f"\n  [green]✅ Task selesai. {n} commands executed.[/]")
    else:
        agent.interactive()


if __name__ == "__main__":
    main()
