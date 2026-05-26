# NEXUS — AI CyberHack Operations Agent

```
███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗
████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝
██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗
██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║
██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝███████║
╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝
```

Autonomous AI Cybersecurity Operations Agent dengan:
- 🧠 Reasoning engine (Chain-of-Thought)
- 🗺️ Multi-step attack & defense planning
- ⚙️ Workflow orchestration + autonomous tool execution
- 🔁 Self-correction & reflection
- 💾 Long-term contextual memory
- 🛠️ 5328 cybershack tools (15 kategori)
- 🖥️ Terminal + browser controller
- 📊 Realtime monitoring dashboard

---

## Quick Start (Google Colab)

```python
from google.colab import drive
drive.mount('/content/drive')

!git clone https://github.com/dnx123532/ai_cyberhack.git /content/ai_cyberhack
%cd /content/ai_cyberhack

!pip install -q transformers peft trl bitsandbytes datasets accelerate sentencepiece

!python training/train.py
```

---

## Pipeline

```bash
# 1. Analisa raw tools
python analyzer/code_analyzer.py

# 2. Build tool registry
python builder/registry_builder.py

# 3. Extract code/workflow patterns
python builder/pattern_extractor.py

# 4. Build training datasets
python scripts/v2/build_all.py
python scripts/v2/convert_jsonl.py

# 5. Validate dataset
python training/validation.py --file data/jsonl/nexus_v2_sharegpt_train.jsonl

# 6. Train (Google Colab T4)
python training/train.py
```

---

## Dataset

| Phase | Entries | Fungsi |
|-------|---------|--------|
| reasoning | 30 | CoT thinking |
| planning | 23 | Multi-step planning |
| workflow | 25 | Tool execution |
| reflection | 25 | Self-correction |
| memory | 82 | Context retention |
| style | 23 | Communication |
| tools | 5328 | Tool knowledge |
| final_merged | 12 | Integrated agent |

Training format: **ShareGPT JSONL** (compatible HuggingFace/TRL)

---

## 15 Tool Categories

`recon` · `scanner` · `web` · `exploitation` · `post_exploitation`
`brute_force` · `password` · `network` · `wireless` · `forensics`
`malware_analysis` · `osint` · `cloud` · `mobile_iot` · `reporting`

---

*For authorized penetration testing and cybersecurity research only.*
