# NEXUS — AI Security Operations Agent
## Complete Architecture Documentation (Steps 1–10)

---

## STEP 1 — PROJECT STRUCTURE

```
nexus/
├── dataraw/              ← INPUT raw GitHub repos (flat, uncategorized)
├── tools/                ← OUTPUT tools setelah normalisasi (15 kategori)
│   ├── recon/            subfinder, amass, theHarvester, recon-ng, Photon
│   ├── scan/             nmap, masscan, nuclei, AutoRecon, Legion
│   ├── web/              sqlmap, burpsuite, ffuf, gobuster, wpscan, nikto
│   ├── exploit/          metasploit, impacket, pwntools, searchsploit, BeEF
│   ├── post_exploit/     mimikatz, bloodhound, crackmapexec, LinPEAS, evil-winrm
│   ├── brute_force/      hydra, medusa, hashcat, john, kerbrute
│   ├── wireless/         aircrack-ng, wifite, bettercap, kismet, airodump-ng
│   ├── cloud/            pacu, prowler, trufflehog, scout, awscli
│   ├── crypto/           cyberchef, hashid, haiti, RsaCtfTool, openssl
│   ├── defense/          wazuh, yara, zeek, sigma, chainsaw, snort
│   ├── evasion/          veil, shellter, AMSITrigger, DefenderCheck, charlotte
│   ├── forensics/        volatility, autopsy, sleuthkit, plaso, chainsaw
│   ├── malware/          ghidra, CAPEv2, yarGen, floss, radare2
│   ├── social/           GoPhish, evilginx2, SocialFish, setoolkit
│   ├── iot/              binwalk, firmwalker, emba, RouterSploit, FACT_core
│   └── utilities/        misc tools yang tidak fit kategori lain
├── tool_registry/        ← JSON metadata semua tools
│   ├── registry.json          full registry
│   ├── registry_by_cat.json   grouped by category
│   ├── registry_lite.json     lightweight untuk AI query
│   ├── raw_tools.json         intermediate dari normalizer
│   └── duplicates.json        tools yang di-deduplicate
├── analyzer/             ← PIPELINE step 1: analisa dataraw/
│   ├── code_analyzer.py       baca semua .py di dataraw/
│   └── output/
│       ├── analysis_report.json
│       ├── summary.json
│       ├── parse_errors.json
│       └── readme_summaries.json
├── builder/              ← PIPELINE step 2-5: buat registry + datasets
│   ├── tool_normalizer.py     categorize + deduplicate tools
│   ├── registry_builder.py    build registry dari raw_tools.json
│   ├── dataset_builder.py     generate 6 core training datasets
│   └── pattern_extractor.py   extract code + workflow patterns
├── datasets/             ← TRAINING DATA (modular per type)
│   ├── reasoning/             cara AI berpikir sebelum bertindak
│   ├── planning/              multi-step planning chains
│   ├── workflow/              execution sequences tool-by-tool
│   ├── reflection/            self-correction dan adaptive learning
│   ├── memory/                context management patterns
│   ├── style/                 presentation dan output format
│   ├── tool_metadata/         tool registry dalam format percakapan
│   ├── code_patterns/         subprocess, async, retry patterns
│   ├── workflow_patterns/     chaining patterns antar tools
│   ├── execution_patterns/    Q&A execution logic
│   └── final/                 merged + shuffled untuk training
├── runtime/              ← RUNTIME (digunakan saat inference)
│   ├── tool_executor.py       eksekusi tools via WSL Kali Linux
│   ├── workflow_executor.py   orchestrate multi-step workflows
│   ├── terminal_controller.py persistent bash session management
│   ├── browser_controller.py  buka browser, reports, dashboards
│   ├── parser_engine.py       parse output nmap/nuclei/dll → structured
│   └── dashboard_launcher.py  serve SOC dashboard + JSON API
├── inference/            ← POST-TRAINING inference scripts
├── ui/                   ← SOC Dashboard (dark neon futuristic)
│   ├── index.html
│   └── static/
│       ├── css/nexus.css
│       └── js/nexus.js
├── shared/               ← SHARED utilities (no duplication)
│   └── utils.py               setup_encoding, root(), save_jsonl, dll
├── training/             ← TRAINING scripts (Colab/GPU)
│   ├── train.py               QLoRA fine-tuning
│   ├── validation.py          JSONL validator
│   └── configs/qlora_config.yaml
├── memory/               ← AGENT MEMORY (runtime persistent)
│   ├── long_term/             facts across sessions
│   └── session/               current session context
├── logs/                 ← LOGS semua module
│   ├── analyzer/
│   ├── runtime/
│   └── training/
├── checkpoints/          ← MODEL CHECKPOINTS (dari training)
├── models/               ← FINAL MODELS (post merge LoRA)
├── build_all.py          ← MASTER BUILD (jalankan semua 5 step)
└── NEXUS_Colab.ipynb     ← Google Colab training notebook
```

**Penggunaan per fase:**

| Folder | Analisis | Training | Runtime | Inference |
|--------|----------|----------|---------|-----------|
| `dataraw/` | ✅ INPUT | ❌ | ❌ | ❌ |
| `tools/` | ❌ | ❌ | ✅ ref | ✅ |
| `tool_registry/` | ❌ | ✅ lite | ✅ query | ✅ |
| `datasets/` | ❌ | ✅ ALL | ❌ | ❌ |
| `runtime/` | ❌ | ❌ | ✅ | ✅ |
| `memory/` | ❌ | ❌ | ✅ | ✅ |
| `models/` | ❌ | ✅ output | ❌ | ✅ |

---

## STEP 2 — DATARAW ANALYSIS

**Input:** `dataraw/` — flat GitHub repos, belum dikategorikan
**Script:** `analyzer/code_analyzer.py`

**Struktur input yang diharapkan:**
```
dataraw/
├── subfinder/       ← repo GitHub subfinder (uncategorized)
├── nmap/            ← repo GitHub nmap
├── bloodhound/      ← repo BloodHound
├── binwalk/         ← repo binwalk
└── ...              ← ribuan repos lainnya (campur semua kategori)
```

**Yang dianalisa dari setiap .py file:**

| Feature | Cara Deteksi | Manfaat untuk Training |
|---------|-------------|----------------------|
| Tool name | `filepath.parts[0]` (parent folder) | identifikasi |
| Fungsi | `ast.FunctionDef` | capability mapping |
| Subprocess | `ast.Call → subprocess.run/Popen` | execution type detection |
| Async | `ast.AsyncFunctionDef` | concurrency support flag |
| API calls | `requests.get/post` pattern | execution type = api |
| Retry logic | `retry/backoff/attempt` keyword | reliability pattern |
| Logging | `import logging/loguru` | observability pattern |
| Kategori | **keyword scoring** (path + imports) | classification |

**Kategorisasi dari flat repos (keyword scoring):**
```python
# dataraw/subfinder/ → "subfinder" ada di keyword list "recon"
# dataraw/bloodhound/ → "bloodhound" ada di keyword list "post_exploit"

def detect_category(filepath, imports):
    tool_name = filepath.relative_to(DATARAW_DIR).parts[0]   # "subfinder"
    text = tool_name + " " + " ".join(imports).lower()
    scores = {
        cat: sum(1 for kw in kws if kw in text)
        for cat, kws in CATEGORY_KEYWORDS.items()
    }
    return max(scores, key=scores.get)   # best match
```

**Output:**
```
analyzer/output/
├── analysis_report.json    ← setiap file: {name, category, functions, imports, ...}
├── summary.json            ← statistik: total tools per category
├── parse_errors.json       ← file yang gagal AST parse (syntax error)
└── readme_summaries.json   ← deskripsi tool dari README files
```

---

## STEP 3 — TOOLS NORMALIZATION

**Input:** `analyzer/output/analysis_report.json`
**Script:** `builder/tool_normalizer.py`
**Output:** `tool_registry/raw_tools.json` + `tools/{category}/`

**Proses normalisasi:**
```
analysis_report.json
      ↓ group by tool name (stem)
      ↓ deduplicate: pilih file terbesar sebagai representative
      ↓ infer purpose dari function names + imports
      ↓ copy best script → tools/{category}/{tool_name}.py
      ↓
raw_tools.json    ← metadata semua tools yang sudah bersih
duplicates.json   ← daftar tools yang di-merge
tools/recon/subfinder.py
tools/scan/nmap.py
...
```

**Duplicate handling:**
```python
# Jika ada 3 file bernama "nmap.py" di 3 subfolder berbeda:
# → pilih yang size terbesar (paling complete)
# → 2 sisanya masuk duplicates.json
by_name = defaultdict(list)
for entry in analysis: by_name[entry["name"]].append(entry)
best = max(entries, key=lambda e: e["size_kb"])
```

**Workflow relation via CHAIN_MAP:**
```python
# subfinder → output: subdomains.txt
# dnsx → input: subdomains.txt (chained dari subfinder)
CHAIN_MAP = {
    "subfinder": ["dnsx", "httpx", "nuclei", "nmap"],
    "nmap":      ["nuclei", "metasploit", "searchsploit"],
    "bloodhound":["impacket", "mimikatz", "crackmapexec"],
    "hashcat":   ["metasploit", "evil-winrm"],
    ...
}
```

---

## STEP 4 — TOOL REGISTRY SYSTEM

**Input:** `tool_registry/raw_tools.json`
**Script:** `builder/registry_builder.py`

**Format satu entry registry:**
```json
{
  "tool": "subfinder",
  "category": "recon",
  "purpose": "passive subdomain enumeration via public DNS data sources",
  "workflow_stage": "recon",
  "risk": "low",
  "input": "domain/ip/email/name",
  "output": "subdomains/hosts/intelligence",
  "execution": "subprocess",
  "supports_async": true,
  "chained_with": ["dnsx", "httpx", "nuclei", "nmap"],
  "tags": [],
  "path": "tools/recon/subfinder"
}
```

**15 kategori dengan mapping stage dan risk:**

| Kategori | Stage | Risk | Input | Output |
|----------|-------|------|-------|--------|
| recon | recon | low | domain/ip | subdomains/intel |
| scan | scan | medium | ip/host/url | ports/services/vulns |
| web | attack | high | url | vulns/paths/secrets |
| exploit | exploit | critical | target/payload | shell/rce |
| post_exploit | post_exploit | critical | session/shell | hashes/persistence |
| brute_force | attack | high | target/wordlist | credentials |
| wireless | attack | high | interface/ssid | handshake/creds |
| cloud | attack | high | credentials/url | misconfigs/secrets |
| crypto | analysis | low | hash/ciphertext | plaintext/decoded |
| defense | monitor | low | logs/network | alerts/rules |
| evasion | exploit | critical | payload/binary | obfuscated/bypass |
| forensics | analysis | low | memory/disk | artifacts/timeline |
| malware | analysis | medium | binary/sample | iocs/behavior |
| social | attack | high | target/template | credentials/access |
| iot | attack | medium | firmware/device | vulns/backdoors |

**Bagaimana AI membaca dan menggunakan registry:**

```python
# 1. Load saat startup (cached)
self.registry = {t["tool"]: t for t in load_json("registry.json")}

# 2. Select tools untuk task tertentu
def select_tools(stage="scan", risk_max="high"):
    return [t for t in registry.values()
            if t["workflow_stage"] == stage
            and risk_order[t["risk"]] <= risk_order[risk_max]
            and is_available(t["tool"])]   # cek di WSL

# 3. Build workflow chain otomatis
def build_chain(start_tool):
    chain = [start_tool]
    for next_tool in registry[start_tool]["chained_with"]:
        if is_available(next_tool):
            chain.append(next_tool)
    return chain
# build_chain("subfinder") → ["subfinder", "dnsx", "httpx", "nuclei"]

# 4. Risk gating
if current_scope == "passive_only":
    tools = select_tools(risk_max="low")   # hanya recon tools
```

**Kenapa registry digunakan runtime (bukan ditraining)?**
- Registry **berubah** saat tools baru diinstall/dihapus
- Training data bersifat **static** (snapshot saat training)
- `is_available()` harus dicek **real-time** di WSL
- Memungkinkan AI adapt ke environment yang berbeda tanpa retrain

---

## STEP 5 — CODE PATTERN EXTRACTION

**Script:** `builder/pattern_extractor.py`

**Prinsip utama: AI belajar POLA, bukan hafal syntax raw exploit**

```
Raw code (TIDAK masuk training):         Pattern yang diekstrak (MASUK training):
─────────────────────────────────────    ─────────────────────────────────────────
subprocess.run(["nmap","-p-",target])  → "cara jalankan CLI tool + capture output"
for line in proc.stdout:               → "cara stream realtime output subprocess"
time.sleep(delay * 2 ** attempt)       → "exponential backoff retry pattern"
asyncio.Semaphore(10)                  → "semaphore untuk concurrent scan control"
```

**10 Code Patterns yang diextract:**

| Pattern | Deskripsi | Kegunaan AI |
|---------|-----------|-------------|
| `subprocess_capture` | run tool + capture stdout | dasar semua tool execution |
| `subprocess_with_retry` | run dengan exponential backoff | handle network flakiness |
| `subprocess_streaming` | live output dari long process | realtime monitoring |
| `async_concurrent_scan` | scan paralel dengan semaphore | scan banyak target efisien |
| `safe_output_parser` | parse output dengan error handling | process tool results |
| `tool_availability_check` | primary → fallback → skip | graceful degradation |
| `structured_logging` | JSON logging untuk AI-readable trail | audit dan debugging |
| `graceful_error_handling` | try → fallback → log → continue | robust execution |
| `workflow_chaining` | pipe output satu tool ke input tool lain | orchestration |
| `threading_parallel` | ThreadPoolExecutor untuk parallel ops | performance |

**10 Workflow Patterns:**

| Pattern | Chain | Kategori |
|---------|-------|---------|
| recon_chain | subfinder→dnsx→httpx→nmap→nuclei | recon+scan |
| web_assessment | gobuster→whatweb→ffuf→nikto→sqlmap | web |
| ad_enum_chain | bloodhound→kerbrute→impacket→hashcat→evil-winrm | post_exploit |
| cloud_audit | prowler→pacu→trufflehog→scout | cloud |
| ir_response | volatility→autopsy→chainsaw→yara→loki | forensics |
| wireless_attack | kismet→wifite→aircrack→bettercap | wireless |
| malware_analysis | floss→yara→CAPEv2→yarGen | malware |
| evasion_chain | msfvenom→Veil→DefenderCheck→AMSITrigger | evasion |
| social_engineering | GoPhish→evilginx2→SocialFish | social |
| iot_firmware | binwalk→firmwalker→emba→RouterSploit | iot |

---

## STEP 6 — DATASET ARCHITECTURE

### Fungsi setiap dataset:

| Dataset | Fungsi | Isi | Training | Runtime |
|---------|--------|-----|----------|---------|
| `reasoning/` | Cara AI berpikir | threat analysis, context eval, tool selection logic | ✅ | ❌ |
| `planning/` | Multi-step planning | pentest plans, IR plans, audit workflows | ✅ | ❌ |
| `workflow/` | Execution sequence | step-by-step tool chains dengan actual commands | ✅ | ❌ |
| `reflection/` | Self-correction | failure analysis, retry strategies, adaptive logic | ✅ | ❌ |
| `memory/` | Context management | store findings, recall info, update status | ✅ | ✅ |
| `style/` | Output presentation | terminal UI, reports, dashboard format | ✅ | ❌ |
| `tool_metadata/` | Tool knowledge | purpose, input/output, risk, chains (lite) | ✅ | ✅ |
| `code_patterns/` | Coding capability | subprocess/async/retry patterns sebagai Q&A | ✅ | ❌ |
| `workflow_patterns/` | Chain knowledge | full tool chains dengan context | ✅ | ❌ |
| `execution_patterns/` | Runtime logic | Q&A tentang tool selection dan execution | ✅ | ❌ |
| `final/` | Merged training | semua JSONL gabung + shuffle + curriculum order | ✅ | ❌ |

### Dataset untuk Reasoning AI:
```
reasoning/    → fondasi berpikir: "kenapa tool ini, kenapa urutan ini"
reflection/   → adaptive improvement: "apa yang salah, bagaimana perbaiki"
tool_metadata/ → knowledge base: "tool apa untuk task ini"
```

### Dataset untuk Workflow AI:
```
workflow/          → execution sequence: "command apa, urutan apa"
workflow_patterns/ → chaining patterns: "tool A → output → tool B input"
planning/          → multi-step orchestration: "rencana N hari/fase"
```

### Curriculum Learning order (untuk training):
```
1. reasoning/       ← belajar berpikir dulu
2. planning/        ← belajar merancang
3. workflow/        ← belajar execute
4. tool_metadata/   ← belajar tools
5. code_patterns/   ← belajar coding patterns
6. workflow_patterns/ ← belajar chaining
7. execution_patterns/ ← belajar Q&A execution
8. reflection/      ← belajar koreksi diri
9. memory/          ← belajar konteks
10. style/          ← belajar presentasi
11. final/merged    ← semua digabung, shuffle
```

---

## STEP 7 — TRAINING DATA DESIGN

### DATA YANG MASUK TRAINING

```
datasets/reasoning/reasoning.jsonl           ← cara AI berpikir
datasets/planning/planning.jsonl             ← multi-step planning
datasets/workflow/workflow.jsonl             ← execution chains
datasets/reflection/reflection.jsonl        ← self-correction
datasets/memory/memory.jsonl                 ← context management
datasets/style/style.jsonl                   ← output format
datasets/tool_metadata/tool_metadata.jsonl  ← tool knowledge (lite)
datasets/code_patterns/code_patterns.jsonl  ← coding patterns
datasets/workflow_patterns/workflow_patterns.jsonl ← chain patterns
datasets/execution_patterns/execution_patterns.jsonl ← exec Q&A
```

### DATA YANG TIDAK MASUK TRAINING

```
dataraw/                    RAW GITHUB REPOS — terlalu noisy, uncurated
tools/**/*.py               RAW TOOL SCRIPTS — implementation detail
tools/**/*.go/.js/.java     BINARY/OTHER LANG — tidak relevan
*.exe, *.bin, *.so          BINARIES — tidak bisa ditraining
checkpoints/                MODEL WEIGHTS
logs/                       RUNTIME LOGS
memory/session/             SESSION STATE
tool_registry/registry.json FULL REGISTRY — terlalu besar, dipakai runtime
```

### ALASAN PEMISAHAN — Penjelasan Lengkap:

**1. Kenapa raw tools TIDAK ditraining?**

```
Masalah jika langsung training raw code:
- 12,000+ file Python dengan kualitas sangat bervariasi
- Mix: good code, bad code, deprecated code, malicious patterns
- AI akan "hafal" syntax specific tools, bukan memahami workflow
- exploit code yang "dihafal" bisa direproduksi tanpa context
- Overfitting ke syntax tertentu → tidak generalizable

Solusi NEXUS:
- EXTRACT pola (subprocess, retry, async) bukan hafal code
- AI tahu "cara run tool" bukan "isi script tool"
- Generalization >> Memorization
```

**2. Kenapa reasoning lebih penting dari hafalan?**

```
Tanpa reasoning training:
  User: "scan target.com"
  AI: nmap -sV target.com   ← langsung tanpa konteks

Dengan reasoning training:
  User: "scan target.com"
  AI reasoning:
    - "external atau internal?"
    - "sudah ada authorization?"
    - "full port atau common port?"
    - "passive dulu atau langsung active?"
    - "ada IDS/WAF yang perlu dihindari?"
  AI: "Untuk external recon, mulai passive dengan subfinder dulu..."
```

**3. Kenapa pattern extraction penting?**

```
Code patterns = generalized capability:

Pattern "subprocess_capture":
  → AI bisa generate wrapper untuk TOOL APAPUN
  → Termasuk tools yang belum pernah dilihat sebelumnya
  → Bukan hanya nmap, tapi apapun yang punya CLI interface

Pattern "retry_with_backoff":
  → AI tahu cara handle network failure secara general
  → Applicable ke semua network tools
  → Tidak perlu training ulang untuk setiap tool baru
```

**4. Kenapa workflow > syntax hafalan?**

```
Syntax hafalan:
  "nmap -sV -p 80,443 target"   ← hanya tahu command ini

Workflow understanding:
  "Setelah httpx detect live hosts →
   nmap -iL live_hosts.txt untuk service detection →
   feed hasil ke nuclei untuk CVE correlation"

  → AI bisa ADAPT workflow ke situasi baru
  → Kalau nmap tidak tersedia → otomatis fallback ke masscan
  → Kalau target lambat → otomatis adjust timing/rate
```

**5. Kenapa registry digunakan runtime (bukan ditraining)?**

```
Training time registry (SALAH):
  AI hafal: "subfinder tersedia" → tapi di runtime subfinder tidak install!

Runtime registry (BENAR):
  Saat inference: is_available("subfinder") → True/False (real-time check)
  AI plan hanya dengan tools yang ACTUALLY installed
  Environment berbeda = registry berbeda = plan berbeda
  Tidak perlu retrain untuk setiap environment
```

---

## STEP 8 — CONTOH DATASET (JSONL FORMAT)

### reasoning.jsonl
```json
{"instruction":"analisa keamanan web internal 192.168.1.0/24","reasoning":["target internal network → mulai passive recon, hindari noise berlebihan","scope /24 = 256 host → butuh host discovery sebelum detail scan","web assessment → prioritas HTTP/HTTPS services dulu","internal = authorized → scan lebih agresif tapi tetap terkontrol","workflow: discover → fingerprint → vuln scan → report"],"planning":["host discovery: nmap -sn 192.168.1.0/24","port scan top-1000 pada live hosts","HTTP fingerprinting: httpx + whatweb","vulnerability scan: nuclei"],"workflow":["discovery","scan","fingerprint","vuln_assessment","report"],"tools":[{"tool":"nmap","purpose":"host discovery dan port scan"},{"tool":"httpx","purpose":"HTTP probe dan fingerprint"},{"tool":"nuclei","purpose":"vulnerability detection"}],"reflection":"pastikan scope coverage penuh sebelum reporting","memory":"192.168.1.0/24 internal — authorized assessment","style":"structured security analyst","response":"Memulai analisa keamanan internal. Step 1: nmap -sn 192.168.1.0/24"}
```

### planning.jsonl
```json
{"instruction":"rancang pentest plan 5 hari untuk web application e-commerce","reasoning":["hari 1-2: recon dan information gathering","hari 3: active scanning dan vuln assessment","hari 4: exploitation dan PoC","hari 5: cleanup + report"],"planning":["H1: subfinder + amass subdomain mapping","H2: httpx + nuclei fingerprint + quick vuln","H3: nikto + gobuster + sqlmap","H4: manual exploit confirmed findings","H5: report draft + executive summary"],"workflow":["scoping","passive_recon","active_scan","exploitation","report"],"tools":[{"tool":"subfinder","purpose":"subdomain discovery"},{"tool":"nuclei","purpose":"vulnerability scanning"},{"tool":"sqlmap","purpose":"SQL injection testing"}],"reflection":"5 hari tight — prioritaskan high-value targets","memory":"e-commerce: 3 domains, 1 API endpoint","style":"senior penetration tester","response":"Pentest plan 5 hari ready. H1: passive recon dengan subfinder + amass."}
```

### workflow.jsonl
```json
{"instruction":"full recon workflow untuk corp.target.com","reasoning":["passive dulu → zero fingerprint di target logs","validate setiap output sebelum feed ke tool berikutnya"],"planning":["subfinder → dnsx → httpx → nmap → nuclei"],"workflow":["passive_recon","dns_validate","http_probe","port_scan","vuln_scan","report"],"tools":[{"tool":"subfinder","purpose":"subdomain enum"},{"tool":"dnsx","purpose":"DNS resolve"},{"tool":"httpx","purpose":"HTTP probe"},{"tool":"nmap","purpose":"port scan"},{"tool":"nuclei","purpose":"vuln scan"}],"reflection":"chain output file langsung sebagai input untuk efisiensi","memory":"corp.target.com: 45 sub, 32 resolved, 18 live, 5 critical","style":"automated recon workflow","response":"Recon chain: subfinder → dnsx → httpx → nmap → nuclei"}
```

### reflection.jsonl
```json
{"instruction":"sqlmap tidak menemukan SQLi padahal manual test vulnerable","reasoning":["default level=1 miss complex injection","WAF memblock sqlmap UA/patterns","parameter butuh custom tamper"],"planning":["retry level=5 risk=3","tamper=space2comment WAF bypass","manual verify dulu sebelum retry"],"workflow":["retry_higher_level","waf_bypass","manual_verify"],"tools":[{"tool":"sqlmap","purpose":"SQL injection dengan advanced options"}],"reflection":"WAF bypass butuh studi target WAF dulu","memory":"app.target.com — WAF detected, time-based blind confirmed manual","style":"adaptive security tester","response":"Retry: sqlmap --level=5 --tamper=space2comment"}
```

### memory.jsonl
```json
{"instruction":"simpan informasi target dari fase recon ke memory","reasoning":["memory system ingat konteks lintas session","simpan IP, hostname, tech, ports, credentials"],"planning":["extract key findings","kategorisasi: network/services/vulns","simpan dengan tags: target, phase, timestamp"],"workflow":["extract","categorize","store","tag"],"tools":[{"tool":"memory system","purpose":"persistent context across sessions"}],"reflection":"memory terstruktur mempercepat reasoning di session berikutnya","memory":"corp.target.com → nginx 1.18, WordPress 6.1, ports 80/443/22","style":"structured memory agent","response":"Memory stored: corp.target.com — nginx 1.18, WP 6.1, ports 80/443/22 open"}
```

### style.jsonl
```json
{"instruction":"buat report untuk critical vulnerability SQL injection","reasoning":["report: summary + technical + business impact + remediation","executive summary untuk management","technical section untuk developer"],"planning":["Executive Summary → Findings → Technical → Remediation → Appendix","setiap finding: Title, CVSS, Description, PoC, Recommendation"],"workflow":["executive_summary","finding_format","technical_detail","remediation"],"tools":[{"tool":"report system","purpose":"structured security report"}],"reflection":"executive summary max 1 halaman","memory":"CRITICAL: SQLi di /api/login — CVSS 9.8","style":"professional security reporter","response":"## CRITICAL: SQL Injection\\n**CVSS:** 9.8\\n**Impact:** Unauthorized DB access\\n**Fix:** Use prepared statements"}
```

### code_patterns.jsonl (ShareGPT format)
```json
{"conversations":[{"from":"system","value":"Kamu adalah NEXUS — AI Security Operations Agent yang mampu menulis automation script dan memahami execution patterns."},{"from":"human","value":"Berikan contoh pattern subprocess_capture untuk security automation."},{"from":"gpt","value":"**subprocess_capture**\\n\\n**Deskripsi:** Jalankan external tool dan capture output\\n\\n**Use case:** nmap, gobuster, subfinder — tool CLI dengan stdout output\\n\\n```python\\nresult = subprocess.run(\\n    [tool_name] + args,\\n    capture_output=True, text=True, timeout=30\\n)\\nif result.returncode == 0:\\n    return result.stdout.splitlines()\\nraise RuntimeError(result.stderr)\\n```"}]}
```

---

## STEP 9 — RUNTIME EXECUTION SYSTEM

### Struktur dan fungsi setiap module:

```
runtime/
├── tool_executor.py        CORE — semua tool execution via WSL Kali Linux
├── workflow_executor.py    ORCHESTRATOR — multi-step security workflows
├── terminal_controller.py  TERMINAL — persistent bash session management
├── browser_controller.py   BROWSER — open dashboard, reports, CVE pages
├── parser_engine.py        PARSER — nmap XML, nuclei JSON, dll → structured
└── dashboard_launcher.py   DASHBOARD — serve SOC UI + API endpoints
```

### Alur lengkap: AI Request → Tool Execution → Parsed Result

```
AI: "temukan subdomain corp.target.com"
        ↓
[1] tool_executor.select_tools(stage="recon")
    → query registry_lite.json
    → filter: is_available() di WSL
    → result: [subfinder, amass, theHarvester] (yang terinstall)
        ↓
[2] tool_executor.execute("subfinder", ["-d","corp.target.com","-silent"])
    → cmd = ["wsl","-d","kali-linux","-u","root","--","subfinder",...]
    → subprocess.run(cmd, capture_output=True, timeout=120)
    → log ke logs/runtime/executions.jsonl
        ↓
[3] parser_engine.parse("subfinder", stdout)
    → ParseResult: {tool:"subfinder", data:["sub1.corp.target.com",...], count:45}
        ↓
[4] AI menerima structured data
    → reasoning: "45 subdomain ditemukan, lanjut dnsx validation"
    → plan: jalankan dnsx dengan subdomains.txt sebagai input
        ↓
[5] workflow_executor._run(next_steps)
    → chain: dnsx → httpx → nuclei
```

### Tool selection logic:

```python
def select_tools(stage: str, risk_max: str = "high") -> list:
    risk_order = {"low":0, "medium":1, "high":2, "critical":3}
    limit = risk_order[risk_max]
    return [
        t for t in self.registry.values()
        if t["workflow_stage"] == stage           # match task stage
        and risk_order.get(t["risk"],0) <= limit  # within risk tolerance
        and self.is_available(t["tool"])          # actually installed
    ]

# Contoh:
# select_tools("recon", "low") → [subfinder, amass, dnsx, theHarvester]
# select_tools("exploit", "critical") → [metasploit, impacket, pwntools]
# select_tools("exploit", "low") → [] ← gating: tidak ada exploit tools dengan risk=low
```

### WSL execution (semua tools via Kali Linux):

```python
WSL = ["wsl", "-d", "kali-linux", "-u", "root", "--"]

def execute(tool: str, args: list, timeout: int = 60) -> dict:
    cmd = WSL + [tool] + [str(a) for a in args]
    # → ["wsl", "-d", "kali-linux", "-u", "root", "--", "subfinder", "-d", "target.com"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return {
        "success":    proc.returncode == 0,
        "stdout":     proc.stdout,
        "stderr":     proc.stderr,
        "duration":   elapsed,
        "returncode": proc.returncode,
    }
```

### Parser engine (12 tool parsers):

```python
PARSERS = {
    "nmap":      _parse_nmap_xml / _parse_nmap_text,   # auto-detect XML vs text
    "nuclei":    _parse_nuclei,     # JSON lines atau plain text
    "gobuster":  _parse_gobuster,   # /path (Status: 200)
    "subfinder": _parse_subfinder,  # one host per line
    "dnsx":      _parse_subfinder,  # same format
    "httpx":     _parse_httpx,      # JSON lines dengan title/status/tech
    "nikto":     _parse_nikto,      # finding lines
    "whatweb":   _parse_whatweb,    # JSON atau plain text
    "masscan":   _parse_masscan,    # "Discovered open port X/tcp on IP"
    "ffuf":      _parse_ffuf,       # JSON results atau plain
    "hashcat":   _parse_hashcat,    # hash:password pairs
    "sqlmap":    _parse_sqlmap,     # key finding lines
}

# AI menerima structured dict, bukan raw text:
result = parser.parse("nmap", raw_output)
# → ParseResult.data = [{"ip":"10.0.0.50","ports":[{"port":22,"service":"ssh"}]}]
```

---

## STEP 10 — UI & STYLE SYSTEM

### SOC Dashboard Layout:

```
╔══════════════════════════════════════════════════════════════════╗
║  ⬡ NEXUS    AUTONOMOUS SECURITY OPS              ● ONLINE 10:45 ║
╠══════════════╦═══════════════════════════════╦══════════════════╣
║ TOOL REGISTRY║    ACTIVE WORKFLOW             ║ SESSION METRICS   ║
║ 5,300 Tools  ║ ══════════════════════  75%   ║ ✓ Success:  42    ║
║  312 Avail.  ║ [✓] subfinder (2.3s)          ║ ✗ Failed:    3    ║
║──────────────║ [✓] dnsx      (1.1s)          ║ ⬡ Total:    45    ║
║ BY CATEGORY  ║ [►] httpx     running...      ║ ⏱ Time:  312s    ║
║ recon:  340  ║ [ ] nmap      pending         ║──────────────────║
║ scan:   313  ║ [ ] nuclei    pending         ║ RECENT EXECUTIONS ║
║ web:   1498  ║ ─────────────────────────     ║ ✓ nmap    (12s)   ║
║ exploit:4100 ║ Progress: ████████████░░  75% ║ ✓ httpx    (3s)   ║
║ ...          ║───────────────────────────────║ ✓ nuclei  (28s)   ║
║──────────────║     LIVE OUTPUT               ║──────────────────║
║ QUICK ACTIONS║ [10:23] subfinder → 45 subs   ║ AGENT MEMORY      ║
║ ⬡ START RECON║ [10:24] dnsx → 32 resolved   ║ corp.target.com   ║
║ ⬡ WEB ASSESS ║ [10:24] httpx running...      ║ nginx 1.18, WP    ║
║ ⬡ TERMINAL   ║ [!] CRITICAL: CVE-2021-41773  ║ ports: 80/443/22  ║
╚══════════════╩═══════════════════════════════╩══════════════════╝
║ NEXUS v1.0   │  AUTHORIZED SECURITY OPERATIONS  │  2024-01-15   ║
╚══════════════════════════════════════════════════════════════════╝
```

### Color System (Dark Neon):
```css
--bg:     #06060d   /* ultra dark navy — main background */
--panel:  #0d0d18   /* dark panel background */
--cyan:   #00f5ff   /* neon cyan — primary accent, headers */
--green:  #00ff88   /* success, done, low severity */
--red:    #ff3366   /* error, failed, critical severity */
--yellow: #ffcc00   /* warning, medium severity */
--amber:  #ff9900   /* running, active, high severity */
--purple: #9933ff   /* special highlights */
--dim:    #44446a   /* secondary text, metadata */
```

### Terminal Visualization Format:
```
[10:23:45] ══ RECON WORKFLOW: corp.target.com ══

[►] subfinder -d corp.target.com -silent       ← cyan = running
[✓] subfinder → 45 subdomains (2.3s)           ← green = success
[►] dnsx -l subdomains.txt -silent             ← cyan = running
[✓] dnsx → 32 resolved (1.1s)                 ← green = success
[►] httpx -l resolved.txt -silent             ← cyan = running
[✗] httpx → timeout (30s exceeded)            ← red = failed
[!] retry dengan timeout=60s...               ← amber = retry
[✓] httpx → 18 live hosts (60s retry)         ← green = success

Progress: ████████████████░░░░  80%
3/5 steps done │ 63.4s elapsed │ ETA ~20s
```

### Workflow Animation States:
```python
STEP_STATES = {
    "pending":  "[ ]",   # dim white
    "running":  "[►]",   # cyan + pulsing
    "done":     "[✓]",   # green
    "failed":   "[✗]",   # red
    "skipped":  "[~]",   # dim
    "retry":    "[↺]",   # amber
}
```

### Style Training Data Format:

AI OUTPUT harus mengikuti NEXUS style, bukan generic chatbot style:

```
❌ Generic:
"I will now run subfinder to find subdomains. Please wait..."

✅ NEXUS style:
"[►] Memulai passive recon → corp.target.com
 Running: subfinder -d corp.target.com -silent
 ETA: ~30s"

❌ Generic report:
"We found a vulnerability in your application."

✅ NEXUS style:
"## 🔴 CRITICAL: SQL Injection
 CVSS: 9.8 | CVE: N/A
 Location: POST /api/login?username=
 Impact: Full database access
 Fix: Use prepared statements immediately"
```

---

## FULL PIPELINE: Cara Menjalankan

### 1. Isi dataraw/ dengan raw GitHub repos
```bash
# Clone tools ke dataraw/
cd dataraw/
git clone https://github.com/projectdiscovery/subfinder
git clone https://github.com/nmap/nmap
git clone https://github.com/BloodHoundAD/BloodHound
# ... ribuan repos lainnya
```

### 2. Jalankan build pipeline
```bash
# Semua step sekaligus:
python build_all.py

# Atau step by step:
python analyzer/code_analyzer.py       # Step 1: analisa dataraw/
python builder/tool_normalizer.py      # Step 2: normalize + categorize
python builder/registry_builder.py    # Step 3: build registry
python builder/dataset_builder.py     # Step 4: generate training data
python builder/pattern_extractor.py   # Step 5: extract patterns
```

### 3. Validasi dataset
```bash
python training/validation.py
```

### 4. Training (Google Colab)
```bash
# Upload datasets/final/ ke Google Drive
# Buka NEXUS_Colab.ipynb
# Jalankan sel 1-10 secara berurutan
```

### 5. Runtime inference
```python
from runtime.tool_executor import executor
from runtime.workflow_executor import workflow
from runtime.dashboard_launcher import dashboard

dashboard.start(port=8080)      # buka http://localhost:8080
workflow.recon("corp.target.com")   # jalankan recon workflow
```

---

*NEXUS v1.0 — Autonomous Security Operations Agent*
*Untuk: defensive security, authorized assessment, SOC automation, lab environment*
*Bukan untuk: unauthorized intrusion, destructive attacks, mass targeting*
