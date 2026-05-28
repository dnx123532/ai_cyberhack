#!/usr/bin/env python3
"""
NEXUS Client v2 — CyberHackSecurity Autonomous Agent
Connect ke Colab API brain + WSL Kali execution + SOC Dashboard + Forge mode

Usage:
    python nexus_client.py
    python nexus_client.py --api https://xxxx.ngrok-free.app
    python nexus_client.py --no-dashboard
"""

import os
import sys
import json
import time
import re
import threading
import subprocess
import requests
import webbrowser
import argparse
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse

# ─── Rich imports ────────────────────────────────────────────────────────────
from rich.console import Console
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.markdown import Markdown
from rich.spinner import Spinner
from rich.columns import Columns
from rich.rule import Rule
from rich import box
from rich.syntax import Syntax

# ─── Paths ────────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).parent
CONFIG_FILE = ROOT / "nexus_config.json"
SESSIONS_DIR = ROOT / "sessions"
FORGE_DIR   = ROOT / "forge"
UI_DIR      = ROOT / "ui"

for d in [SESSIONS_DIR, FORGE_DIR]:
    d.mkdir(exist_ok=True)

# ─── WSL tools ────────────────────────────────────────────────────────────────
WSL_EXE    = r"C:\Windows\System32\wsl.exe"
WSL_DISTRO = "kali-linux"

SAFE_TOOLS = {
    # Network recon
    "nmap", "masscan", "rustscan", "zmap", "unicornscan",
    "subfinder", "amass", "dnsx", "httpx", "httprobe",
    "nikto", "gobuster", "ffuf", "feroxbuster", "dirsearch",
    "whatweb", "wpscan", "nuclei", "wapiti", "skipfish",
    "theHarvester", "recon-ng", "shodan", "censys", "maltego",
    "dnsenum", "dnsrecon", "fierce", "sublist3r", "assetfinder",
    "waybackurls", "gau", "katana", "hakrawler", "gospider",
    "gowitness", "aquatone", "eyewitness",
    # Web tools
    "sqlmap", "xsstrike", "dalfox", "arjun", "wfuzz",
    "burpsuite", "zaproxy",
    # Exploitation / Post
    "hydra", "hashcat", "john", "medusa", "kerbrute",
    "crackmapexec", "cme", "bloodhound-python",
    "impacket-GetUserSPNs", "impacket-secretsdump",
    "impacket-psexec", "impacket-wmiexec", "impacket-smbclient",
    "evil-winrm", "netexec",
    # Recon extras
    "subfinder", "amass", "assetfinder", "findomain",
    "waybackurls", "waybackhack", "gau", "gauplus", "katana",
    "hakrawler", "gospider", "photon", "sublist3r",
    "sherlock", "crosslinked", "holehe", "maigret",
    "httpx", "httprobe", "dnsx", "massdns",
    # Wireless
    "aircrack-ng", "airodump-ng", "aireplay-ng", "airmon-ng",
    "kismet", "wifite", "hcxpcapngtool", "hcxdumptool",
    # Cloud
    "prowler", "scoutsuite", "pacu", "cloudsploit",
    # Forensics / Defense
    "volatility3", "vol.py", "autopsy", "strings", "binwalk",
    "yara", "zeek", "sigma", "suricata", "snort",
    "tshark", "wireshark", "tcpdump", "chainsaw",
    # Malware
    "ghidra", "cuckoo", "gophish", "maltrail",
    # System utils
    "python3", "python", "python2",
    "bash", "sh", "zsh",
    "cat", "ls", "grep", "find", "awk", "sed", "sort", "uniq",
    "curl", "wget", "ping", "whois", "dig", "host", "nslookup",
    "ssh", "scp", "nc", "netcat", "ncat",
    "sqlite3", "pip", "pip3", "apt", "apt-get", "git",
    "tar", "unzip", "zip", "gunzip", "gzip",
    "chmod", "chown", "mkdir", "rm", "cp", "mv",
    "echo", "printf", "tee", "head", "tail", "wc",
    "ps", "top", "kill", "pkill", "id", "whoami", "uname",
    "ifconfig", "ip", "route", "iptables", "ss", "netstat",
}

CONFIRM_TOOLS = {
    "msfconsole", "metasploit", "mimikatz",
    "evilginx2", "setoolkit", "routersploit",
}

console = Console()

# ─── Tool Registry ────────────────────────────────────────────────────────────
TOOL_REGISTRY_FILE = ROOT / "tool_registry" / "registry.json"

def win_path_to_wsl(path: str) -> str:
    """Convert E:\foo\bar → /mnt/e/foo/bar"""
    import re as _re
    def _conv(m):
        return f"/mnt/{m.group(1).lower()}/{m.group(2).replace(chr(92), '/')}"
    return _re.sub(r"([A-Za-z]):\\([\w\\.\-/]+)", _conv, path)


def load_tool_registry() -> str:
    """Load tool registry dan format WSL paths untuk system prompt NEXUS."""
    try:
        with open(TOOL_REGISTRY_FILE) as f:
            tools = json.load(f)
        lines = ["=== TOOLS LOKAL (GUNAKAN PATH INI — JANGAN UBAH) ==="]
        cats = {}
        for t in tools:
            cat = t.get("category", "misc")
            cats.setdefault(cat, []).append(t)
        for cat, items in sorted(cats.items()):
            lines.append(f"\n[{cat.upper()}]")
            for t in items:
                name  = t.get("tool", "?")
                exc   = win_path_to_wsl(t.get("exec", name))
                usage = t.get("usage", "--help")
                lines.append(f"  {name}: {exc} {usage}")
        lines.append("\n=== RULES ===")
        lines.append("- SELALU gunakan path di atas untuk tools lokal")
        lines.append("- Jangan gunakan Windows path (E:\\...), gunakan /mnt/e/...")
        lines.append("- Kasih command dalam ```bash block")
        lines.append("- Tools system (nmap, gobuster, ffuf) langsung tanpa path")
        return "\n".join(lines)
    except Exception:
        return ""

TOOL_CONTEXT = load_tool_registry()

# ─── Config ───────────────────────────────────────────────────────────────────
DEFAULT_CONFIG = {
    "api_url": "",
    "wsl_enabled": True,
    "auto_execute": False,
    "dashboard_port": 7788,
    "max_context": 10,
    "wsl_distro": "kali-linux",
}


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                cfg = json.load(f)
            return {**DEFAULT_CONFIG, **cfg}
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(cfg: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


# ─── API Client ───────────────────────────────────────────────────────────────
class NexusAPI:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.connected = False
        self.latency_ms = 0

    def test(self) -> bool:
        """Test connectivity to Colab API."""
        try:
            t0 = time.time()
            r = requests.get(
                f"{self.base_url}/health",
                timeout=10,
            )
            self.latency_ms = int((time.time() - t0) * 1000)
            self.connected = r.status_code == 200
        except Exception:
            self.connected = False
        return self.connected

    def ask(self, prompt: str, context: list) -> str:
        """Send prompt to Colab API, get response."""
        try:
            r = requests.post(
                f"{self.base_url}/ask",
                json={"prompt": prompt, "context": context, "tools": TOOL_CONTEXT},
                timeout=120,
            )
            if r.status_code == 200:
                data = r.json()
                return data.get("response", data.get("text", str(data)))
            return f"[API Error {r.status_code}] {r.text[:200]}"
        except requests.Timeout:
            return "[Error] API timeout (60s) — Colab masih loading?"
        except requests.ConnectionError:
            return "[Error] Tidak bisa connect ke API. Cek URL dan ngrok tunnel."
        except Exception as e:
            return f"[Error] {e}"

    def generate_code(self, description: str) -> str:
        """Ask NEXUS to generate a Python tool."""
        prompt = (
            f"Buatkan Python script untuk: {description}\n"
            "Output HANYA berupa kode Python yang siap dijalankan, "
            "mulai dari #!/usr/bin/env python3. "
            "Sertakan argparse, logging, dan error handling yang proper."
        )
        return self.ask(prompt, [])


# ─── WSL Executor ─────────────────────────────────────────────────────────────
class WSLExecutor:
    def __init__(self, distro: str = WSL_DISTRO):
        self.distro = distro
        self.available = self._check_wsl()

    def _check_wsl(self) -> bool:
        try:
            r = subprocess.run(
                [WSL_EXE, "--list", "--quiet"],
                capture_output=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            # Decode UTF-16 LE (Windows WSL output) + strip null bytes
            try:
                out = r.stdout.decode("utf-16-le", errors="ignore")
            except Exception:
                out = r.stdout.decode("utf-8", errors="ignore")
            # Remove spaces between chars (WSL --list quirk)
            out_clean = out.replace("\x00", "").replace(" ", "").lower()
            distro_clean = self.distro.replace(" ", "").replace("-", "").lower()
            return (
                self.distro.lower().replace(" ", "") in out_clean
                or distro_clean in out_clean
                or "kali" in out_clean
            )
        except Exception:
            return False

    def run(self, cmd: str, on_line=None, timeout: int = 120) -> tuple[int, str]:
        """Run command in WSL, stream output via on_line callback."""
        full_cmd = [WSL_EXE, "-d", self.distro, "-u", "root", "--", "bash", "-c", cmd]
        output_lines = []
        try:
            proc = subprocess.Popen(
                full_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            deadline = time.time() + timeout
            for line in proc.stdout:
                line = line.rstrip()
                output_lines.append(line)
                if on_line:
                    on_line(line)
                if time.time() > deadline:
                    proc.kill()
                    break
            proc.wait()
            return proc.returncode, "\n".join(output_lines)
        except FileNotFoundError:
            msg = f"WSL not found: {WSL_EXE}"
            if on_line:
                on_line(msg)
            return -1, msg
        except Exception as e:
            if on_line:
                on_line(str(e))
            return -1, str(e)

    def is_safe(self, cmd: str) -> tuple[bool, bool]:
        """Returns (is_allowed, needs_confirm)."""
        tokens = cmd.strip().split()
        if not tokens:
            return True, False
        tool = Path(tokens[0]).name  # handle /usr/bin/nmap → nmap

        # Dangerous flags override
        dangerous_flags = ["--os-shell", "--os-cmd", "--file-write", "--file-read"]
        if tool == "sqlmap" and any(f in cmd for f in dangerous_flags):
            return True, True

        # Allow semua python3 calls ke local repo paths
        if tool in ("python3", "python") and "/mnt/e/agent_cyberhack/" in cmd:
            return True, False

        # Allow bash/sh scripts dari local repo
        if tool in ("bash", "sh") and "/mnt/e/agent_cyberhack/" in cmd:
            return True, False

        # Allow cat >> (forge file creation)
        if tool == "cat" and ">>" in cmd:
            return True, False

        if tool in SAFE_TOOLS:
            return True, False
        if tool in CONFIRM_TOOLS:
            return True, True
        # sudo + safe tool is ok
        if tool == "sudo" and len(tokens) > 1 and tokens[1] in SAFE_TOOLS:
            return True, False
        # python3/bash general — confirm dulu
        if tool in ("python3", "python", "bash", "sh"):
            return True, True
        return False, False


# ─── Command starters ─────────────────────────────────────────────────────────
_CMD_STARTERS = (
    "nmap","masscan","rustscan","subfinder","amass","dnsx","httpx",
    "nikto","gobuster","ffuf","feroxbuster","dirsearch","nuclei","whatweb",
    "wpscan","sqlmap","xsstrike","dalfox","arjun","wfuzz","hydra","hashcat",
    "john","medusa","Medusa","patator","crackmapexec","cme","bloodhound","impacket","kerbrute",
    "aircrack","airodump","aireplay","airmon","wifite","hcxpcapngtool",
    "prowler","pacu","volatility","vol.py","yara","zeek","sigma","chainsaw",
    "python3","python","python2","bash","sh","perl","ruby","node",
    "curl","wget","nc","netcat","ncat","ssh","scp",
    "cat","ls","grep","find","awk","sed","sort","uniq","echo","printf",
    "chmod","mkdir","cp","mv","rm","tar","unzip","zip","git","pip","pip3",
    "apt","apt-get","sudo","tee","head","tail","wc","ps","kill",
)

def _is_new_cmd(line: str) -> bool:
    """True jika baris ini adalah awal command baru (bukan lanjutan)."""
    if not line.split():
        return False
    first = line.split()[0].lstrip("./")
    # Handle /mnt/e/.../tool.py — ambil nama file saja
    if "/" in first:
        first = first.split("/")[-1]
    # Handle python3 /path/to/tool.py — cek arg pertama juga
    first_lower = first.lower().replace(".py", "").replace(".sh", "")
    # Kalau dimulai dengan python3/bash + path = new command
    if first_lower in ("python3", "python", "bash", "sh", "perl", "ruby"):
        return True
    return any(first_lower == s or first_lower.startswith(s) for s in _CMD_STARTERS)

# ─── Path Normalizer ──────────────────────────────────────────────────────────
def normalize_wsl_path(cmd: str) -> str:
    """Convert Windows backslash paths ke WSL paths. Jangan sentuh URLs."""
    def win_to_wsl(m):
        drive = m.group(1).lower()
        rest  = m.group(2).replace("\\", "/")
        return f"/mnt/{drive}/{rest}"
    # Hanya convert Windows path dengan backslash: E:\foo\bar
    cmd = re.sub(r"(?<![:/])([A-Za-z]):\\([\w\\./\-]+)", win_to_wsl, cmd)
    return cmd


# ─── Command Parser ────────────────────────────────────────────────────────────
def parse_commands(text: str) -> list[str]:
    """Extract bash commands dari NEXUS response."""
    cmds = []

    for block in re.findall(r"```(?:bash|shell|sh|console)?\n(.*?)```", text, re.DOTALL):
        # Join explicit line continuations (\)
        block = re.sub(r"\\\n\s*", " ", block)
        lines = [l.strip() for l in block.split("\n")]

        # Detect kalau ada multi-line construct (while/for/if/do/case)
        MULTILINE_KEYWORDS = ("while ", "for ", "if ", "case ", "until ", "function ")
        block_has_multiline = any(
            any(l.startswith(kw) for kw in MULTILINE_KEYWORDS)
            for l in lines if l and not l.startswith("#")
        )

        if block_has_multiline:
            # Treat seluruh block sebagai satu command
            clean_lines = []
            skip_heredoc = False
            for l in lines:
                if skip_heredoc:
                    if l.strip() in ("PYEOF","EOF","END","'PYEOF'","'EOF'"):
                        skip_heredoc = False
                    continue
                if "<<" in l and ("EOF" in l or "PYEOF" in l):
                    skip_heredoc = True
                    continue
                if l and not l.startswith("#"):
                    clean_lines.append(l)
            if clean_lines:
                full_cmd = "; ".join(clean_lines)
                cmds.append(normalize_wsl_path(full_cmd))
            continue

        current = ""
        skip_heredoc = False
        for line in lines:
            if skip_heredoc:
                if line.strip() in ("PYEOF","EOF","END","'PYEOF'","'EOF'"):
                    skip_heredoc = False
                continue
            if not line or line.startswith("#"):
                continue
            if "<<" in line and ("EOF" in line or "PYEOF" in line or "END" in line):
                skip_heredoc = True
                continue
            if current and _is_new_cmd(line):
                cmds.append(normalize_wsl_path(current.strip()))
                current = line
            elif current:
                current += " " + line
            else:
                current = line

        if current:
            cmds.append(normalize_wsl_path(current.strip()))

    # $ cmd lines fallback
    if not cmds:
        for line in text.split("\n"):
            m = re.match(r"^\$\s+(.+)", line.strip())
            if m:
                cmds.append(normalize_wsl_path(m.group(1).strip()))

    return cmds


# ─── SOC Dashboard Server ─────────────────────────────────────────────────────
class DashboardState:
    def __init__(self):
        self.lock = threading.Lock()
        self.online = True
        self.executions: list[dict] = []
        self.findings: list[dict] = []
        self.output_buffer: list[str] = []
        self.metrics = {"success": 0, "failed": 0, "total": 0, "duration_s": 0}

    def add_output(self, line: str):
        with self.lock:
            self.output_buffer.append(line)
            if len(self.output_buffer) > 500:
                self.output_buffer.pop(0)

    def add_execution(self, tool: str, duration_s: float, exit_code: int):
        with self.lock:
            self.executions.insert(0, {
                "tool": tool, "duration_s": round(duration_s, 1),
                "exit_code": exit_code,
                "time": datetime.now().strftime("%H:%M:%S"),
            })
            self.executions = self.executions[:20]
            self.metrics["total"] += 1
            self.metrics["duration_s"] += duration_s
            if exit_code == 0:
                self.metrics["success"] += 1
            else:
                self.metrics["failed"] += 1

    def add_finding(self, severity: str, desc: str, tool: str):
        with self.lock:
            self.findings.insert(0, {
                "severity": severity, "desc": desc, "tool": tool,
                "time": datetime.now().strftime("%H:%M:%S"),
            })
            self.findings = self.findings[:50]

    def to_json(self) -> dict:
        with self.lock:
            return {
                "online": self.online,
                "metrics": self.metrics,
                "executions": self.executions[:10],
                "findings": self.findings[:20],
                "output": self.output_buffer[-50:],
            }


DASHBOARD = DashboardState()


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(UI_DIR), **kwargs)

    def do_GET(self):
        if self.path == "/api/status":
            data = json.dumps(DASHBOARD.to_json()).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif self.path == "/api/stream":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            try:
                last = 0
                while True:
                    with DASHBOARD.lock:
                        buf = DASHBOARD.output_buffer
                    if len(buf) > last:
                        for line in buf[last:]:
                            data = f"data: {json.dumps(line)}\n\n"
                            self.wfile.write(data.encode())
                        self.wfile.flush()
                        last = len(buf)
                    time.sleep(0.5)
            except Exception:
                pass
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == "/api/finding":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            DASHBOARD.add_finding(
                body.get("severity", "info"),
                body.get("desc", ""),
                body.get("tool", ""),
            )
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *_):
        pass  # Silence HTTP logs


def start_dashboard_server(port: int):
    if not UI_DIR.exists():
        return
    try:
        server = HTTPServer(("127.0.0.1", port), DashboardHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        return server
    except OSError:
        return None


# ─── Forge Mode ───────────────────────────────────────────────────────────────
class ForgeMode:
    def __init__(self, api: "NexusAPI", executor: WSLExecutor):
        self.api = api
        self.executor = executor

    def run(self, description: str) -> Path | None:
        console.print(f"\n[cyan]⬡ FORGE MODE[/] — Generating tool: [yellow]{description}[/]\n")

        with console.status("[cyan]NEXUS writing your tool...[/]", spinner="dots"):
            code = self.api.generate_code(description)

        # Extract just the code block if response has extra text
        code_match = re.search(r"```(?:python)?\n(.*?)```", code, re.DOTALL)
        if code_match:
            code = code_match.group(1)

        # Clean shebang if duplicated
        if code.count("#!/usr/bin/env python3") > 1:
            parts = code.split("#!/usr/bin/env python3")
            code = "#!/usr/bin/env python3" + parts[-1]

        # Show the code
        console.print(Panel(
            Syntax(code, "python", theme="monokai", line_numbers=True),
            title="[cyan]Generated Tool[/]",
            border_style="cyan",
        ))

        # Save
        slug = re.sub(r"[^a-z0-9_]", "_", description.lower())[:40]
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = FORGE_DIR / f"tool_{slug}_{ts}.py"
        path.write_text(code, encoding="utf-8")
        console.print(f"\n[green]✓ Saved:[/] {path}\n")

        if Confirm.ask("[yellow]Execute in WSL?[/]", default=False):
            def show(line):
                console.print(f"  [dim]{line}[/]")
            rc, _ = self.executor.run(f"python3 {path}", on_line=show)
            status = "[green]✓ Done[/]" if rc == 0 else f"[red]✗ Exit {rc}[/]"
            console.print(f"\n{status}\n")

        return path


# ─── Main Agent ───────────────────────────────────────────────────────────────
class NexusAgent:
    def __init__(self, cfg: dict):
        self.cfg     = cfg
        self.api     = NexusAPI(cfg.get("api_url", ""))
        self.wsl     = WSLExecutor(cfg.get("wsl_distro", WSL_DISTRO))
        self.forge   = ForgeMode(self.api, self.wsl)
        self.context: list[dict] = []          # last N exchanges
        self.session_start = datetime.now()
        self._dashboard_server = None

    # ── UI helpers ────────────────────────────────────────────────────────────

    def _header(self):
        ts = datetime.now().strftime("%H:%M:%S")
        api_status = (
            f"[green]● API ONLINE[/] [dim]{self.api.base_url}[/]  [cyan]{self.api.latency_ms}ms[/]"
            if self.api.connected else
            "[red]● API OFFLINE[/]"
        )
        wsl_status = (
            f"[green]● WSL {self.wsl.distro}[/]"
            if self.wsl.available else
            "[red]● WSL N/A[/]"
        )
        console.rule(
            f"[bold cyan]⬡ NEXUS[/] [dim]CyberHackSecurity[/]  "
            f"{api_status}  {wsl_status}  [dim]{ts}[/]",
            style="cyan dim",
        )

    def _print_response(self, text: str):
        """Pretty-print NEXUS response with syntax highlighting."""
        # Split on code blocks and render each part
        parts = re.split(r"(```[\s\S]*?```)", text)
        for part in parts:
            if part.startswith("```"):
                m = re.match(r"```(\w+)?\n([\s\S]*?)```", part)
                if m:
                    lang = m.group(1) or "text"
                    code = m.group(2)
                    console.print(Syntax(code, lang, theme="monokai", line_numbers=False))
                else:
                    console.print(part)
            else:
                if part.strip():
                    console.print(Markdown(part))

    def _add_context(self, role: str, content: str):
        self.context.append({"role": role, "content": content})
        max_ctx = self.cfg.get("max_context", 10)
        if len(self.context) > max_ctx * 2:
            self.context = self.context[-(max_ctx * 2):]

    # ── Commands ──────────────────────────────────────────────────────────────

    def cmd_help(self):
        table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        table.add_column("cmd", style="cyan", no_wrap=True)
        table.add_column("desc", style="dim")
        cmds = [
            ("/help",         "Tampilkan perintah ini"),
            ("/api <url>",    "Set Colab API URL"),
            ("/status",       "Cek connection status"),
            ("/exec <cmd>",   "Jalankan perintah WSL manual"),
            ("/forge <desc>", "NEXUS generate + run custom tool"),
            ("/clear",        "Clear chat history"),
            ("/save",         "Save session ke JSON"),
            ("/load <file>",  "Load session sebelumnya"),
            ("/dashboard",    "Buka SOC Dashboard di browser"),
            ("/exit",         "Keluar"),
        ]
        for c, d in cmds:
            table.add_row(c, d)
        console.print(Panel(table, title="[cyan]NEXUS Commands[/]", border_style="cyan dim"))

    def cmd_status(self):
        table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        table.add_column("key", style="dim", no_wrap=True)
        table.add_column("val")

        with console.status("Testing API..."):
            ok = self.api.test() if self.api.base_url else False

        table.add_row("API URL", self.api.base_url or "[dim]not set[/]")
        table.add_row("API Status", "[green]ONLINE[/]" if ok else "[red]OFFLINE[/]")
        table.add_row("Latency", f"{self.api.latency_ms}ms" if ok else "—")
        table.add_row("WSL", f"[green]{self.wsl.distro}[/]" if self.wsl.available else "[red]Not available[/]")
        table.add_row("Auto-execute", "ON" if self.cfg.get("auto_execute") else "OFF")
        table.add_row("Context turns", str(len(self.context) // 2))
        console.print(Panel(table, title="[cyan]Status[/]", border_style="cyan dim"))

    def cmd_set_api(self, url: str):
        self.api.base_url = url.rstrip("/")
        self.cfg["api_url"] = self.api.base_url
        save_config(self.cfg)
        with console.status("Testing connection..."):
            ok = self.api.test()
        if ok:
            console.print(f"[green]✓ Connected![/] Latency: {self.api.latency_ms}ms")
        else:
            console.print("[red]✗ Could not connect.[/] URL disimpan, coba lagi nanti.")

    def cmd_exec(self, cmd: str):
        if not self.wsl.available:
            console.print("[red]WSL tidak tersedia.[/]")
            return

        allowed, needs_confirm = self.wsl.is_safe(cmd)
        if not allowed:
            console.print(f"[red]⚠ Tool tidak ada di whitelist.[/] Tambah manual atau pakai /forge.")
            return
        if needs_confirm:
            if not Confirm.ask(f"[yellow]⚠ Confirm execute:[/] {cmd}", default=False):
                return

        console.print(f"\n[cyan]▶[/] [dim]{cmd}[/]")
        t0 = time.time()

        def show(line):
            console.print(f"  {line}")
            DASHBOARD.add_output(line)

        rc, _ = self.wsl.run(cmd, on_line=show, timeout=300)
        dur = time.time() - t0
        DASHBOARD.add_execution(cmd.split()[0], dur, rc)
        status = f"[green]✓ Done[/] ({dur:.1f}s)" if rc == 0 else f"[red]✗ Exit {rc}[/]"
        console.print(f"\n{status}\n")

    def cmd_save(self):
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = SESSIONS_DIR / f"session_{ts}.json"
        data = {
            "timestamp": ts,
            "api_url": self.api.base_url,
            "context": self.context,
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        console.print(f"[green]✓ Saved:[/] {path}")

    def cmd_load(self, filename: str):
        path = SESSIONS_DIR / filename if not Path(filename).is_absolute() else Path(filename)
        if not path.exists():
            console.print(f"[red]File not found:[/] {path}")
            return
        with open(path) as f:
            data = json.load(f)
        self.context = data.get("context", [])
        console.print(f"[green]✓ Loaded:[/] {len(self.context)//2} turns dari {path.name}")

    def cmd_dashboard(self):
        port = self.cfg.get("dashboard_port", 7788)
        url  = f"http://127.0.0.1:{port}"
        webbrowser.open(url)
        console.print(f"[cyan]Opening dashboard:[/] {url}")

    # ── Execute commands from response ────────────────────────────────────────

    def _fix_cmd(self, cmd: str) -> str:
        """Auto-fix known wrong paths sebelum execute."""
        # theHarvester → selalu pakai system tool (lebih reliable)
        if "theHarvester" in cmd and "/mnt/e/" in cmd:
            args = cmd.split(".py", 1)[-1].strip() if ".py" in cmd else ""
            cmd = f"theHarvester {args}".strip()
            return cmd

        # sqlmap → pakai path lokal yang benar
        if "sqlmap" in cmd and "/mnt/e/" in cmd:
            correct = "/mnt/e/agent_cyberhack/data/raw_datasets/tool_scripts/web/sqlmap/sqlmap.py"
            cmd = re.sub(r"/mnt/e/[^\s]*/sqlmap\.py", correct, cmd)

        # dirsearch → pakai path lokal yang benar
        if "dirsearch" in cmd and "/mnt/e/" in cmd:
            correct = "/mnt/e/agent_cyberhack/data/raw_datasets/tool_scripts/web/dirsearch/dirsearch.py"
            cmd = re.sub(r"/mnt/e/[^\s]*/dirsearch\.py", correct, cmd)

        # Sublist3r → path lokal yang benar
        if "sublist3r" in cmd.lower() and "/mnt/e/" in cmd:
            correct = "/mnt/e/agent_cyberhack/data/raw_datasets/tool_scripts/recon/Sublist3r/sublist3r.py"
            cmd = re.sub(r"/mnt/e/[^\s]*/sublist3r\.py", correct, cmd, flags=re.IGNORECASE)

        return cmd

    def _execute_response_cmds(self, response: str):
        cmds = parse_commands(response)
        if not cmds:
            return

        console.print(f"\n[cyan]⬡ Detected {len(cmds)} command(s)[/]")
        for c in cmds:
            console.print(f"  [dim]·[/] {c}")

        auto = self.cfg.get("auto_execute", False)
        if not auto:
            if not Confirm.ask("\nExecute in WSL?", default=False):
                return

        for cmd in cmds:
            cmd = self._fix_cmd(cmd)
            allowed, needs_confirm = self.wsl.is_safe(cmd)
            if not allowed:
                console.print(f"[yellow]⚠ Skipped (not in whitelist):[/] {cmd}")
                continue
            if needs_confirm and not Confirm.ask(f"[yellow]⚠ Confirm:[/] {cmd}", default=False):
                continue

            console.print(f"\n[cyan]▶[/] [dim]{cmd}[/]")
            t0 = time.time()

            def show(line, _cmd=cmd):
                try:
                    # Strip ANSI escape codes buat Rich safety
                    clean = re.sub(r'\x1b\[[0-9;]*[mGKHF]', '', line)
                    clean = re.sub(r'\x1b\[\?[0-9]+[hl]', '', clean)
                    print(f"  {clean}", flush=True)
                    DASHBOARD.add_output(clean)
                except Exception:
                    pass

            rc, output = self.wsl.run(cmd, on_line=show, timeout=300)
            dur = time.time() - t0
            DASHBOARD.add_execution(cmd.split()[0], dur, rc)

            if rc == 0:
                console.print(f"\n[green]✓ Done[/] ({dur:.1f}s)")
            else:
                console.print(f"\n[red]✗ Exit {rc}[/] ({dur:.1f}s)")

    # ── Think ─────────────────────────────────────────────────────────────────

    def think(self, user_input: str) -> str:
        if not self.api.base_url:
            return (
                "[bold red]API URL belum di-set![/]\n"
                "Jalankan: [cyan]/api https://xxxx.ngrok-free.app[/]\n"
                "Atau tambahkan di nexus_config.json"
            )

        self._add_context("user", user_input)
        with console.status("[cyan]NEXUS thinking...[/]", spinner="dots"):
            response = self.api.ask(user_input, self.context[:-1])

        self._add_context("assistant", response)
        return response

    # ── Setup wizard ──────────────────────────────────────────────────────────

    def setup_wizard(self):
        console.print("\n[bold cyan]⬡ NEXUS Setup[/]\n")
        if not self.api.base_url:
            console.print(
                "[yellow]API URL belum dikonfigurasi.[/]\n"
                "Masukkan URL ngrok dari Colab (atau tekan Enter untuk skip):"
            )
            url = Prompt.ask("[cyan]API URL[/]", default="")
            if url:
                self.cmd_set_api(url)
        elif not self.api.connected:
            console.print(f"[dim]Testing saved API: {self.api.base_url}[/]")
            self.api.test()

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self, launch_dashboard: bool = True):
        # ─── Banner ───────────────────────────────────────────────────────────
        console.print()
        console.print(Panel(
            "[bold cyan]  ⬡  NEXUS  ⬡[/]\n"
            "[dim]CyberHackSecurity Autonomous Agent[/]\n"
            "[dim]WSL Kali + Colab API + SOC Dashboard[/]",
            border_style="cyan",
            expand=False,
        ))
        console.print()

        # ─── Dashboard ────────────────────────────────────────────────────────
        if launch_dashboard and UI_DIR.exists():
            port = self.cfg.get("dashboard_port", 7788)
            self._dashboard_server = start_dashboard_server(port)
            if self._dashboard_server:
                console.print(f"[green]✓ SOC Dashboard:[/] http://127.0.0.1:{port}")
                time.sleep(0.5)
                webbrowser.open(f"http://127.0.0.1:{port}")

        # ─── Setup ────────────────────────────────────────────────────────────
        self.setup_wizard()

        # ─── Status line ──────────────────────────────────────────────────────
        console.print()
        self._header()
        console.print()
        console.print("[dim]Ketik pertanyaan atau /help untuk perintah. /exit untuk keluar.[/]\n")

        # ─── REPL ─────────────────────────────────────────────────────────────
        while True:
            try:
                user_input = Prompt.ask("[bold cyan]NEXUS >[/]").strip()
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Exiting... Bye bro! 👋[/]")
                break

            if not user_input:
                continue

            # ─ Built-in commands ──────────────────────────────────────────────
            if user_input.lower() in ("/exit", "/quit", "exit", "quit"):
                console.print("[dim]Bye bro! 👋[/]")
                break

            elif user_input.lower() in ("/help", "help"):
                self.cmd_help()

            elif user_input.lower() == "/status":
                self.cmd_status()

            elif user_input.lower().startswith("/api "):
                self.cmd_set_api(user_input[5:].strip())

            elif user_input.lower().startswith("/exec "):
                self.cmd_exec(user_input[6:].strip())

            elif user_input.lower().startswith("/forge "):
                desc = user_input[7:].strip()
                self.forge.run(desc)

            elif user_input.lower() == "/clear":
                self.context.clear()
                console.clear()
                self._header()
                console.print("[green]✓ Context cleared.[/]\n")

            elif user_input.lower() == "/save":
                self.cmd_save()

            elif user_input.lower().startswith("/load "):
                self.cmd_load(user_input[6:].strip())

            elif user_input.lower() in ("/dashboard", "/ui"):
                self.cmd_dashboard()

            elif user_input.startswith("/"):
                console.print(f"[red]Unknown command:[/] {user_input}  (ketik /help)")

            # ─ Normal chat → NEXUS ────────────────────────────────────────────
            else:
                response = self.think(user_input)
                console.print()
                console.print(Panel(
                    response,
                    title="[cyan]NEXUS[/]",
                    border_style="cyan dim",
                    padding=(1, 2),
                ))
                console.print()
                DASHBOARD.add_output(f"Q: {user_input[:80]}")
                DASHBOARD.add_output(f"A: {response[:120]}...")

                # Auto-detect and offer to execute commands
                if self.wsl.available:
                    self._execute_response_cmds(response)

        # ─── Cleanup ──────────────────────────────────────────────────────────
        if self._dashboard_server:
            self._dashboard_server.shutdown()


# ─── Entry point ──────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="NEXUS — CyberHackSecurity Autonomous Agent"
    )
    parser.add_argument("--api", help="Colab API URL (e.g. https://xxx.ngrok-free.app)")
    parser.add_argument("--no-dashboard", action="store_true", help="Skip SOC dashboard")
    parser.add_argument("--auto-exec", action="store_true", help="Auto-execute WSL commands without confirm")
    args = parser.parse_args()

    cfg = load_config()

    if args.api:
        cfg["api_url"] = args.api.rstrip("/")
        save_config(cfg)

    if args.auto_exec:
        cfg["auto_execute"] = True

    agent = NexusAgent(cfg)
    agent.run(launch_dashboard=not args.no_dashboard)


if __name__ == "__main__":
    main()
