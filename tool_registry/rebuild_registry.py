"""
NEXUS Tool Registry Builder
Scan semua tools di data/raw_datasets/tool_scripts/ dan build registry.json
dengan entry point yang benar untuk setiap tool.
"""
import json
import os
from pathlib import Path

ROOT = Path(__file__).parent.parent
TOOLS_DIR = ROOT / "data" / "raw_datasets" / "tool_scripts"
OUT = Path(__file__).parent / "registry.json"

# Entry point utama per tool (main script yang dieksekusi)
ENTRY_POINTS = {
    # RECON
    "Sublist3r":      ("sublist3r.py", "-d {domain} -o {output}"),
    "theHarvester":   ("theHarvester.py", "-d {domain} -b all -l 500"),
    "Photon":         ("photon.py", "-u {url} -o {output}"),
    "recon-ng":       ("recon-ng", "--no-version"),

    # SCAN
    "AutoRecon":      ("autorecon.py", "{target}"),
    "nmapAutomator":  ("nmapAutomator.sh", "{target} All"),
    "nmap-vulners":   ("vulners.nse", None),
    "Legion":         ("legion.py", None),

    # WEB
    "sqlmap":         ("sqlmap.py", "-u {url} --batch --dbs"),
    "XSStrike":       ("xsstrike.py", "-u {url}"),
    "dirsearch":      ("dirsearch.py", "-u {url} -e php,html,js,txt"),
    "Arjun":          ("arjun.py", "-u {url}"),
    "PayloadsAllTheThings": (None, None),  # wordlist collection

    # EXPLOIT
    "impacket":       ("setup.py", None),
    "pwntools":       (None, None),  # library
    "BeEF":           ("beef", None),
    "Exploit-Suggester": ("linux-exploit-suggester.sh", None),

    # POST EXPLOIT
    "CrackMapExec":   ("cme", "{protocol} {target} -u {user} -p {pass}"),
    "LinPEAS":        ("linpeas.sh", None),
    "BloodHound":     ("bloodhound-python", "-d {domain} -u {user} -p {pass} -c All"),
    "PowerSploit":    (None, None),
    "nishang":        (None, None),
    "SharpCollection":(None, None),

    # BRUTE FORCE
    "patator":        ("patator.py", "ssh_login host={target} user=FILE0 password=FILE1"),
    "crowbar":        ("crowbar.py", "-b {service} -s {target} -u {user} -C {wordlist}"),
    "Medusa":         ("medusa", "-h {target} -u {user} -P {wordlist} -M {service}"),
    "BruteX":         ("brutex", "{target} {port}"),

    # WIRELESS
    "wifite2":        ("wifite.py", "--wpa --dict {wordlist}"),
    "bettercap":      ("bettercap", "-iface {interface}"),
    "hcxtools":       ("hcxpcapngtool", "{input} -o {output}.hc22000"),
    "Pwnagotchi":     ("pwnagotchi", "--manual"),

    # CLOUD
    "Pacu":           ("cli.py", None),
    "ScoutSuite":     ("scout.py", "--provider {provider}"),
    "Prowler":        ("prowler", "-g cislevel1"),
    "CloudSploit":    ("index.js", None),
    "SkyArk":         ("SkyArk.ps1", None),

    # CRYPTO
    "RsaCtfTool":     ("RsaCtfTool.py", "--publickey {key} --attack all"),
    "hashID":         ("hashid.py", "{hash}"),
    "haiti":          ("haiti", "{hash}"),
    "CyberChef":      (None, None),

    # DEFENSE
    "sigma":          ("sigmac", "-t {backend} {rule}"),
    "Zeek":           ("zeek", "-i {interface}"),
    "Wazuh":          (None, None),
    "YARA-Rules":     (None, None),

    # EVASION
    "Veil":           ("Veil.py", None),
    "charlotte":      ("charlotte.py", "-p {payload} -l {lhost} -o {output}"),
    "Shellter":       ("shellter", None),
    "AMSITrigger":    ("AMSITrigger.exe", None),
    "DefenderCheck":  ("DefenderCheck.exe", "{file}"),

    # FORENSICS
    "volatility3":    ("vol.py", "-f {image} windows.pslist"),
    "autopsy":        ("autopsy", None),
    "chainsaw":       ("chainsaw", "hunt {evtx_dir} --sigma sigma/ --mapping mappings/"),
    "LogonTracer":    ("logontracer.py", "-r {evtx} -z -u {user}"),
    "KAPE":           ("kape.exe", "--tsource {source} --tdest {dest}"),

    # MALWARE
    "yarGen":         ("yarGen.py", "-m {malware_dir} -o {output}.yar"),
    "maltrail":       ("server.py", None),
    "CAPEv2":         ("cape.py", None),
    "Quasar":         (None, None),

    # SOCIAL
    "GoPhish":        ("gophish", None),
    "evilginx2":      ("evilginx", None),
    "SocialFish":     ("SocialFish.py", "{template}"),
    "PhEmail":        ("phEmail.py", "-t {target}"),

    # IOT
    "RouterSploit":   ("rsf.py", None),
    "binwalk":        ("binwalk", "-e {firmware}"),
    "firmwalker":     ("firmwalker.sh", "{firmware_dir}"),
    "FACT_core":      ("start_fact.py", None),
    "emba":           ("emba.sh", "-f {firmware} -l {log_dir}"),
}

CATEGORY_TOOLS = {
    "recon":       ["Sublist3r", "theHarvester", "Photon", "recon-ng"],
    "scan":        ["AutoRecon", "nmapAutomator", "nmap-vulners", "Legion"],
    "web":         ["sqlmap", "XSStrike", "dirsearch", "Arjun", "PayloadsAllTheThings"],
    "exploit":     ["impacket", "pwntools", "BeEF", "Exploit-Suggester"],
    "post_exploit":["CrackMapExec", "LinPEAS", "BloodHound", "PowerSploit", "nishang"],
    "brute_force": ["patator", "crowbar", "Medusa", "BruteX"],
    "wireless":    ["wifite2", "bettercap", "hcxtools", "Pwnagotchi"],
    "cloud":       ["Pacu", "ScoutSuite", "Prowler", "CloudSploit", "SkyArk"],
    "crypto":      ["RsaCtfTool", "hashID", "haiti", "CyberChef"],
    "defense":     ["sigma", "Zeek", "Wazuh", "YARA-Rules"],
    "evasion":     ["Veil", "charlotte", "Shellter", "AMSITrigger", "DefenderCheck"],
    "forensics":   ["volatility3", "autopsy", "chainsaw", "LogonTracer", "KAPE"],
    "malware":     ["yarGen", "maltrail", "CAPEv2", "Quasar"],
    "social":      ["GoPhish", "evilginx2", "SocialFish", "PhEmail"],
    "iot":         ["RouterSploit", "binwalk", "firmwalker", "FACT_core", "emba"],
}

def build():
    registry = []
    for category, tools in CATEGORY_TOOLS.items():
        for tool_name in tools:
            tool_dir = TOOLS_DIR / category / tool_name
            entry_script, usage = ENTRY_POINTS.get(tool_name, (None, None))

            # Build full path
            if entry_script and tool_dir.exists():
                full_path = tool_dir / entry_script
                exec_cmd = f"python3 {full_path}" if str(full_path).endswith('.py') else str(full_path)
            else:
                exec_cmd = tool_name.lower()  # assume installed in PATH

            registry.append({
                "tool": tool_name,
                "category": category,
                "path": str(tool_dir) if tool_dir.exists() else None,
                "exec": exec_cmd,
                "usage": usage or "see --help",
                "available": tool_dir.exists(),
            })

    with open(OUT, "w") as f:
        json.dump(registry, f, indent=2)

    print(f"[+] Registry built: {len(registry)} tools")
    available = sum(1 for t in registry if t["available"])
    print(f"[+] Available locally: {available}/{len(registry)}")
    for cat, tools in CATEGORY_TOOLS.items():
        avail = sum(1 for t in tools if (TOOLS_DIR/cat/t).exists())
        print(f"    {cat}: {avail}/{len(tools)}")

if __name__ == "__main__":
    build()
