"""Ground truth lookup for tool invocation — the ONE place that knows how a
tool is actually run on this machine. Backed by datagen/registry.json, which
was built by actually checking `which <bin>` in WSL and scanning real repo
entrypoints (see datagen/build_registry.py) — every entry here is verified,
none of it is guessed.

The point: the LLM should never have to remember an exact file path. It only
needs to say *which tool*; this module supplies the *real* invoke string.
"""
import json
import re
from pathlib import Path

REGISTRY_PATH = Path(__file__).resolve().parent.parent / "datagen" / "registry.json"


def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


class ToolRegistry:
    def __init__(self, path: Path = REGISTRY_PATH):
        entries = json.loads(path.read_text(encoding="utf-8"))
        self.by_norm_name = {}
        for e in entries:
            self.by_norm_name[_normalize(e["tool"])] = e

    def resolve(self, name: str):
        """Exact (normalized) match only — deliberately no fuzzy guessing here.
        Returns the registry entry dict, or None if this tool isn't registered."""
        return self.by_norm_name.get(_normalize(name))

    def find_mentioned(self, text: str):
        """Every registered tool whose name appears in `text`, longest name first
        (so 'CrackMapExec' matches before a shorter accidental substring would)."""
        hits = []
        for entry in self.by_norm_name.values():
            if entry["tool"].lower() in text.lower():
                hits.append(entry)
        hits.sort(key=lambda e: len(e["tool"]), reverse=True)
        return hits
