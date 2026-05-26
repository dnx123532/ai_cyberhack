"""
NEXUS — Pattern Extractor
Ekstrak POLA dari raw scripts (bukan raw code).
AI belajar PATTERN, bukan menghafal syntax.

Output: datasets/code_patterns/code_patterns.jsonl
        datasets/workflow_patterns/workflow_patterns.jsonl
        datasets/execution_patterns/execution_patterns.jsonl
"""

import sys
from pathlib import Path

from shared.utils import setup_encoding, get_logger, root, save_jsonl, make_conversation

setup_encoding()
logger = get_logger("nexus.patterns")

# ── Output dirs ───────────────────────────────────────────────────────────────
CODE_DIR    = root("datasets", "code_patterns")
WFLOW_DIR   = root("datasets", "workflow_patterns")
EXEC_DIR    = root("datasets", "execution_patterns")
for d in (CODE_DIR, WFLOW_DIR, EXEC_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ── Pattern definitions ───────────────────────────────────────────────────────

CODE_PATTERNS = [
    {
        "name"    : "subprocess_capture",
        "desc"    : "Jalankan external tool dan capture output",
        "use_case": "nmap, gobuster, subfinder — tool CLI dengan stdout output",
        "code"    : (
            "result = subprocess.run(\n"
            "    [tool_name] + args,\n"
            "    capture_output=True, text=True, timeout=30\n"
            ")\n"
            "if result.returncode == 0:\n"
            "    return result.stdout.splitlines()\n"
            "raise RuntimeError(result.stderr)"
        ),
    },
    {
        "name"    : "subprocess_with_retry",
        "desc"    : "Jalankan tool dengan exponential backoff retry",
        "use_case": "Network tools yang flaky, DNS resolution, API calls",
        "code"    : (
            "def run_with_retry(cmd, retries=3, delay=2):\n"
            "    for attempt in range(retries):\n"
            "        try:\n"
            "            result = subprocess.run(cmd, capture_output=True,\n"
            "                                    text=True, timeout=30)\n"
            "            if result.returncode == 0:\n"
            "                return result.stdout\n"
            "        except subprocess.TimeoutExpired:\n"
            "            pass\n"
            "        time.sleep(delay * (2 ** attempt))  # exponential backoff\n"
            "    raise RuntimeError(f'Failed after {retries} attempts')"
        ),
    },
    {
        "name"    : "subprocess_streaming",
        "desc"    : "Stream output realtime dari long-running process",
        "use_case": "nmap -p-, masscan, nuclei — tool yang butuh live output",
        "code"    : (
            "proc = subprocess.Popen(\n"
            "    cmd, stdout=subprocess.PIPE,\n"
            "    stderr=subprocess.STDOUT, text=True, bufsize=1\n"
            ")\n"
            "for line in proc.stdout:\n"
            "    line = line.rstrip()\n"
            "    yield line          # stream ke caller\n"
            "proc.wait()"
        ),
    },
    {
        "name"    : "async_concurrent_scan",
        "desc"    : "Scan multiple targets concurrently dengan semaphore",
        "use_case": "subfinder/dnsx/httpx pada banyak domain sekaligus",
        "code"    : (
            "async def scan_all(targets: list, concurrency: int = 10):\n"
            "    sem = asyncio.Semaphore(concurrency)\n"
            "    async def bounded(t):\n"
            "        async with sem:\n"
            "            proc = await asyncio.create_subprocess_exec(\n"
            "                *([tool] + [t]),\n"
            "                stdout=asyncio.subprocess.PIPE,\n"
            "                stderr=asyncio.subprocess.PIPE\n"
            "            )\n"
            "            out, _ = await proc.communicate()\n"
            "            return {'target': t, 'output': out.decode()}\n"
            "    return await asyncio.gather(*[bounded(t) for t in targets])"
        ),
    },
    {
        "name"    : "safe_output_parser",
        "desc"    : "Parse tool output dengan graceful error handling",
        "use_case": "Parse nmap XML, nuclei JSON, sqlmap output",
        "code"    : (
            "def parse_output(raw: str) -> list:\n"
            "    results = []\n"
            "    for line in raw.splitlines():\n"
            "        line = line.strip()\n"
            "        if not line or line.startswith('#'):\n"
            "            continue\n"
            "        try:\n"
            "            results.append(parse_line(line))\n"
            "        except ValueError:\n"
            "            continue   # skip malformed lines silently\n"
            "    return results"
        ),
    },
    {
        "name"    : "tool_availability_check",
        "desc"    : "Check tool availability dengan fallback ke alternatif",
        "use_case": "Pilih port scanner: rustscan → masscan → nmap (degraded)",
        "code"    : (
            "def best_available(candidates: list[str]) -> str:\n"
            "    for tool in candidates:\n"
            "        if shutil.which(tool):\n"
            "            return tool\n"
            "    raise RuntimeError(\n"
            "        f'None of {candidates} is installed. '\n"
            "        f'Install with: apt install {candidates[0]}'\n"
            "    )\n\n"
            "# Usage: scanner = best_available(['rustscan','masscan','nmap'])"
        ),
    },
    {
        "name"    : "structured_logging",
        "desc"    : "Structured JSON logging untuk AI-readable execution trail",
        "use_case": "Log semua tool execution agar AI bisa belajar dari history",
        "code"    : (
            "import logging, json\n"
            "logger = logging.getLogger('nexus')\n\n"
            "def log_execution(tool, args, result, duration):\n"
            "    logger.info(json.dumps({\n"
            "        'tool'    : tool,\n"
            "        'args'    : args,\n"
            "        'success' : result['returncode'] == 0,\n"
            "        'duration': duration,\n"
            "        'outputs' : result['stdout'][:200],\n"
            "    }))"
        ),
    },
    {
        "name"    : "graceful_error_handling",
        "desc"    : "Handle tool failure dengan primary → fallback → skip",
        "use_case": "Tool tidak terinstall, permission denied, timeout",
        "code"    : (
            "def run_safe(tool, args, fallback_tool=None):\n"
            "    try:\n"
            "        return executor.execute(tool, args)\n"
            "    except FileNotFoundError:\n"
            "        if fallback_tool:\n"
            "            logger.warning(f'{tool} not found, trying {fallback_tool}')\n"
            "            return executor.execute(fallback_tool, args)\n"
            "        return {'success': False, 'stderr': f'{tool} not installed'}\n"
            "    except subprocess.TimeoutExpired:\n"
            "        logger.warning(f'{tool} timed out')\n"
            "        return {'success': False, 'stderr': 'timeout'}"
        ),
    },
]

WORKFLOW_PATTERNS = [
    {
        "name"  : "recon_chain",
        "desc"  : "Full recon: domain → subdomains → live hosts → ports → vulns",
        "category": "recon+scan",
        "stages": [
            {"step":1,"tool":"subfinder",  "in":"domain",         "out":"subdomains.txt"},
            {"step":2,"tool":"dnsx",       "in":"subdomains.txt", "out":"resolved.txt"},
            {"step":3,"tool":"httpx",      "in":"resolved.txt",   "out":"live_hosts.txt"},
            {"step":4,"tool":"nmap",       "in":"resolved.txt",   "out":"ports.txt"},
            {"step":5,"tool":"nuclei",     "in":"live_hosts.txt", "out":"vulns.txt"},
        ],
        "parallelizable": [3, 4],
    },
    {
        "name"  : "web_assessment_chain",
        "desc"  : "Web pentest: discover paths → fingerprint → fuzz → vuln scan",
        "category": "web",
        "stages": [
            {"step":1,"tool":"gobuster",   "in":"url",         "out":"dirs.txt"},
            {"step":2,"tool":"whatweb",    "in":"url",         "out":"tech.json"},
            {"step":3,"tool":"ffuf",       "in":"url+wordlist","out":"paths.txt"},
            {"step":4,"tool":"nikto",      "in":"url",         "out":"vulns.txt"},
            {"step":5,"tool":"sqlmap",     "in":"url+params",  "out":"sqli.txt"},
        ],
        "parallelizable": [1, 2, 3],
    },
    {
        "name"  : "ad_enum_chain",
        "desc"  : "Active Directory: enumerate → Kerberoast → crack → lateral move",
        "category": "post_exploit",
        "stages": [
            {"step":1,"tool":"bloodhound", "in":"domain/creds", "out":"ad_graph.json"},
            {"step":2,"tool":"kerbrute",   "in":"domain/users", "out":"valid_users.txt"},
            {"step":3,"tool":"impacket",   "in":"dc_ip",        "out":"spn_hashes.txt"},
            {"step":4,"tool":"hashcat",    "in":"hashes",       "out":"cracked.txt"},
            {"step":5,"tool":"evil-winrm", "in":"ip/creds",     "out":"shell"},
        ],
        "parallelizable": [],
    },
    {
        "name"  : "cloud_audit_chain",
        "desc"  : "AWS/Cloud audit: enumerate IAM → misconfig → secrets → report",
        "category": "cloud",
        "stages": [
            {"step":1,"tool":"prowler",    "in":"aws_creds",   "out":"audit.json"},
            {"step":2,"tool":"pacu",       "in":"aws_creds",   "out":"findings.json"},
            {"step":3,"tool":"trufflehog", "in":"git_repo/s3", "out":"secrets.txt"},
            {"step":4,"tool":"scout",      "in":"aws_creds",   "out":"scout.html"},
        ],
        "parallelizable": [1, 2, 3],
    },
    {
        "name"  : "ir_response_chain",
        "desc"  : "Incident Response: memory dump → disk forensics → IOC hunt → timeline",
        "category": "forensics+defense",
        "stages": [
            {"step":1,"tool":"volatility", "in":"memory_dump", "out":"processes.json"},
            {"step":2,"tool":"autopsy",    "in":"disk_image",  "out":"artifacts"},
            {"step":3,"tool":"chainsaw",   "in":"evtx_logs",   "out":"events.json"},
            {"step":4,"tool":"yara",       "in":"files",       "out":"ioc_matches.json"},
            {"step":5,"tool":"loki",       "in":"filesystem",  "out":"ioc_report.txt"},
        ],
        "parallelizable": [1, 2],
    },
    {
        "name"  : "wireless_attack_chain",
        "desc"  : "Wireless pentest: discover → capture → crack → MITM",
        "category": "wireless",
        "stages": [
            {"step":1,"tool":"kismet",     "in":"interface",   "out":"networks.json"},
            {"step":2,"tool":"wifite",     "in":"interface",   "out":"handshake.cap"},
            {"step":3,"tool":"aircrack-ng","in":"handshake",   "out":"psk.txt"},
            {"step":4,"tool":"bettercap",  "in":"interface",   "out":"traffic.pcap"},
        ],
        "parallelizable": [],
    },
    {
        "name"  : "malware_analysis_chain",
        "desc"  : "Malware analysis: static → dynamic sandbox → IOC extraction → sig",
        "category": "malware",
        "stages": [
            {"step":1,"tool":"floss",      "in":"binary",      "out":"strings.txt"},
            {"step":2,"tool":"yara",       "in":"binary",      "out":"rule_matches.json"},
            {"step":3,"tool":"CAPEv2",     "in":"binary",      "out":"sandbox_report.json"},
            {"step":4,"tool":"yarGen",     "in":"binary",      "out":"new_rules.yar"},
        ],
        "parallelizable": [1, 2],
    },
    {
        "name"  : "evasion_chain",
        "desc"  : "Payload crafting + AV/EDR bypass testing",
        "category": "evasion",
        "stages": [
            {"step":1,"tool":"msfvenom",       "in":"payload_type",    "out":"payload.exe"},
            {"step":2,"tool":"Veil",           "in":"payload.exe",     "out":"obfuscated.exe"},
            {"step":3,"tool":"DefenderCheck",  "in":"obfuscated.exe",  "out":"detection_report"},
            {"step":4,"tool":"AMSITrigger",    "in":"script",          "out":"amsi_triggers.txt"},
        ],
        "parallelizable": [],
    },
    {
        "name"  : "social_engineering_chain",
        "desc"  : "Phishing campaign: clone → host → harvest → report",
        "category": "social",
        "stages": [
            {"step":1,"tool":"GoPhish",    "in":"template/targets", "out":"campaign_id"},
            {"step":2,"tool":"evilginx2",  "in":"domain/phishlet",  "out":"session_tokens"},
            {"step":3,"tool":"SocialFish", "in":"target_url",       "out":"credentials.txt"},
        ],
        "parallelizable": [],
    },
    {
        "name"  : "iot_firmware_chain",
        "desc"  : "IoT/firmware: extract → analyze → find vulns → exploit",
        "category": "iot",
        "stages": [
            {"step":1,"tool":"binwalk",    "in":"firmware.bin",     "out":"extracted/"},
            {"step":2,"tool":"firmwalker", "in":"extracted/",       "out":"findings.txt"},
            {"step":3,"tool":"emba",       "in":"firmware.bin",     "out":"report.html"},
            {"step":4,"tool":"RouterSploit","in":"device_ip",       "out":"vulns.txt"},
        ],
        "parallelizable": [2, 3],
    },
]

EXEC_PATTERNS_QA = [
    (
        "Bagaimana AI NEXUS memilih tool yang tepat untuk sebuah task?",
        (
            "NEXUS menggunakan **tool registry** dengan logic:\n\n"
            "1. **Identifikasi task stage** → mapping ke workflow_stage\n"
            "2. **Query registry** berdasarkan `workflow_stage` + `input_type`\n"
            "3. **Filter by risk** sesuai authorization scope\n"
            "4. **Availability check** — hanya tools yang terinstall\n"
            "5. **Select best match** berdasarkan purpose + output format\n"
            "6. **Build execution chain** via `chained_with` field\n\n"
            "Contoh: task='scan ports' → stage='scan' → [nmap, masscan, rustscan] → select available"
        ),
    ),
    (
        "Bagaimana cara chain output dari satu tool ke tool berikutnya?",
        (
            "NEXUS menggunakan **file intermediary pattern**:\n\n"
            "```\n"
            "subfinder -d target.com -o subdomains.txt\n"
            "dnsx -l subdomains.txt -o resolved.txt\n"
            "httpx -l resolved.txt -o live_hosts.txt\n"
            "nuclei -l live_hosts.txt -o vulns.txt\n"
            "```\n\n"
            "Setiap tool menulis ke file → tool berikutnya membaca file tersebut.\n"
            "Output format distandarisasi (satu host/IP per baris) agar kompatibel antar tool."
        ),
    ),
    (
        "Bagaimana handle jika tool gagal di tengah workflow?",
        (
            "NEXUS menggunakan **graceful degradation**:\n\n"
            "1. Jika tool gagal dan ada fallback → run fallback\n"
            "2. Jika tidak ada fallback → log warning, lanjut ke step berikutnya\n"
            "3. Jika step kritikal gagal (stop_on_fail=True) → hentikan workflow\n"
            "4. Setelah workflow selesai → reflection: analisa step yang gagal\n"
            "5. Retry dengan parameter berbeda jika ada pattern failure"
        ),
    ),
    (
        "Bagaimana AI scan banyak target secara efisien?",
        (
            "Untuk banyak target, NEXUS menggunakan **async concurrent execution**:\n\n"
            "```python\n"
            "semaphore = asyncio.Semaphore(10)  # max 10 concurrent\n"
            "results = await asyncio.gather(\n"
            "    *[bounded_scan(target) for target in targets]\n"
            ")\n"
            "```\n\n"
            "Rate limit dengan semaphore mencegah flooding network.\n"
            "Recommended concurrency: 10 untuk scan, 50 untuk DNS resolution."
        ),
    ),
]


def build_datasets():
    logger.info("Building pattern datasets")

    # 1. code_patterns.jsonl
    code_records = []
    for p in CODE_PATTERNS:
        q = f"Berikan contoh pattern '{p['name']}' untuk security automation."
        a = (f"**{p['name']}**\n\n"
             f"**Deskripsi:** {p['desc']}\n\n"
             f"**Use case:** {p['use_case']}\n\n"
             f"```python\n{p['code']}\n```")
        code_records.append(make_conversation(q, a, context="patterns"))
    save_jsonl(CODE_DIR / "code_patterns.jsonl", code_records)
    logger.info(f"code_patterns.jsonl: {len(code_records)} entries")

    # 2. workflow_patterns.jsonl
    wf_records = []
    for wp in WORKFLOW_PATTERNS:
        q = f"Jelaskan workflow chain untuk '{wp['name']}'."
        steps_str = "\n".join(
            f"  Step {s['step']}: [{s['tool']}]  {s['in']} → {s['out']}"
            for s in wp["stages"]
        )
        par = wp.get("parallelizable", [])
        a = (f"**Workflow: {wp['name']}**\n\n"
             f"**Deskripsi:** {wp['desc']}\n\n"
             f"**Steps:**\n{steps_str}\n\n")
        if par:
            tools = [wp["stages"][i-1]["tool"] for i in par if i <= len(wp["stages"])]
            a += f"**Parallelizable:** Steps {par} → {', '.join(tools)} bisa jalan bersamaan"
        wf_records.append(make_conversation(q, a, context="patterns"))
    save_jsonl(WFLOW_DIR / "workflow_patterns.jsonl", wf_records)
    logger.info(f"workflow_patterns.jsonl: {len(wf_records)} entries")

    # 3. execution_patterns.jsonl
    exec_records = [make_conversation(q, a, context="patterns") for q, a in EXEC_PATTERNS_QA]
    save_jsonl(EXEC_DIR / "execution_patterns.jsonl", exec_records)
    logger.info(f"execution_patterns.jsonl: {len(exec_records)} entries")

    print(f"\n  ✅ Pattern datasets built")
    print(f"  code_patterns     : {len(code_records)} entries")
    print(f"  workflow_patterns : {len(wf_records)} entries")
    print(f"  execution_patterns: {len(exec_records)} entries\n")


if __name__ == "__main__":
    build_datasets()
