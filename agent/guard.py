"""Anti-hallucination guard for NEXUS's generated text.

The fine-tuned model is good at language/reasoning but — like any LLM
trained on a small dataset — unreliable at reproducing exact file paths
from memory. This module doesn't try to fix that by training harder; it
catches it after the fact: scan the model's response for any command that
claims to invoke a known tool, and if the invoke prefix doesn't match the
verified real one in registry.json, replace it.

This is deterministic string substitution against ground truth, not another
LLM call — it can't hallucinate, because it only ever copies a value that
was already verified by actually running `which`/scanning the filesystem
(see datagen/build_registry.py).
"""
import re

from registry_lookup import ToolRegistry

# A "wrong invoke" is either a `python3 /some/path/to/script.py`-style prefix,
# or a bare word that isn't already the correct binary name.
_PY_SCRIPT_RE = re.compile(r"python3\s+\S+\.py")


def _extract_candidate_lines(text: str):
    """Pull out anything that looks like an attempted command: ```bash blocks
    with `$ ...` lines, and inline `(python3 ...)` mentions in prose."""
    lines = []
    for block in re.findall(r"```(?:bash)?\n(.*?)```", text, re.DOTALL):
        for line in block.splitlines():
            line = line.strip()
            if line.startswith("$"):
                lines.append(line[1:].strip())
    for m in re.finditer(r"\(((?:python3|[\w./\-]+)[^)]*)\)", text):
        candidate = m.group(1).strip()
        if candidate:
            lines.append(candidate)
    return lines


def check_and_fix(text: str, registry: ToolRegistry | None = None):
    """Returns (corrected_text, corrections) where corrections is a list of
    {tool, wrong, correct} dicts — empty if nothing needed fixing."""
    registry = registry or ToolRegistry()
    corrections = []
    corrected = text

    for line in _extract_candidate_lines(text):
        for entry in registry.find_mentioned(line):
            real_invoke = entry["invoke"]
            if line.lower().startswith(real_invoke.lower()):
                continue  # already correct

            wrong_prefix = None
            m = _PY_SCRIPT_RE.match(line)
            if m:
                wrong_prefix = m.group(0)
            elif line.split(" ", 1)[0].lower() != real_invoke.lower():
                # bare first token doesn't match — e.g. wrong case, wrong binary name
                wrong_prefix = line.split(" ", 1)[0]

            if wrong_prefix is None:
                continue

            fixed_line = real_invoke + line[len(wrong_prefix):]
            if wrong_prefix in corrected:
                corrected = corrected.replace(wrong_prefix, real_invoke)
                corrections.append({
                    "tool": entry["tool"],
                    "wrong": wrong_prefix,
                    "correct": real_invoke,
                })
            break  # one correction per line is enough

    return corrected, corrections


if __name__ == "__main__":
    import sys
    text = sys.stdin.read()
    fixed, fixes = check_and_fix(text)
    if fixes:
        print("=== CORRECTIONS MADE ===")
        for f in fixes:
            print(f"  [{f['tool']}] '{f['wrong']}' -> '{f['correct']}'")
        print()
    print("=== CORRECTED TEXT ===")
    print(fixed)
