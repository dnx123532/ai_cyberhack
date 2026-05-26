"""
NEXUS — Terminal Controller
Open dan control terminal untuk menjalankan tools via WSL Kali Linux.
Supports: Windows Terminal, cmd, PowerShell + WSL integration.
"""

import subprocess, threading, queue, time
from pathlib import Path
from typing import Callable

from shared.utils import get_logger, root, append_jsonl

logger      = get_logger("nexus.terminal")
TERM_LOG    = root("logs", "runtime", "terminal.jsonl")

WSL         = ["wsl", "-d", "kali-linux", "-u", "root", "--"]
TERM_APPS   = ["wt", "cmd"]          # Windows Terminal preferred


class TerminalSession:
    """
    Interactive terminal session via WSL subprocess.
    Maintains a long-running bash process for stateful command execution.
    """

    def __init__(self, session_id: str = "nexus"):
        self.session_id  = session_id
        self.proc        = None
        self._out_queue  = queue.Queue()
        self._reader     = None
        self._alive      = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> bool:
        """Start a persistent bash session inside WSL."""
        try:
            self.proc = subprocess.Popen(
                WSL + ["bash", "--norc", "--noprofile"],
                stdin  = subprocess.PIPE,
                stdout = subprocess.PIPE,
                stderr = subprocess.STDOUT,
                text   = True,
                bufsize= 1,
            )
            self._alive  = True
            self._reader = threading.Thread(target=self._read_loop, daemon=True)
            self._reader.start()
            logger.info(f"Terminal session '{self.session_id}' started (pid={self.proc.pid})")
            return True
        except FileNotFoundError:
            logger.error("WSL not found — install WSL + kali-linux distro")
            return False
        except Exception as e:
            logger.error(f"Terminal start failed: {e}")
            return False

    def stop(self):
        """Terminate the bash session."""
        self._alive = False
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.stdin.write("exit\n")
                self.proc.stdin.flush()
                self.proc.wait(timeout=5)
            except Exception:
                self.proc.kill()
        logger.info(f"Terminal session '{self.session_id}' stopped")

    # ── Command execution ─────────────────────────────────────────────────────

    def run(self, command: str, timeout: int = 60) -> dict:
        """
        Execute a command in the persistent bash session.
        Returns {command, output, returncode, duration}.
        """
        if not self._alive or not self.proc:
            if not self.start():
                return {"command": command, "output": "", "returncode": -1,
                        "success": False, "stderr": "Terminal not started"}

        start   = time.time()
        sentinel = f"__NEXUS_EXIT_{int(time.time())}__"

        # Clear stale output
        while not self._out_queue.empty():
            self._out_queue.get_nowait()

        # Send command + echo sentinel with return code
        try:
            self.proc.stdin.write(f"{command}\n")
            self.proc.stdin.write(f'echo "{sentinel}:$?"\n')
            self.proc.stdin.flush()
        except BrokenPipeError:
            self._alive = False
            return {"command": command, "output": "", "returncode": -1,
                    "success": False, "stderr": "Broken pipe — session died"}

        lines    = []
        retcode  = -1
        deadline = time.time() + timeout

        while time.time() < deadline:
            try:
                line = self._out_queue.get(timeout=0.1)
                if sentinel in line:
                    try:
                        retcode = int(line.split(":")[-1])
                    except ValueError:
                        retcode = 0
                    break
                lines.append(line)
            except queue.Empty:
                if self.proc.poll() is not None:
                    break

        duration = round(time.time() - start, 2)
        output   = "\n".join(lines)
        record   = {
            "session"    : self.session_id,
            "command"    : command,
            "output"     : output,
            "returncode" : retcode,
            "success"    : retcode == 0,
            "duration"   : duration,
        }
        append_jsonl(TERM_LOG, record)
        return record

    def run_stream(self, command: str, callback: Callable[[str], None],
                   timeout: int = 120):
        """Run command and stream each output line to callback."""
        if not self._alive or not self.proc:
            if not self.start():
                callback("[ERROR] Terminal not started")
                return

        sentinel = f"__NEXUS_STREAM_{int(time.time())}__"
        while not self._out_queue.empty():
            self._out_queue.get_nowait()

        try:
            self.proc.stdin.write(f"{command}\n")
            self.proc.stdin.write(f'echo "{sentinel}"\n')
            self.proc.stdin.flush()
        except BrokenPipeError:
            callback("[ERROR] Session died")
            return

        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                line = self._out_queue.get(timeout=0.1)
                if sentinel in line:
                    break
                callback(line)
            except queue.Empty:
                if self.proc.poll() is not None:
                    break

    # ── Internal reader ───────────────────────────────────────────────────────

    def _read_loop(self):
        """Background thread: read stdout and push to queue."""
        try:
            for line in self.proc.stdout:
                self._out_queue.put(line.rstrip())
        except (ValueError, OSError):
            pass
        finally:
            self._alive = False

    @property
    def is_alive(self) -> bool:
        return self._alive and (self.proc is not None) and (self.proc.poll() is None)


class TerminalController:
    """
    High-level controller: manage multiple named sessions.
    """

    def __init__(self):
        self._sessions: dict[str, TerminalSession] = {}

    def session(self, name: str = "default") -> TerminalSession:
        """Get or create a named session."""
        if name not in self._sessions or not self._sessions[name].is_alive:
            s = TerminalSession(session_id=name)
            s.start()
            self._sessions[name] = s
        return self._sessions[name]

    def run(self, command: str, session: str = "default",
            timeout: int = 60) -> dict:
        return self.session(session).run(command, timeout=timeout)

    def run_stream(self, command: str, callback: Callable[[str], None],
                   session: str = "default", timeout: int = 120):
        self.session(session).run_stream(command, callback, timeout=timeout)

    def open_window(self, title: str = "NEXUS Terminal") -> bool:
        """Open a visible Windows Terminal window with WSL Kali."""
        for app in TERM_APPS:
            try:
                if app == "wt":
                    subprocess.Popen(
                        ["wt", "-p", "kali-linux", "--title", title],
                        creationflags=subprocess.DETACHED_PROCESS,
                    )
                else:
                    subprocess.Popen(
                        ["cmd", "/c", "start", "cmd", "/k",
                         "wsl -d kali-linux -u root"],
                        shell=True,
                    )
                logger.info(f"Opened terminal window via {app}")
                return True
            except FileNotFoundError:
                continue
        logger.warning("Could not open terminal window — no supported app found")
        return False

    def stop_all(self):
        for s in self._sessions.values():
            s.stop()
        self._sessions.clear()


# Singleton
terminal = TerminalController()
