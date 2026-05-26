"""
NEXUS — Workflow Executor
Orchestrate multi-step security workflows.
Import tool_executor via absolute package path (works from any cwd).
"""

import time
from pathlib import Path

from shared.utils import get_logger, root, append_jsonl
from runtime.tool_executor import executor   # absolute import — always works

logger      = get_logger("nexus.workflow")
WFLOW_LOG   = root("logs", "runtime", "workflows.jsonl")
OUTPUT_BASE = root("runtime", "output")

# ── Timeouts per tool category (seconds) ─────────────────────────────────────
DEFAULT_TIMEOUT = 120
TOOL_TIMEOUTS   = {
    "subfinder":120,"dnsx":60,"httpx":90,"nmap":300,"masscan":120,
    "nuclei":300,"gobuster":120,"nikto":180,"whatweb":30,"ffuf":120,
}

# ── Wordlist paths (WSL paths — Linux context) ────────────────────────────────
WORDLISTS = {
    "common"  : "/usr/share/wordlists/dirb/common.txt",
    "medium"  : "/usr/share/wordlists/dirb/common.txt",
    "rockyou" : "/usr/share/wordlists/rockyou.txt",
    "dns"     : "/usr/share/wordlists/dnsmap.txt",
}


class WorkflowExecutor:
    def __init__(self):
        self.on_step_done = None     # optional UI callback

    # ── Recon workflow ────────────────────────────────────────────────────────

    def recon(self, domain: str, out_dir: str | None = None) -> dict:
        out = Path(out_dir) if out_dir else OUTPUT_BASE / f"recon_{domain}"
        out.mkdir(parents=True, exist_ok=True)

        self._header("RECON WORKFLOW", domain)
        steps = [
            {"name":"subdomain_enum", "tool":"subfinder",
             "args":["-d",domain,"-silent","-o",str(out/"subdomains.txt")]},
            {"name":"dns_resolution", "tool":"dnsx",
             "args":["-l",str(out/"subdomains.txt"),"-silent","-o",str(out/"resolved.txt")]},
            {"name":"http_probe",     "tool":"httpx",
             "args":["-l",str(out/"resolved.txt"),"-silent","-o",str(out/"live_hosts.txt")]},
            {"name":"port_scan",      "tool":"nmap",
             "args":["-iL",str(out/"resolved.txt"),"-T4","--open","-oN",str(out/"ports.txt")]},
            {"name":"vuln_scan",      "tool":"nuclei",
             "args":["-l",str(out/"live_hosts.txt"),"-severity","medium,high,critical",
                     "-silent","-o",str(out/"vulns.txt")]},
        ]
        return self._run(steps)

    # ── Web workflow ──────────────────────────────────────────────────────────

    def web_assessment(self, url: str, out_dir: str | None = None) -> dict:
        out = Path(out_dir) if out_dir else OUTPUT_BASE / "web"
        out.mkdir(parents=True, exist_ok=True)

        self._header("WEB ASSESSMENT WORKFLOW", url)
        steps = [
            {"name":"dir_enum",       "tool":"gobuster",
             "args":["dir","-u",url,"-w",WORDLISTS["common"],
                     "-o",str(out/"dirs.txt"),"-q"]},
            {"name":"tech_fp",        "tool":"whatweb",
             "args":[url,"--log-json",str(out/"tech.json")]},
            {"name":"vuln_scan",      "tool":"nikto",
             "args":["-h",url,"-o",str(out/"nikto.txt"),"-Format","txt"]},
        ]
        return self._run(steps)

    # ── Internal runner ───────────────────────────────────────────────────────

    def _run(self, steps: list) -> dict:
        result = {"steps":[], "start":time.time()}
        for step in steps:
            t = step["tool"]
            print(f"  [►] {step['name']} ({t})...")
            r = executor.execute(t, step["args"],
                                 timeout=TOOL_TIMEOUTS.get(t, DEFAULT_TIMEOUT))
            sr = {"name":step["name"],"tool":t,
                  "success":r["success"],"duration":r["duration"]}
            # Count output lines without race condition
            out_arg_idx = next((i+1 for i,a in enumerate(step["args"]) if a=="-o"), None)
            if out_arg_idx and r["success"]:
                try:
                    f = Path(step["args"][out_arg_idx])
                    sr["output_count"] = len(f.read_text(encoding="utf-8",errors="ignore").splitlines())
                except OSError:
                    pass
            icon = "✓" if r["success"] else "✗"
            cnt  = f"  {sr.get('output_count','')} results" if sr.get("output_count") else ""
            print(f"  [{icon}] {t}{cnt}  ({r['duration']}s)")
            result["steps"].append(sr)
            if self.on_step_done:
                self.on_step_done(sr)

        result["duration"] = round(time.time()-result["start"],2)
        result["success"]  = all(s["success"] for s in result["steps"])
        append_jsonl(WFLOW_LOG, result)
        self._summary(result)
        return result

    @staticmethod
    def _header(title: str, target: str):
        print(f"\n  {'═'*52}\n  {title}\n  Target : {target}\n  {'═'*52}\n")

    @staticmethod
    def _summary(r: dict):
        ok = sum(1 for s in r["steps"] if s["success"])
        print(f"\n  {ok}/{len(r['steps'])} steps ok  |  {r['duration']}s total\n")


workflow = WorkflowExecutor()
