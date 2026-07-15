"""Convert the curriculum output (datagen/output/level*.jsonl, all grounded
in real WSL execution) into the ShareGPT format train.py expects:

{"conversations": [{"from":"system",...},{"from":"human",...},{"from":"gpt",...}]}

Every response is structured in explicit stages — [Berpikir] [Tool] [Aksi]
[Observasi] [Kesimpulan] — a condensed version of the classic agent loop
(think -> select tool -> act -> observe -> respond). The point isn't to
teach new facts here; every [Aksi]/[Observasi] pair is still the exact same
real command+output as before. The stage labels teach the MODEL'S OWN
PROCESS: reason before picking a tool, act, look at what actually happened,
then conclude — instead of jumping straight to a command.

Output: data/jsonl/nexus_v2_sharegpt_train.jsonl (90%) + _val.jsonl (10%)
"""
import json
import random
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from common import OUTPUT_DIR, ROOT

OUT_DIR = ROOT / "data" / "jsonl"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SYSTEM_PROMPT = (
    "Kamu adalah NEXUS — AI Security Operations Agent yang otonom. "
    "Kamu memiliki kemampuan reasoning mendalam, multi-step planning, "
    "workflow orchestration, self-reflection, dan memory jangka panjang. "
    "Kamu beroperasi dalam konteks authorized security assessment, "
    "defensive security, SOC automation, dan vulnerability research. "
    "Setiap jawaban ngikutin tahapan: [Berpikir] alasan sebelum bertindak, "
    "[Tool] tool yang dipilih, [Aksi] command yang dijalankan, [Observasi] hasil "
    "nyata, [Kesimpulan] jawaban akhir. JUJUR soal hasil eksekusi nyata — "
    "jangan pernah ngarang command atau output yang gak beneran dijalanin."
)


def code_block(cmd, stdout, stderr, exit_code, max_len=1500):
    out = (stdout or "").strip()
    err = (stderr or "").strip()
    body = out if out else err
    body = body[:max_len]
    status = "sukses" if exit_code == 0 else f"gagal (exit {exit_code})"
    return f"```bash\n$ {cmd}\n```\nStatus: {status}\n```\n{body}\n```"


def bare_invoke(cmd: str) -> str:
    parts = cmd.split()
    if parts and parts[-1] in ("-h", "--help"):
        return " ".join(parts[:-1])
    return cmd


def conv_level1(e):
    tool, category = e["tool"], e["category"]
    human = e["instruction"]
    parts = [
        f"[Berpikir] User nanya cara pakai {tool}, belum ada target/argumen spesifik yang disebut. "
        f"Paling aman cek dulu opsi yang tersedia lewat help sebelum eksekusi beneran ke target.",
        f"[Tool] {tool} ({category}, {e['tool_type']}) — invoke terverifikasi: `{bare_invoke(e['command'])}`",
        f"[Aksi]\n{code_block(e['command'], e['stdout'], e['stderr'], e['exit_code'])}",
    ]
    if e["exit_code"] == 0:
        parts.append(f"[Kesimpulan] {tool} siap dipake, opsi-opsinya udah kelihatan di atas.")
    else:
        parts.append(f"[Kesimpulan] {tool} belum bisa jalan bersih di environment ini — errornya di atas, "
                      f"biasanya dependency yang belum ke-install, bukan salah command.")
    return human, "\n\n".join(parts)


def conv_dep_fix(e):
    tool = e["tool"]
    human = f"jalanin {tool} dong, kalau error dependency benerin sendiri"
    parts = [f"[Berpikir] Coba jalanin {tool} dulu, kalau gagal cek apa errornya cuma soal dependency yang bisa dibenerin sendiri."]
    for step in e["transcript"]:
        if step["step"] == "initial_run" or step["step"].startswith("retry_run"):
            parts.append(f"[Aksi]\n{code_block(step['command'], step.get('stdout', ''), step.get('stderr', ''), step['exit_code'])}")
        elif step["step"].startswith("pip_install"):
            parts.append(f"[Berpikir] Ketauan butuh module `{step['missing_module']}` yang belum ke-install.")
            parts.append(f"[Aksi]\n```bash\n$ {step['command']}\n```")
    if e["resolved"]:
        parts.append(f"[Kesimpulan] {tool} sekarang jalan normal setelah dependency-nya di-install.")
    else:
        parts.append(f"[Kesimpulan] {tool} masih belum bisa jalan sepenuhnya walau udah dicoba install dependency "
                      f"yang keliatan — butuh investigasi manual lebih lanjut (bukan auto-fixable dari pesan errornya doang).")
    return human, "\n\n".join(parts)


def conv_level2(e):
    tool = e["tool"]
    if e["stage"] == "missing_resource_recognition":
        human = e["instruction"]
        parts = [
            f"[Berpikir] Sebelum klaim bisa eksekusi, cek dulu apakah {tool} beneran punya semua yang dibutuhin "
            f"di environment ini sekarang.",
            f"[Kesimpulan] {e['correct_response']}",
        ]
        return human, "\n\n".join(parts)

    human = e["instruction"]
    parts = [
        f"[Berpikir] User minta eksekusi {tool} beneran ke target, bukan cuma liat help."
        + (f" {e['note']}." if e.get("note") else ""),
        f"[Tool] {tool} ({e['category']})",
        f"[Aksi]\n{code_block(e['command'], e['stdout'], e['stderr'], e['exit_code'])}",
    ]
    if e["exit_code"] == 0:
        parts.append(f"[Kesimpulan] Berhasil, ini hasil nyata dari {tool} ke target-nya.")
    else:
        parts.append(f"[Kesimpulan] Gagal (exit {e['exit_code']}) — errornya di atas, itu hasil real bukan simulasi.")
    return human, "\n\n".join(parts)


def conv_level3(e):
    tool = e["tool"]
    human = f"jalanin {tool} ke target"
    m, f = e["mistake"], e["fix"]
    parts = [
        f"[Berpikir] Coba jalanin {tool} dulu.",
        f"[Aksi]\n{code_block(m['command'], m['stdout'], m['stderr'], m['exit_code'])}",
    ]
    if m["exit_code"] != 0:
        parts.append(f"[Berpikir] Ternyata error — {m['diagnosis']}. Perlu command yang bener.")
        parts.append(f"[Aksi]\n{code_block(f['command'], f['stdout'], f['stderr'], f['exit_code'])}")
        parts.append("[Kesimpulan] Setelah dibenerin, dapet hasil valid.")
    else:
        parts.append(f"[Kesimpulan] Ternyata {m['diagnosis']}, jadi tetep dapet hasil valid tanpa perlu dibenerin.")
    return human, "\n\n".join(parts)


def conv_level4(e):
    human = e["instruction"]
    parts = [f"[Berpikir] Ini butuh beberapa langkah nyambung — hasil satu step jadi input step berikutnya, bukan tools independen."]
    for step in e["steps"]:
        parts.append(f"[Tool] Step {step['step']}: {step['goal']}")
        parts.append(f"[Aksi]\n{code_block(step['command'], step['stdout'], step['stderr'], step['exit_code'])}")
    fr = e["final_result"]
    concl = (f"[Kesimpulan] Endpoint `{fr['endpoint_found']}` dengan param `{fr['param_found']}` — "
             f"{'exploit dikonfirmasi beneran ketemu.' if fr['exploit_confirmed'] else 'belum ada exploit yang terkonfirmasi.'}")
    parts.append(concl)
    return human, "\n\n".join(parts)


def conv_level5(e):
    human = e["instruction"]
    parts = [f"[Berpikir] Gak ada tool siap pakai buat ini ({e['registry_gap_confirmed']}), harus tulis sendiri, jalanin, benerin kalau error."]
    for step in e["transcript"]:
        parts.append(f"[Aksi] Percobaan {step['attempt']} — {step['note']}\n```python\n{step['code']}\n```\n"
                      f"```bash\n$ {step['command']}\n```")
        parts.append(f"[Observasi] `{step['stdout'] or step['stderr']}` (exit {step['exit_code']})")
    parts.append("[Kesimpulan] Berhasil ketemu." if e["final_success"] else "[Kesimpulan] Masih belum berhasil, perlu diteruskan.")
    return human, "\n\n".join(parts)


def main():
    examples = []

    for path, conv in [
        (OUTPUT_DIR / "level1_discovery.jsonl", conv_level1),
        (OUTPUT_DIR / "level1b_dep_fix.jsonl", conv_dep_fix),
        (OUTPUT_DIR / "level2_basic_exec.jsonl", conv_level2),
        (OUTPUT_DIR / "level2b_dep_fix.jsonl", conv_dep_fix),
        (OUTPUT_DIR / "level3_error_recovery.jsonl", conv_level3),
        (OUTPUT_DIR / "level4_chaining.jsonl", conv_level4),
        (OUTPUT_DIR / "level5_forge.jsonl", conv_level5),
    ]:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            e = json.loads(line)
            human, gpt = conv(e)
            examples.append({
                "conversations": [
                    {"from": "system", "value": SYSTEM_PROMPT},
                    {"from": "human", "value": human},
                    {"from": "gpt", "value": gpt},
                ]
            })

    random.seed(42)
    random.shuffle(examples)
    split = max(1, int(len(examples) * 0.1))
    val, train = examples[:split], examples[split:]

    train_path = OUT_DIR / "nexus_v2_sharegpt_train.jsonl"
    val_path = OUT_DIR / "nexus_v2_sharegpt_val.jsonl"

    with open(train_path, "w", encoding="utf-8") as f:
        for e in train:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    with open(val_path, "w", encoding="utf-8") as f:
        for e in val:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    print(f"Total: {len(examples)} (train={len(train)}, val={len(val)})")
    print(f"Saved -> {train_path}")
    print(f"Saved -> {val_path}")


if __name__ == "__main__":
    main()
