"""
NEXUS — Browser Controller
Open browser untuk dashboard, reporting, dan web reconnaissance tasks.
Uses: webbrowser (built-in) + optional subprocess for specific browsers.
"""

import subprocess, webbrowser, time
from pathlib import Path

from shared.utils import get_logger, root, append_jsonl

logger      = get_logger("nexus.browser")
BROWSER_LOG = root("logs", "runtime", "browser.jsonl")

# Preferred browsers (checked in order)
BROWSERS = ["chrome", "chromium-browser", "firefox", "msedge"]


class BrowserController:
    """
    Control browser windows for NEXUS dashboards and web tools.
    """

    def __init__(self):
        self._opened: list[dict] = []

    # ── URL opening ───────────────────────────────────────────────────────────

    def open(self, url: str, label: str = "") -> bool:
        """Open URL in default browser."""
        try:
            webbrowser.open(url)
            record = {"url": url, "label": label, "ts": time.time(), "success": True}
            self._opened.append(record)
            append_jsonl(BROWSER_LOG, record)
            logger.info(f"Opened: {url}")
            return True
        except Exception as e:
            logger.error(f"Browser open failed: {e}")
            return False

    def open_dashboard(self, port: int = 8080, path: str = "/") -> bool:
        """Open local NEXUS dashboard."""
        url = f"http://localhost:{port}{path}"
        return self.open(url, label="nexus_dashboard")

    def open_report(self, report_path: str | Path) -> bool:
        """Open an HTML report file in browser."""
        p = Path(report_path).resolve()
        if not p.exists():
            logger.error(f"Report not found: {p}")
            return False
        return self.open(p.as_uri(), label="report")

    def open_chromium_headless(self, url: str, screenshot_path: str | None = None) -> dict:
        """
        Run Chromium headless via WSL for web screenshots / scraping.
        Requires: chromium-browser installed in WSL.
        """
        WSL = ["wsl", "-d", "kali-linux", "-u", "root", "--"]
        cmd = WSL + [
            "chromium-browser", "--headless", "--disable-gpu",
            "--no-sandbox", "--disable-dev-shm-usage",
        ]
        if screenshot_path:
            cmd += [f"--screenshot={screenshot_path}"]
        cmd += [url]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            record = {
                "url"       : url,
                "screenshot": screenshot_path,
                "success"   : result.returncode == 0,
                "stderr"    : result.stderr[:200],
            }
        except subprocess.TimeoutExpired:
            record = {"url": url, "success": False, "stderr": "timeout"}
        except FileNotFoundError:
            record = {"url": url, "success": False, "stderr": "WSL or chromium not found"}

        append_jsonl(BROWSER_LOG, record)
        return record

    # ── Web recon helpers ─────────────────────────────────────────────────────

    def open_target(self, target: str) -> bool:
        """Smart open: prepend https:// if no scheme."""
        if not target.startswith(("http://", "https://")):
            target = f"https://{target}"
        return self.open(target, label="recon_target")

    def open_shodan(self, query: str) -> bool:
        """Open Shodan search for a query."""
        import urllib.parse
        url = f"https://www.shodan.io/search?query={urllib.parse.quote(query)}"
        return self.open(url, label="shodan")

    def open_cve(self, cve_id: str) -> bool:
        """Open NVD page for a CVE."""
        url = f"https://nvd.nist.gov/vuln/detail/{cve_id}"
        return self.open(url, label="cve")

    def history(self) -> list[dict]:
        return list(self._opened)


# Singleton
browser = BrowserController()
