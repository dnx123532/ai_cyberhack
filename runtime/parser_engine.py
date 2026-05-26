"""
NEXUS — Parser Engine
Parse output dari berbagai security tools ke structured data.
Supports: nmap (XML/text), nuclei (JSON/text), gobuster, subfinder,
          httpx, nikto, whatweb, masscan, sqlmap, hashcat, ffuf.
"""

import re, json, xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from shared.utils import get_logger

logger = get_logger("nexus.parser")


# ─────────────────────────────────────────────────────────────────────────────
# Base
# ─────────────────────────────────────────────────────────────────────────────

class ParseResult:
    def __init__(self, tool: str, raw: str, data: list | dict,
                 count: int = 0, error: str = ""):
        self.tool  = tool
        self.raw   = raw
        self.data  = data
        self.count = count or (len(data) if isinstance(data, list) else 1)
        self.error = error

    def ok(self) -> bool:
        return not self.error

    def __repr__(self):
        return f"<ParseResult tool={self.tool} count={self.count} error={self.error!r}>"


# ─────────────────────────────────────────────────────────────────────────────
# Tool parsers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_nmap_xml(raw: str) -> ParseResult:
    """Parse nmap XML output (-oX or inline XML)."""
    try:
        root_el = ET.fromstring(raw)
    except ET.ParseError as e:
        return ParseResult("nmap", raw, [], error=str(e))

    hosts = []
    for host in root_el.findall("host"):
        status = host.find("status")
        if status is None or status.get("state") != "up":
            continue
        addr_el = host.find("address[@addrtype='ipv4']")
        ip = addr_el.get("addr", "") if addr_el is not None else ""

        ports = []
        for port in host.findall(".//port"):
            state  = port.find("state")
            svc    = port.find("service")
            portid = port.get("portid", "")
            proto  = port.get("protocol", "tcp")
            if state is not None and state.get("state") == "open":
                ports.append({
                    "port"   : int(portid),
                    "proto"  : proto,
                    "service": svc.get("name", "") if svc is not None else "",
                    "version": svc.get("version", "") if svc is not None else "",
                })
        if ip:
            hosts.append({"ip": ip, "ports": ports})

    return ParseResult("nmap", raw, hosts)


def _parse_nmap_text(raw: str) -> ParseResult:
    """Parse nmap plain-text output (-oN)."""
    hosts, current_ip, current_ports = [], None, []

    for line in raw.splitlines():
        line = line.strip()
        ip_match = re.match(r"Nmap scan report for (?:.+ \()?(\d+\.\d+\.\d+\.\d+)\)?", line)
        if ip_match:
            if current_ip:
                hosts.append({"ip": current_ip, "ports": current_ports})
            current_ip    = ip_match.group(1)
            current_ports = []
            continue

        port_match = re.match(r"(\d+)/(\w+)\s+open\s+(\S+)(?:\s+(.+))?", line)
        if port_match and current_ip:
            current_ports.append({
                "port"   : int(port_match.group(1)),
                "proto"  : port_match.group(2),
                "service": port_match.group(3),
                "version": port_match.group(4) or "",
            })

    if current_ip:
        hosts.append({"ip": current_ip, "ports": current_ports})

    return ParseResult("nmap", raw, hosts)


def _parse_nuclei(raw: str) -> ParseResult:
    """Parse nuclei output — JSON lines or plain text."""
    findings = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("{"):
            try:
                obj = json.loads(line)
                findings.append({
                    "template": obj.get("template-id", ""),
                    "name"    : obj.get("info", {}).get("name", ""),
                    "severity": obj.get("info", {}).get("severity", ""),
                    "host"    : obj.get("host", ""),
                    "url"     : obj.get("matched-at", ""),
                })
                continue
            except json.JSONDecodeError:
                pass
        # plain text: [severity] [template] url
        m = re.match(r"\[(\w+)\]\s+\[(.+?)\]\s+(.+)", line)
        if m:
            findings.append({
                "severity": m.group(1).lower(),
                "template": m.group(2),
                "url"     : m.group(3),
            })

    return ParseResult("nuclei", raw, findings)


def _parse_gobuster(raw: str) -> ParseResult:
    """Parse gobuster dir/vhost output."""
    paths = []
    for line in raw.splitlines():
        line = line.strip()
        m = re.match(r"(/\S*)\s+\(Status:\s+(\d+)\)", line)
        if m:
            paths.append({"path": m.group(1), "status": int(m.group(2))})
    return ParseResult("gobuster", raw, paths)


def _parse_subfinder(raw: str) -> ParseResult:
    """Parse subfinder output — one subdomain per line."""
    subs = [l.strip() for l in raw.splitlines() if l.strip() and not l.startswith("[")]
    return ParseResult("subfinder", raw, subs)


def _parse_httpx(raw: str) -> ParseResult:
    """Parse httpx output — JSON lines or plain URL list."""
    hosts = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("{"):
            try:
                obj = json.loads(line)
                hosts.append({
                    "url"         : obj.get("url", ""),
                    "status_code" : obj.get("status-code", 0),
                    "title"       : obj.get("title", ""),
                    "webserver"   : obj.get("webserver", ""),
                    "tech"        : obj.get("tech", []),
                })
                continue
            except json.JSONDecodeError:
                pass
        # plain URL
        if line.startswith("http"):
            hosts.append({"url": line})

    return ParseResult("httpx", raw, hosts)


def _parse_nikto(raw: str) -> ParseResult:
    """Parse nikto text output."""
    findings = []
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("+ ") and "OSVDB" not in line:
            findings.append({"finding": line[2:]})
        elif re.match(r"\+ OSVDB-\d+:", line):
            m = re.match(r"\+ (OSVDB-\d+): (.+)", line)
            if m:
                findings.append({"osvdb": m.group(1), "finding": m.group(2)})
    return ParseResult("nikto", raw, findings)


def _parse_whatweb(raw: str) -> ParseResult:
    """Parse whatweb JSON or text output."""
    tech = []
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                obj = json.loads(line)
                for target, data in obj.items():
                    plugins = data.get("plugins", {})
                    tech.append({"target": target, "tech": list(plugins.keys())})
                continue
            except json.JSONDecodeError:
                pass
        # plain text: URL [code] Tech1, Tech2
        m = re.match(r"(https?://\S+)\s+\[(\d+)\]\s+(.*)", line)
        if m:
            tech.append({
                "url"   : m.group(1),
                "status": int(m.group(2)),
                "tech"  : [t.strip() for t in m.group(3).split(",")],
            })
    return ParseResult("whatweb", raw, tech)


def _parse_masscan(raw: str) -> ParseResult:
    """Parse masscan output (text or JSON)."""
    results = []
    for line in raw.splitlines():
        line = line.strip()
        m = re.match(r"Discovered open port (\d+)/(\w+) on (\S+)", line)
        if m:
            results.append({
                "port" : int(m.group(1)),
                "proto": m.group(2),
                "ip"   : m.group(3),
            })
    return ParseResult("masscan", raw, results)


def _parse_ffuf(raw: str) -> ParseResult:
    """Parse ffuf JSON output or plain text."""
    results = []
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                obj = json.loads(line)
                if "results" in obj:
                    for r in obj["results"]:
                        results.append({
                            "url"   : r.get("url", ""),
                            "status": r.get("status", 0),
                            "length": r.get("length", 0),
                            "words" : r.get("words", 0),
                        })
                continue
            except json.JSONDecodeError:
                pass
        # plain: [Status: 200, Size: 1234, Words: 56] URL
        m = re.match(r"\[Status: (\d+),.*?\]\s+(https?\S+)", line)
        if m:
            results.append({"status": int(m.group(1)), "url": m.group(2)})
    return ParseResult("ffuf", raw, results)


def _parse_hashcat(raw: str) -> ParseResult:
    """Parse hashcat potfile or output: hash:password."""
    cracked = []
    for line in raw.splitlines():
        line = line.strip()
        if ":" in line and not line.startswith("#"):
            parts = line.split(":", 1)
            if len(parts) == 2:
                cracked.append({"hash": parts[0], "password": parts[1]})
    return ParseResult("hashcat", raw, cracked)


def _parse_sqlmap(raw: str) -> ParseResult:
    """Parse sqlmap key findings from its verbose output."""
    findings = []
    for line in raw.splitlines():
        line = line.strip()
        if any(kw in line for kw in (
            "injectable", "Parameter:", "Type:", "Title:", "Payload:",
            "available databases", "database management system"
        )):
            findings.append({"line": line})
    return ParseResult("sqlmap", raw, findings)


# ─────────────────────────────────────────────────────────────────────────────
# Router
# ─────────────────────────────────────────────────────────────────────────────

_PARSERS = {
    "nmap"      : lambda r: _parse_nmap_xml(r) if r.strip().startswith("<") else _parse_nmap_text(r),
    "nuclei"    : _parse_nuclei,
    "gobuster"  : _parse_gobuster,
    "subfinder" : _parse_subfinder,
    "dnsx"      : _parse_subfinder,    # same format: one host per line
    "httpx"     : _parse_httpx,
    "nikto"     : _parse_nikto,
    "whatweb"   : _parse_whatweb,
    "masscan"   : _parse_masscan,
    "ffuf"      : _parse_ffuf,
    "hashcat"   : _parse_hashcat,
    "sqlmap"    : _parse_sqlmap,
}


class ParserEngine:
    """Route raw tool output to the appropriate parser."""

    def parse(self, tool: str, raw: str) -> ParseResult:
        """Parse raw output for a given tool name."""
        if not raw or not raw.strip():
            return ParseResult(tool, raw, [], error="empty output")

        parser = _PARSERS.get(tool.lower())
        if not parser:
            # Generic: return non-empty lines
            lines = [l.strip() for l in raw.splitlines() if l.strip()]
            return ParseResult(tool, raw, lines)

        try:
            return parser(raw)
        except Exception as e:
            logger.warning(f"Parser error ({tool}): {e}")
            return ParseResult(tool, raw, [], error=str(e))

    def parse_file(self, tool: str, file_path: str | Path) -> ParseResult:
        """Read output file and parse it."""
        p = Path(file_path)
        if not p.exists():
            return ParseResult(tool, "", [], error=f"file not found: {p}")
        raw = p.read_text(encoding="utf-8", errors="ignore")
        return self.parse(tool, raw)

    def supported_tools(self) -> list[str]:
        return list(_PARSERS.keys())


# Singleton
parser = ParserEngine()
