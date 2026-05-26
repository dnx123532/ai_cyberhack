"""
NEXUS — Tool Executor
Semua eksekusi tool melalui WSL Kali Linux.
Features: availability caching, bounded log, streaming output.
"""

import subprocess, time
from collections import deque

from shared.utils import get_logger, root, load_json, append_jsonl

logger = get_logger("nexus.executor")

REGISTRY_PATH = root("tool_registry", "registry.json")
LOG_PATH      = root("logs", "runtime", "executions.jsonl")
WSL           = ["wsl", "-d", "kali-linux", "-u", "root", "--"]


class ToolExecutor:
    def __init__(self):
        self.registry    = self._load_registry()
        # bounded in-memory log — prevents unbounded memory growth on long runs
        self.exec_log    = deque(maxlen=1000)
        # cache tool availability — avoids spawning `which` on every selection
        self._avail_cache: dict[str, bool] = {}

    def _load_registry(self) -> dict:
        data = load_json(REGISTRY_PATH, default=[])
        if not data:
            logger.warning("Registry empty — run builder/registry_builder.py first")
        return {t["tool"]: t for t in data}

    # ── Tool availability ─────────────────────────────────────────────────────

    def is_available(self, tool: str) -> bool:
        """Check tool availability via WSL `which`. Result is cached per session."""
        if tool not in self._avail_cache:
            result = subprocess.run(
                WSL + ["which", tool],
                capture_output=True, text=True
            )
            self._avail_cache[tool] = result.returncode == 0
        return self._avail_cache[tool]

    def warm_availability_cache(self, tools: list[str]):
        """Pre-check a list of tools in parallel to warm the cache."""
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            pool.map(self.is_available, tools)

    # ── Tool info ─────────────────────────────────────────────────────────────

    def get_info(self, tool: str) -> dict | None:
        return self.registry.get(tool)

    def select_tools(self, stage: str, risk_max: str = "high") -> list[dict]:
        """Return available tools matching workflow stage and risk threshold."""
        risk_order = {"low":0,"medium":1,"high":2,"critical":3}
        limit = risk_order.get(risk_max, 2)
        return [
            t for t in self.registry.values()
            if t["workflow_stage"] == stage
            and risk_order.get(t["risk"], 0) <= limit
            and self.is_available(t["tool"])
        ]

    # ── Execution ─────────────────────────────────────────────────────────────

    def execute(self, tool: str, args: list,
                timeout: int = 60, stream: bool = False) -> dict:
        cmd   = WSL + [tool] + [str(a) for a in args]
        start = time.time()
        logger.info(f"exec: {' '.join(cmd)}")

        try:
            if stream:
                result = self._run_streaming(cmd)
            else:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
                result = {
                    "returncode": proc.returncode,
                    "stdout"    : proc.stdout,
                    "stderr"    : proc.stderr,
                    "success"   : proc.returncode == 0,
                }
        except subprocess.TimeoutExpired:
            result = {"returncode":-1,"stdout":"","stderr":f"TIMEOUT after {timeout}s","success":False}
        except FileNotFoundError:
            result = {"returncode":-1,"stdout":"","stderr":"WSL not found","success":False}
        except Exception as e:
            result = {"returncode":-1,"stdout":"","stderr":str(e),"success":False}

        record = {"tool":tool,"args":args,"duration":round(time.time()-start,2),**result}
        self.exec_log.append(record)
        append_jsonl(LOG_PATH, record)
        return record

    def _run_streaming(self, cmd: list) -> dict:
        lines = []
        proc  = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in proc.stdout:
            line = line.rstrip()
            print(f"  {line}")
            lines.append(line)
        proc.wait()
        return {"returncode":proc.returncode,"stdout":"\n".join(lines),"stderr":"",
                "success":proc.returncode==0}

    def execute_chain(self, chain: list) -> list:
        """Run a list of {tool, args, timeout?, stop_on_fail?} steps sequentially."""
        results = []
        for step in chain:
            r = self.execute(step["tool"], step.get("args",[]),
                             timeout=step.get("timeout",120), stream=step.get("stream",False))
            results.append(r)
            if not r["success"] and step.get("stop_on_fail", False):
                logger.warning(f"Chain stopped at {step['tool']} — execution failed")
                break
        return results


# Singleton — import this in other modules
executor = ToolExecutor()
