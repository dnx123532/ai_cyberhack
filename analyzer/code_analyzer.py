"""
NEXUS — Code Analyzer
Membaca seluruh folder dataraw/ secara paralel dan mengekstrak:
  nama file, fungsi, subprocess, async, parser, API, retry, logging, dependency
Output: analyzer/output/{analysis_report,summary,parse_errors,readme_summaries}.json
"""

import ast, json, sys
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from shared.utils import setup_encoding, get_logger, ensure_dir, save_json, root

setup_encoding()
logger = get_logger("nexus.analyzer")

DATARAW_DIR = root("data", "raw_datasets", "tool_scripts")  # {category}/{tool_name}/...
OUTPUT_DIR  = ensure_dir(root("analyzer", "output"))

# ── 15 kategori berdasarkan struktur folder AKTUAL di data/raw_datasets/tool_scripts/ ──
CATEGORY_KEYWORDS = {
    "recon"       : ["subfinder","amass","dnsx","massdns","whois","passive","enum","discovery",
                     "harvester","spiderfoot","maltego","shodan","osint","photon","sublist3r",
                     "recon-ng","theharvester","censys","hunter","breach","email","linkedin"],
    "scan"        : ["nmap","masscan","rustscan","nuclei","nikto","openvas","port","scan",
                     "vuln","detect","autoRecon","legion","nmap-vulners","nmapAutomator",
                     "service","fingerprint","banner"],
    "web"         : ["sqlmap","burp","ffuf","gobuster","dirsearch","wfuzz","xss","sqli","lfi",
                     "inject","fuzz","crawl","zaproxy","nikto","davtest","wpscan","joomscan",
                     "droopescan","whatweb","wafw00f","ssrf","ssti"],
    "exploit"     : ["metasploit","msfconsole","exploit","payload","shellcode","overflow","rce",
                     "reverse_shell","beef","pwntools","impacket","searchsploit","exploitdb",
                     "cve","poc","eternalblue","ms17"],
    "post_exploit": ["mimikatz","bloodhound","crackmapexec","linpeas","winpeas","privesc",
                     "lateral","privilege","escalat","dump","token","evil-winrm","empire",
                     "nishang","powersploit","sharpcollection","rubeus","kerbrute"],
    "brute_force" : ["hydra","medusa","brutex","spray","brute","credential","force","patator",
                     "crowbar","aircrack","hashcat","john","cracker","rainbow","wordlist",
                     "crack","hash","rockyou","mutation"],
    "wireless"    : ["aircrack","airodump","wifite","kismet","wpa","wifi","bluetooth","wireless",
                     "bettercap","hostapd","mdk3","mdk4","wifiphisher","wireshark","tcpdump",
                     "scapy","ettercap","arp","mitm","sniff","capture","bssid","ssid"],
    "cloud"       : ["pacu","scout","prowler","awscli","boto","azure","gcp","s3","iam","bucket",
                     "cloud","trufflehog","gitleaks","cloudsploit","cloudmapper","lambda",
                     "kubernetes","k8s","docker","container","ecr","eks","terraform"],
    "crypto"      : ["cyberchef","rsactftool","hashid","haiti","openssl","gpg","encrypt","decrypt",
                     "cipher","hash","aes","rsa","sha","md5","bcrypt","base64","hex","xor",
                     "steg","steganograph","decode","encode","crypto"],
    "defense"     : ["wazuh","yara","zeek","sigma","snort","suricata","ids","ips","siem",
                     "monitor","alert","detect","ossec","tripwire","auditd","defender",
                     "endpoint","edr","antivirus","firewall","harden","baseline","cis"],
    "evasion"     : ["amsi","amsiTrigger","defendercheck","shellter","veil","charlotte","obfusc",
                     "bypass","evade","av","edr","unhook","hollow","inject","dll","lolbas",
                     "living","land","mshta","regsvr","certutil","rundll"],
    "forensics"   : ["volatility","autopsy","sleuthkit","strings","foremost","forensic",
                     "artifact","timeline","memory","dump","image","disk","carv","recover",
                     "chainsaw","hayabusa","loki","thor","log2timeline","plaso","evtx"],
    "malware"     : ["ghidra","radare","ida","yara","peid","sandbox","decompil","reverse",
                     "disassem","malware","capev2","cuckoo","maltrail","yargen","angr",
                     "binwalk","floss","remnux","dynamic","static","rat","trojan"],
    "social"      : ["gophish","socialfish","evilginx","setoolkit","phish","spear","bait",
                     "pretex","vishing","smishing","email","clone","harvest","credential",
                     "phEmail","evilginx2","modlishka"],
    "iot"         : ["routersploit","binwalk","fact","firmwalker","emba","firmware","iot",
                     "embedded","uart","jtag","spi","i2c","can","modbus","mqtt","coap",
                     "zigbee","zwave","lora","scada","ics","plc","android","apk","jadx","frida"],
}


class FileAnalyzer(ast.NodeVisitor):
    __slots__ = ("filepath","functions","classes","imports","subprocess","async_funcs",
                 "api_calls","has_retry","has_logging","has_argparse")

    def __init__(self, filepath: Path):
        self.filepath     = filepath
        self.functions    = []
        self.classes      = []
        self.imports      = set()      # set avoids dup from the start
        self.subprocess   = set()
        self.async_funcs  = []
        self.api_calls    = set()
        self.has_retry    = False
        self.has_logging  = False
        self.has_argparse = False

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.add(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        mod = node.module or ""
        self.imports.add(mod)
        if mod in ("logging", "loguru"):   self.has_logging  = True
        if mod == "argparse":              self.has_argparse = True
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self.functions.append(node.name)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self.async_funcs.append(node.name)
        self.functions.append(node.name)
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self.classes.append(node.name)
        self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            base = self._name(node.func.value)
            full = f"{base}.{attr}"
            if "subprocess" in base or attr in ("run","Popen","call","check_output"):
                self.subprocess.add(full)
            if attr in ("get","post","request","fetch","session"):
                self.api_calls.add(full)
        elif isinstance(node.func, ast.Name):
            if node.func.id in ("subprocess","Popen","run"):
                self.subprocess.add(node.func.id)

        # retry detection — only use ast.unparse on 3.9+ (silent fallback otherwise)
        if not self.has_retry and hasattr(ast, "unparse"):
            try:
                code = ast.unparse(node).lower()
                if "retry" in code or "attempts" in code or "backoff" in code:
                    self.has_retry = True
            except Exception:
                pass

        self.generic_visit(node)

    @staticmethod
    def _name(node) -> str:
        if isinstance(node, ast.Name):      return node.id
        if isinstance(node, ast.Attribute): return f"{FileAnalyzer._name(node.value)}.{node.attr}"
        return ""


def detect_category(filepath: Path, imports: set) -> str:
    """
    Deteksi kategori dari data/raw_datasets/tool_scripts/{category}/{tool_name}/...
    Struktur sudah pre-categorized → pakai folder level-1 langsung.
    Fallback ke keyword scoring jika folder tidak match kategori yang dikenal.
    """
    KNOWN_CATS = set(CATEGORY_KEYWORDS.keys())
    try:
        rel_parts = filepath.relative_to(DATARAW_DIR).parts
        # rel_parts[0] = kategori (e.g. "recon", "exploit")
        # rel_parts[1] = nama tool (e.g. "theHarvester", "metasploit")
        if rel_parts and rel_parts[0].lower() in KNOWN_CATS:
            return rel_parts[0].lower()
        cat_folder = rel_parts[0].lower() if rel_parts else ""
    except ValueError:
        cat_folder = ""

    # Fallback: keyword scoring dari path + imports
    text = cat_folder + " " + str(filepath).lower() + " " + " ".join(imports).lower()
    scores = {cat: sum(1 for kw in kws if kw in text) for cat, kws in CATEGORY_KEYWORDS.items()}
    best_cat, best_score = max(scores.items(), key=lambda x: x[1])
    return best_cat if best_score > 0 else "utilities"


def analyze_file(filepath: Path) -> dict:
    try:
        rel = filepath.relative_to(DATARAW_DIR)
        # structure: {category}/{tool_name}/... → use tool_name as name
        tool_name = rel.parts[1] if len(rel.parts) > 1 else filepath.stem
    except ValueError:
        tool_name = filepath.stem
    result = {
        "file": str(filepath.relative_to(DATARAW_DIR)),
        "name": tool_name,
        "size_kb": round(filepath.stat().st_size / 1024, 1),
        "category": "unknown", "functions": [], "classes": [],
        "imports": [], "subprocess": [], "async_funcs": [], "api_calls": [],
        "has_retry": False, "has_logging": False, "has_argparse": False,
        "is_async": False, "parse_error": None,
    }
    try:
        source = filepath.read_text(encoding="utf-8", errors="ignore")
        tree   = ast.parse(source)
        fa     = FileAnalyzer(filepath)
        fa.visit(tree)
        result.update({
            "functions"  : fa.functions[:30],
            "classes"    : fa.classes,
            "imports"    : sorted(fa.imports)[:20],
            "subprocess" : sorted(fa.subprocess),
            "async_funcs": fa.async_funcs,
            "api_calls"  : sorted(fa.api_calls),
            "has_retry"  : fa.has_retry,
            "has_logging": fa.has_logging,
            "has_argparse":fa.has_argparse,
            "is_async"   : bool(fa.async_funcs),
            "category"   : detect_category(filepath, fa.imports),
        })
    except SyntaxError as e:
        result["parse_error"] = f"SyntaxError: {e}"
    except Exception as e:
        result["parse_error"] = str(e)
    return result


def extract_readme_desc(readme_path: Path) -> str:
    try:
        text  = readme_path.read_text(encoding="utf-8", errors="ignore")
        lines = [l.strip() for l in text.splitlines() if l.strip() and not l.startswith(("#","<","!"))]
        return " ".join(lines[:3])[:300]
    except (OSError, UnicodeDecodeError):
        return ""


def run_analysis(workers: int = 8):
    logger.info("NEXUS Code Analyzer starting")

    if not DATARAW_DIR.exists():
        logger.error(f"dataraw/ not found: {DATARAW_DIR}")
        logger.info("Buat folder dataraw/ dan isi dengan repo GitHub security tools")
        return

    # Cari semua Python files; skip venv/node_modules/test dirs
    SKIP = {"venv", ".venv", "node_modules", "site-packages", "__pycache__",
            ".git", "test", "tests", "spec", "docs", "examples", "migrations"}
    py_files = [
        p for p in DATARAW_DIR.rglob("*.py")
        if not any(s in p.parts for s in SKIP)
    ]
    readmes  = list(DATARAW_DIR.rglob("README*"))

    # Count unique tool repos (direct subdirs of dataraw/)
    tool_repos = {p.relative_to(DATARAW_DIR).parts[0]
                  for p in py_files
                  if len(p.relative_to(DATARAW_DIR).parts) > 0}
    logger.info(f"Tool repos: {len(tool_repos)}  Python files: {len(py_files)}  READMEs: {len(readmes)}")

    # Parallel analysis
    results, errors = [], []
    by_cat = defaultdict(list)
    done = 0

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(analyze_file, f): f for f in py_files}
        for fut in as_completed(futures):
            r = fut.result()
            results.append(r)
            by_cat[r["category"]].append(r["name"])
            if r["parse_error"]:
                errors.append({"file": r["file"], "error": r["parse_error"]})
            done += 1
            if done % 200 == 0:
                logger.info(f"  {done}/{len(py_files)} analyzed...")

    # README summaries (capped at 100 for speed)
    readme_summaries = {
        rm.parent.name: extract_readme_desc(rm)
        for rm in readmes[:100]
    }

    summary = {
        "total_py_files"  : len(py_files),
        "total_analyzed"  : len(results),
        "parse_errors"    : len(errors),
        "categories"      : {c: len(t) for c, t in sorted(by_cat.items(), key=lambda x: -len(x[1]))},
        "async_tools"     : sum(1 for r in results if r["is_async"]),
        "subprocess_tools": sum(1 for r in results if r["subprocess"]),
        "has_retry"       : sum(1 for r in results if r["has_retry"]),
        "has_logging"     : sum(1 for r in results if r["has_logging"]),
    }

    save_json(OUTPUT_DIR / "analysis_report.json",    results,          pretty=True)
    save_json(OUTPUT_DIR / "summary.json",            summary,          pretty=True)
    save_json(OUTPUT_DIR / "parse_errors.json",       errors,           pretty=True)
    save_json(OUTPUT_DIR / "readme_summaries.json",   readme_summaries, pretty=True)

    print(f"\n  {'─'*50}")
    print(f"  CATEGORY BREAKDOWN ({len(results)} files analyzed)")
    print(f"  {'─'*50}")
    for cat, count in summary["categories"].items():
        bar = "█" * min(count // max(len(py_files) // 30, 1), 25)
        print(f"  {cat:20s}: {count:5d}  {bar}")
    print(f"\n  Async   : {summary['async_tools']}  Subprocess: {summary['subprocess_tools']}")
    print(f"  Errors  : {len(errors)}")
    print(f"  Output  : {OUTPUT_DIR}\n")


if __name__ == "__main__":
    run_analysis()
