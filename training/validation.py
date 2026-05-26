"""
NEXUS Dataset Validator
Usage: python training/validation.py --file data/jsonl/nexus_v2_sharegpt_train.jsonl --save
"""
import sys, json, hashlib, argparse
from pathlib import Path
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")

class DatasetValidator:
    def __init__(self, path, fmt="sharegpt"):
        self.path = Path(path); self.fmt = fmt
        self.errors = []; self.warnings = []; self.stats = defaultdict(int); self.hashes = set()

    def validate(self):
        print(f"\n{'='*55}\n  NEXUS Dataset Validator\n  File: {self.path.name}  Format: {self.fmt}\n{'='*55}\n")
        if not self.path.exists(): raise FileNotFoundError(self.path)
        lines = self.path.read_text(encoding="utf-8").splitlines()
        self.stats["total_lines"] = len(lines)
        token_lengths = []
        required = {"sharegpt":["conversations"],"alpaca":["instruction","output"]}.get(self.fmt,["text"])

        for ln, line in enumerate(lines, 1):
            line = line.strip()
            if not line: self.stats["empty_lines"] += 1; continue
            try: entry = json.loads(line)
            except json.JSONDecodeError as e:
                self.errors.append({"line":ln,"type":"INVALID_JSON","detail":str(e)}); self.stats["invalid_json"] += 1; continue
            missing = [f for f in required if f not in entry]
            if missing:
                self.errors.append({"line":ln,"type":"MISSING_FIELDS","detail":str(missing)}); self.stats["missing_fields"] += 1; continue
            text = self._extract(entry)
            if not text: self.warnings.append({"line":ln,"type":"MALFORMED"}); self.stats["malformed"] += 1; continue
            if len(text) < 20: self.stats["too_short"] += 1
            est = len(text)//4; token_lengths.append(est)
            if est > 2048: self.stats["exceeds_tokens"] += 1
            h = hashlib.md5(text.encode()).hexdigest()
            if h in self.hashes: self.stats["duplicates"] += 1
            else: self.hashes.add(h); self.stats["unique_entries"] += 1
            self.stats["valid_entries"] += 1

        if token_lengths:
            self.stats.update({"token_min":min(token_lengths),"token_max":max(token_lengths),
                               "token_mean":int(sum(token_lengths)/len(token_lengths))})
        self._print(); return {"stats":dict(self.stats),"errors":self.errors,"warnings":self.warnings,
                               "is_valid":(self.stats["invalid_json"]+self.stats["missing_fields"])==0}

    def _extract(self, e):
        if self.fmt=="sharegpt":
            c=e.get("conversations",[])
            return " ".join(x.get("value","") for x in c if isinstance(x,dict)) if len(c)>=2 else None
        return e.get("instruction","")+e.get("output","") if self.fmt=="alpaca" else e.get("text","")

    def _print(self):
        s=self.stats
        print(f"  Total     : {s['total_lines']}  Valid: {s['valid_entries']}  Unique: {s['unique_entries']}")
        print(f"  Errors    : JSON={s['invalid_json']}  Fields={s['missing_fields']}")
        print(f"  Warnings  : Dupes={s['duplicates']}  Short={s['too_short']}  Tokens={s['exceeds_tokens']}")
        if s.get("token_mean"): print(f"  Tokens    : min={s['token_min']} mean={s['token_mean']} max={s['token_max']}")
        errs=s["invalid_json"]+s["missing_fields"]
        print(f"\n  {'✅ VALID — siap training' if errs==0 else f'❌ {errs} ERRORS — fix dulu!'}\n")

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--file",default="data/jsonl/nexus_v2_sharegpt_train.jsonl")
    p.add_argument("--format",default="sharegpt",choices=["alpaca","sharegpt","chatml","raw"])
    p.add_argument("--save",action="store_true")
    args=p.parse_args()
    v=DatasetValidator(args.file,fmt=args.format); report=v.validate()
    if args.save:
        out=Path("data/validation/validation_report.json"); out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
        print(f"  Saved: {out}")
    sys.exit(0 if report["is_valid"] else 1)
