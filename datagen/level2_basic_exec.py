"""Level 2 — Basic Correct Execution.

Reuses the exact invoke strings verified in Level 1, now with real
arguments against an authorized safe target:
  - testphp.vulnweb.com  (Acunetix's public intentionally-vulnerable test
    site, provided specifically for security-tool testing)
  - 127.0.0.1            (local, zero external traffic)

Tools that need a resource this environment doesn't have (a memory dump,
cloud credentials, a wireless interface, a GUI) are NOT faked — they're
recorded as "missing_resource" examples instead. That's a real skill too:
recognizing what a tool needs before claiming it can run.
"""
import json

from common import OUTPUT_DIR, load_registry, run_wsl, reset_jsonl, append_jsonl

OUT_PATH = OUTPUT_DIR / "level2_basic_exec.jsonl"

WEB_TARGET = "http://127.0.0.1:5000"  # local vulnapp.py test lab (see testlab/), 100% reliable
DOMAIN_TARGET = "scanme.nmap.org"     # Nmap project's explicitly-authorized public test domain

# (category, tool) -> (args string appended to the verified invoke, timeout seconds, note)
# Only tools with a genuinely safe, bounded, real command are included here.
TOOL_ARGS = {
    ("recon", "theHarvester"): ("-d {domain} -l 50 -b crtsh", 75,
        "passive-only source (crt.sh), no API key needed, no active scanning"),
    ("recon", "Sublist3r"): ("-d {domain}", 60, "passive subdomain enum"),
    ("web", "dirsearch"): ("-u {web} -w /mnt/e/agent_cyberhack/datagen/testlab/wordlist.txt --timeout 5 -t 5", 60,
        "custom small wordlist matching the local test app's real routes"),
    ("web", "Arjun"): ("-u {web}/profile", 60, "param discovery against an endpoint with one real hidden param (token)"),
    ("web", "XSStrike"): ("-u \"{web}/search?q=test\" --skip-dom", 60, "q is reflected unescaped -> real XSS test target"),
    ("crypto", "hashID"): ("5f4dcc3b5aa765d61d8327deb882cf99", 15,
        "offline hash-type identification, zero network"),
    ("brute_force", "crowbar"): ("-b sshkey -s 127.0.0.1/32 -u root -k /nonexistent", 20,
        "points at a local port with nothing listening -> real connection-refused, not a live brute-force"),
    ("post_exploit", "CrackMapExec"): ("smb 127.0.0.1", 20,
        "local host with no SMB service -> real negative result, safe"),
    ("brute_force", "patator"): (
        "http_fuzz url=\"{web}/profile?token=FILE0\" 0=/mnt/e/agent_cyberhack/datagen/testlab/tokens.txt "
        "-x ignore:fgrep='who are you'", 60,
        "brute-forces the same /profile?token= param from Level 5, via a real tool this time instead of a hand-written script"),
    ("recon", "Photon"): ("-u {web} -l 1 -t 5 --timeout 5", 30, "shallow crawl (level=1) of the local test lab"),
    ("recon", "recon-ng"): ("-w nexus_test -r /mnt/e/agent_cyberhack/datagen/testlab/reconng.rc --no-marketplace", 30,
        "batch mode via resource file (-r), no interactive shell, no API keys needed for these commands"),
    # sqlmap LAST: its heavy time-based/blind payloads can crash the lightweight
    # Flask dev server (observed: RANDOMBLOB-based payloads killed it mid-run),
    # so every other tool gets a turn against a healthy server first.
    ("web", "sqlmap"): ("-u \"{web}/product?id=1\" --batch --level=1 --risk=1", 90,
        "--batch avoids interactive prompts; id is raw-concatenated into SQL -> real injection point"),
}

MISSING_RESOURCE = {
    ("forensics", "volatility3"): "butuh file memory dump (-f image.raw) yang gak ada di environment ini",
    ("cloud", "ScoutSuite"): "butuh AWS/Azure/GCP credentials yang gak dikonfigurasi di environment ini",
    ("cloud", "Prowler"): "butuh cloud provider credentials yang gak dikonfigurasi di environment ini",
    ("wireless", "wifite2"): "butuh wireless interface dalam monitor mode, gak ada NIC fisik di WSL",
    ("iot", "RouterSploit"): "butuh target device IoT nyata untuk exploit modules-nya",
    ("social", "SocialFish"): "spin up phishing server, butuh domain/hosting setup eksplisit, di luar scope demo aman",
    ("malware", "maltrail"): "sensor butuh network capture privilege & interface khusus",
    ("crypto", "RsaCtfTool"): "butuh file kunci RSA (public key/cipher) sebagai target analisis",
    ("cloud", "Pacu"): "butuh AWS credentials yang gak dikonfigurasi di environment ini",
    ("evasion", "charlotte"): "ini tool builder buat Windows DLL shellcode (C++), gak ada mode eksekusi CLI nyata buat testing di Linux/WSL — cuma nampilin banner info doang",
    ("forensics", "LogonTracer"): "butuh Windows Event Log (EVTX) asli buat dianalisis, gak ada sample di environment ini",
    ("malware", "yarGen"): "butuh sample malware + goodware database yang harus didownload dulu (proses lama, di luar scope demo cepat)",
    ("scan", "AutoRecon"): "butuh TTY interaktif buat live keyboard input pas scanning (termios.tcgetattr gagal kalau dipanggil non-interaktif/headless) — sudah dicoba 3x termasuk --ignore-plugin-checks, konsisten gagal di titik yang sama",
}


def main():
    registry = {(e["category"], e["tool"]): e for e in load_registry()}
    reset_jsonl(OUT_PATH)

    executed, missing = 0, 0

    for (category, tool), (args_tpl, timeout, note) in TOOL_ARGS.items():
        entry = registry.get((category, tool))
        if not entry or entry["type"] not in ("system", "local"):
            continue
        args = args_tpl.format(domain=DOMAIN_TARGET, web=WEB_TARGET)
        cmd = f"{entry['invoke']} {args}"
        stdout, stderr, code = run_wsl(cmd, timeout=timeout)

        example = {
            "level": 2,
            "stage": "basic_execution",
            "category": category,
            "tool": tool,
            "instruction": f"jalanin {tool} ke target {DOMAIN_TARGET if 'domain' in args_tpl or '{domain}' in args_tpl else WEB_TARGET}, real run bukan simulasi",
            "command": cmd,
            "note": note,
            "stdout": stdout[:8000],
            "stderr": stderr[:2000],
            "exit_code": code,
            "verified_real_execution": True,
        }
        append_jsonl(OUT_PATH, example)
        executed += 1
        print(f"[exec] {category}/{tool} -> exit={code}, output_len={len(stdout)+len(stderr)}")

    for (category, tool), reason in MISSING_RESOURCE.items():
        entry = registry.get((category, tool))
        if not entry:
            continue
        example = {
            "level": 2,
            "stage": "missing_resource_recognition",
            "category": category,
            "tool": tool,
            "instruction": f"jalanin {tool} sekarang",
            "correct_response": f"{tool} ada dan bisa dipanggil ({entry['invoke']}), tapi {reason}. "
                                 f"Gak bisa jalan sampe resource itu disediain — bukan tool-nya yang error.",
            "verified_real_execution": False,
            "reasoning_grounded_in": "level1 -h output + tool's documented required arguments",
        }
        append_jsonl(OUT_PATH, example)
        missing += 1
        print(f"[resource-check] {category}/{tool} -> missing resource documented")

    print(f"\nExecuted: {executed}, Missing-resource examples: {missing}")
    print(f"Saved -> {OUT_PATH}")


if __name__ == "__main__":
    main()
