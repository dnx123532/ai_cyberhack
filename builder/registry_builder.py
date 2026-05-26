"""
NEXUS — Registry Builder
Input : tool_registry/raw_tools.json  (atau data/v2/tools_script.json jika masih ada)
        analyzer/output/analysis_report.json
Output: tool_registry/registry.json        full registry
        tool_registry/registry_by_cat.json grouped by category
        tool_registry/registry_lite.json   lightweight untuk AI query
        datasets/tool_metadata/tool_metadata.jsonl  untuk training
"""

import sys
from pathlib import Path
from collections import defaultdict

from shared.utils import (setup_encoding, get_logger, root,
                          load_json, save_json, save_jsonl, make_conversation)

setup_encoding()
logger = get_logger("nexus.registry")

# ── Paths (all resolved from project root) ────────────────────────────────────
TOOLS_JSON    = root("tool_registry", "raw_tools.json")
ANALYSIS_JSON = root("analyzer", "output", "analysis_report.json")
REGISTRY_DIR  = root("tool_registry")
DATASET_DIR   = root("datasets", "tool_metadata")

# ── Maps berdasarkan 15 kategori ASLI dari data/raw_datasets/tool_scripts/ ────

# workflow_stage: fase dalam pentest/SOC lifecycle
STAGE_MAP = {
    "recon"       : "recon",           # passive/active reconnaissance
    "scan"        : "scan",            # port/service/vuln scanning
    "web"         : "attack",          # web application testing
    "exploit"     : "exploit",         # exploitation
    "post_exploit": "post_exploit",    # lateral movement, persistence, privesc
    "brute_force" : "attack",          # credential attacks
    "wireless"    : "attack",          # wireless/network attacks
    "cloud"       : "attack",          # cloud misconfig & attack
    "crypto"      : "analysis",        # cryptography, hash analysis
    "defense"     : "monitor",         # SIEM, IDS/IPS, hardening
    "evasion"     : "exploit",         # AV/EDR bypass, obfuscation
    "forensics"   : "analysis",        # incident response, memory/disk forensics
    "malware"     : "analysis",        # malware analysis, reverse engineering
    "social"      : "attack",          # phishing, social engineering
    "iot"         : "attack",          # IoT/firmware/embedded hacking
    "utilities"   : "misc",
}

# risk_level: seberapa destruktif jika disalahgunakan
RISK_MAP = {
    "recon"       : "low",
    "scan"        : "medium",
    "web"         : "high",
    "exploit"     : "critical",
    "post_exploit": "critical",
    "brute_force" : "high",
    "wireless"    : "high",
    "cloud"       : "high",
    "crypto"      : "low",
    "defense"     : "low",
    "evasion"     : "critical",
    "forensics"   : "low",
    "malware"     : "medium",
    "social"      : "high",
    "iot"         : "medium",
    "utilities"   : "low",
}

# input/output type per kategori
IO_MAP = {
    "recon"       : ("domain/ip/email/name",     "subdomains/hosts/intelligence"),
    "scan"        : ("ip/host/url/cidr",          "ports/services/vulnerabilities"),
    "web"         : ("url",                       "vulnerabilities/paths/secrets"),
    "exploit"     : ("target/payload",            "shell/access/rce"),
    "post_exploit": ("session/shell/credentials", "hashes/tokens/persistence"),
    "brute_force" : ("target/wordlist",           "valid_credentials/hashes"),
    "wireless"    : ("interface/ssid/pcap",       "handshake/credentials/traffic"),
    "cloud"       : ("credentials/region/url",    "misconfigs/access/secrets"),
    "crypto"      : ("hash/ciphertext/encoded",   "plaintext/decoded/cracked"),
    "defense"     : ("logs/events/network",       "alerts/rules/reports"),
    "evasion"     : ("payload/binary",            "obfuscated/bypass_artifact"),
    "forensics"   : ("memory_dump/disk_image",    "artifacts/iocs/timeline"),
    "malware"     : ("binary/sample/pcap",        "iocs/behavior/signatures"),
    "social"      : ("target/template",           "credentials/access"),
    "iot"         : ("firmware/device/interface", "vulnerabilities/backdoors"),
    "utilities"   : ("target",                    "output"),
}
CHAIN_MAP = {
    # recon chains
    "subfinder"    : ["dnsx","httpx","nuclei","nmap"],
    "amass"        : ["dnsx","masscan","nmap"],
    "theHarvester" : ["subfinder","amass","shodan"],
    "shodan"       : ["nmap","nuclei","metasploit"],
    "recon-ng"     : ["subfinder","theHarvester","shodan"],
    "Photon"       : ["subfinder","httpx","gobuster"],
    "Sublist3r"    : ["dnsx","httpx","nuclei"],
    # scan chains
    "dnsx"         : ["httpx","nuclei"],
    "httpx"        : ["nuclei","ffuf","nikto","whatweb","gobuster"],
    "nmap"         : ["nuclei","metasploit","searchsploit","nikto"],
    "masscan"      : ["nmap","nuclei"],
    "AutoRecon"    : ["nuclei","metasploit"],
    "nuclei"       : ["sqlmap","metasploit"],
    # web chains
    "gobuster"     : ["sqlmap","nikto","ffuf"],
    "ffuf"         : ["sqlmap","burpsuite"],
    "sqlmap"       : ["metasploit"],
    "wpscan"       : ["metasploit","hydra"],
    "nikto"        : ["sqlmap","metasploit"],
    # exploit chains
    "metasploit"   : ["mimikatz","bloodhound","crackmapexec"],
    "impacket"     : ["bloodhound","mimikatz","crackmapexec"],
    "pwntools"     : ["metasploit"],
    # post_exploit chains
    "bloodhound"   : ["impacket","mimikatz","rubeus"],
    "crackmapexec" : ["mimikatz","bloodhound","evil-winrm"],
    "LinPEAS"      : ["metasploit","crackmapexec"],
    "mimikatz"     : ["crackmapexec","evil-winrm","impacket"],
    "rubeus"       : ["impacket","crackmapexec"],
    # brute_force chains
    "hydra"        : ["metasploit","evil-winrm","crackmapexec"],
    "hashcat"      : ["metasploit","evil-winrm","crackmapexec"],
    "kerbrute"     : ["hashcat","crackmapexec"],
    # wireless chains
    "bettercap"    : ["wireshark","tcpdump","metasploit"],
    "aircrack-ng"  : ["hashcat"],
    "wifite"       : ["hashcat","aircrack-ng"],
    # cloud chains
    "pacu"         : ["aws","trufflehog"],
    "prowler"      : ["pacu","scout"],
    # forensics/malware chains
    "volatility"   : ["yara","strings"],
    "yarGen"       : ["yara","volatility"],
}


def build_entry(tool: dict, analysis_map: dict) -> dict:
    name     = tool.get("name") or tool.get("tool", "unknown")
    category = tool.get("category", "utilities")
    purpose  = tool.get("purpose") or tool.get("description", "")
    a        = analysis_map.get(name, {})
    has_sub  = bool(a.get("subprocess"))
    is_async = a.get("is_async", False)
    execution = ("async_subprocess" if is_async and has_sub
                 else "subprocess" if has_sub
                 else "api" if a.get("api_calls") else "cli")
    io = IO_MAP.get(category, ("target", "output"))
    return {
        "tool"          : name,
        "category"      : category,
        "purpose"       : purpose[:200],
        "workflow_stage": STAGE_MAP.get(category, "misc"),
        "risk"          : RISK_MAP.get(category, "medium"),
        "input"         : io[0],
        "output"        : io[1],
        "execution"     : execution,
        "supports_async": is_async,
        "chained_with"  : CHAIN_MAP.get(name.lower(), []),
        "tags"          : tool.get("tags", [])[:8],
        "path"          : f"tools/{category}/{name}",
    }


def build_registry():
    logger.info("Building tool registry")
    DATASET_DIR.mkdir(parents=True, exist_ok=True)

    tools_raw = load_json(TOOLS_JSON)
    if tools_raw is None:
        logger.error(f"raw_tools.json not found at {TOOLS_JSON}")
        logger.info("Run: python builder/tool_normalizer.py first")
        return

    analysis_list = load_json(ANALYSIS_JSON, default=[])
    analysis_map  = {a.get("name",""):a for a in analysis_list}
    logger.info(f"Tools: {len(tools_raw)}  Analysis entries: {len(analysis_map)}")

    registry = [build_entry(t, analysis_map) for t in tools_raw]
    by_cat   = defaultdict(list)
    for e in registry:
        by_cat[e["category"]].append(e)

    save_json(REGISTRY_DIR / "registry.json",        registry)
    save_json(REGISTRY_DIR / "registry_by_cat.json", dict(by_cat))
    lite = [{"tool":r["tool"],"category":r["category"],"purpose":r["purpose"],
             "workflow_stage":r["workflow_stage"],"risk":r["risk"],
             "chained_with":r["chained_with"]} for r in registry]
    save_json(REGISTRY_DIR / "registry_lite.json", lite)

    # Training JSONL — tool metadata in conversation format
    records = []
    for r in registry:
        q = f"Jelaskan tool {r['tool']}: tujuan, input/output, kapan digunakan, dan chain ke tool apa?"
        a = (f"**{r['tool']}** — {r['purpose']}\n\n"
             f"• Kategori      : {r['category']}\n"
             f"• Workflow stage: {r['workflow_stage']}\n"
             f"• Risk level    : {r['risk']}\n"
             f"• Input         : {r['input']}\n"
             f"• Output        : {r['output']}\n"
             f"• Execution     : {r['execution']}\n"
             f"• Async         : {'✓' if r['supports_async'] else '✗'}\n")
        if r["chained_with"]:
            a += f"• Chain ke      : {', '.join(r['chained_with'])}\n"
        records.append(make_conversation(q, a, context="tools"))
    save_jsonl(DATASET_DIR / "tool_metadata.jsonl", records)

    print(f"\n  Registry built: {len(registry)} tools")
    for cat, tools in sorted(by_cat.items(), key=lambda x: -len(x[1])):
        bar = "█" * min(len(tools)//50, 20)
        print(f"  {cat:20s}: {len(tools):5d}  {bar}")
    print(f"\n  ✅ Saved to tool_registry/  +  datasets/tool_metadata/\n")


if __name__ == "__main__":
    build_registry()
