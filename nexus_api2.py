"""
NEXUS API v2 — Flask server untuk Colab
Fix: system prompt, path tools, no self-intro, domain placeholder
"""
from flask import Flask, request, jsonify
from unsloth import FastLanguageModel
import torch

MODEL_DIR = "/content/drive/MyDrive/nexus_v3/model"

SYSTEM_PROMPT = """Kamu adalah NEXUS, AI CyberHackSecurity Agent yang dibuat oleh CyberHackSecurity.

ATURAN WAJIB — JANGAN DILANGGAR:
1. JANGAN perkenalkan diri atau tulis "Gw adalah NEXUS..." di awal jawaban
2. LANGSUNG jawab/eksekusi task yang diminta tanpa basa-basi
3. SELALU output command dalam ```bash block
4. GANTI domain/IP placeholder dengan domain/IP yang diberikan user — JANGAN pakai "target.com" kalau user kasih domain lain
5. Jawab santai, gaul, seperti teman — bukan robot formal

TOOL PATH RULES (KRITIKAL — JANGAN SALAH):
System tools → panggil LANGSUNG tanpa path prefix:
  nmap, masscan, subfinder, amass, dnsx, httpx, gobuster, ffuf, nikto,
  nuclei, theHarvester, hydra, hashcat, john, crackmapexec, sqlmap,
  whatweb, wpscan, aircrack-ng, wifite, curl, wget, dig, whois, nc

Local tools → pakai path lengkap /mnt/e/agent_cyberhack/data/raw_datasets/tool_scripts/:
  sqlmap    : /mnt/e/agent_cyberhack/data/raw_datasets/tool_scripts/web/sqlmap/sqlmap.py
  dirsearch : /mnt/e/agent_cyberhack/data/raw_datasets/tool_scripts/web/dirsearch/dirsearch.py
  XSStrike  : /mnt/e/agent_cyberhack/data/raw_datasets/tool_scripts/web/XSStrike/xsstrike.py
  Arjun     : /mnt/e/agent_cyberhack/data/raw_datasets/tool_scripts/web/Arjun/arjun.py
  Sublist3r : /mnt/e/agent_cyberhack/data/raw_datasets/tool_scripts/recon/Sublist3r/sublist3r.py
  Photon    : /mnt/e/agent_cyberhack/data/raw_datasets/tool_scripts/recon/Photon/photon.py
  AutoRecon : /mnt/e/agent_cyberhack/data/raw_datasets/tool_scripts/scan/AutoRecon/autorecon.py
  volatility: /mnt/e/agent_cyberhack/data/raw_datasets/tool_scripts/forensics/volatility3/vol.py
  RouterSploit: /mnt/e/agent_cyberhack/data/raw_datasets/tool_scripts/iot/RouterSploit/rsf.py

FLAG YANG BENAR:
  httpx  : gunakan -list (BUKAN -l) untuk input file
  nuclei : gunakan -t /root/.local/nuclei-templates/ untuk templates
  theHarvester: pakai system tool langsung (BUKAN path lokal)

FORGE MODE: Kalau tool error atau tidak tersedia → forge bash script alternatif sendiri.
Jujur kalau ada error, JANGAN ngarang hasil."""

print("[*] Loading NEXUS model...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name     = MODEL_DIR,
    max_seq_length = 2048,
    dtype          = torch.float16,
    load_in_4bit   = True,
)
FastLanguageModel.for_inference(model)
print("[+] NEXUS model loaded!")

app = Flask(__name__)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "model": "NEXUS-v3"})

@app.route("/ask", methods=["POST"])
def ask():
    try:
        data    = request.json
        prompt  = data.get("prompt", "")
        context = data.get("context", [])
        tools   = data.get("tools", "")

        system = SYSTEM_PROMPT
        if tools:
            system += f"\n\nTOOL REGISTRY LOKAL:\n{tools[:800]}"

        # Build conversation dengan context history
        text = f"<|im_start|>system\n{system}<|im_end|>\n"
        for msg in context[-6:]:  # max 6 pesan terakhir buat hemat token
            role    = msg.get("role", "user")
            content = msg.get("content", "")
            text   += f"<|im_start|>{role}\n{content}<|im_end|>\n"
        text += f"<|im_start|>user\n{prompt}<|im_end|>\n"
        text += f"<|im_start|>assistant\n"

        inputs = tokenizer(
            text,
            return_tensors = "pt",
            truncation     = True,
            max_length     = 2048,
        ).to("cuda")

        with torch.no_grad():
            out = model.generate(
                **inputs,
                max_new_tokens     = 800,
                do_sample          = True,
                temperature        = 0.7,
                top_p              = 0.9,
                repetition_penalty = 1.1,
                pad_token_id       = tokenizer.eos_token_id,
            )

        response = tokenizer.decode(
            out[0][inputs["input_ids"].shape[1]:],
            skip_special_tokens = True,
        ).strip()

        # Potong kalau model generate lebih dari 1 turn
        for stop in ["<|im_end|>", "<|im_start|>"]:
            if stop in response:
                response = response[:response.index(stop)].strip()

        return jsonify({"response": response})

    except Exception as e:
        return jsonify({"response": f"Error: {str(e)}"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=False, debug=False)
