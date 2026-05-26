"""
NEXUS — Dashboard Launcher
Launch dan manage SOC dashboard (Flask dev server atau static HTML).
Opens browser automatically after server starts.
"""

import threading, time, http.server, socketserver, json
from pathlib import Path

from shared.utils import get_logger, root
from runtime.browser_controller import browser

logger     = get_logger("nexus.dashboard")
UI_DIR     = root("ui")
STATIC_DIR = root("ui", "static")
LOGS_DIR   = root("logs", "runtime")

DEFAULT_PORT = 8080


# ─────────────────────────────────────────────────────────────────────────────
# Static file server (no Flask dependency)
# ─────────────────────────────────────────────────────────────────────────────

class _NexusHandler(http.server.SimpleHTTPRequestHandler):
    """Serve UI static files + a /api/status JSON endpoint."""

    _ui_dir: Path = UI_DIR

    def do_GET(self):
        if self.path == "/api/status":
            self._serve_status()
        elif self.path == "/api/executions":
            self._serve_log("executions.jsonl")
        elif self.path == "/api/workflows":
            self._serve_log("workflows.jsonl")
        else:
            # Serve from ui/
            original = self.directory
            self.directory = str(self._ui_dir)
            super().do_GET()
            self.directory = original

    def _serve_status(self):
        status = {
            "agent"    : "NEXUS",
            "status"   : "online",
            "timestamp": time.time(),
        }
        body = json.dumps(status).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_log(self, filename: str):
        log_file = LOGS_DIR / filename
        records  = []
        if log_file.exists():
            for line in log_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        # Return latest 100
        body = json.dumps(records[-100:]).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        # Suppress default HTTP access log — use nexus logger instead
        logger.debug(f"HTTP {args[0] if args else ''}")


# ─────────────────────────────────────────────────────────────────────────────
# Launcher
# ─────────────────────────────────────────────────────────────────────────────

class DashboardLauncher:
    def __init__(self):
        self._server  = None
        self._thread  = None
        self._port    = DEFAULT_PORT
        self._running = False

    def start(self, port: int = DEFAULT_PORT, open_browser: bool = True) -> bool:
        """Start dashboard server and optionally open browser."""
        if self._running:
            logger.info(f"Dashboard already running on port {self._port}")
            return True

        # Ensure ui/ has at least a minimal index.html
        self._ensure_ui()

        self._port = port

        # Find free port if requested port is taken
        while not self._is_port_free(self._port):
            logger.warning(f"Port {self._port} in use — trying {self._port + 1}")
            self._port += 1

        try:
            _NexusHandler._ui_dir = UI_DIR
            self._server = socketserver.TCPServer(
                ("", self._port), _NexusHandler, bind_and_activate=False
            )
            self._server.allow_reuse_address = True
            self._server.server_bind()
            self._server.server_activate()

            self._thread = threading.Thread(
                target=self._server.serve_forever,
                daemon=True,
                name="nexus-dashboard",
            )
            self._thread.start()
            self._running = True
            logger.info(f"Dashboard started → http://localhost:{self._port}")

            if open_browser:
                time.sleep(0.5)   # brief wait for server to be ready
                browser.open_dashboard(port=self._port)

            return True

        except OSError as e:
            logger.error(f"Dashboard start failed: {e}")
            return False

    def stop(self):
        """Stop the dashboard server."""
        if self._server:
            self._server.shutdown()
            self._server = None
        self._running = False
        logger.info("Dashboard stopped")

    @property
    def url(self) -> str:
        return f"http://localhost:{self._port}"

    @property
    def running(self) -> bool:
        return self._running

    @staticmethod
    def _is_port_free(port: int) -> bool:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(("localhost", port)) != 0

    def _ensure_ui(self):
        """Create minimal index.html if ui/ doesn't have one."""
        index = UI_DIR / "index.html"
        if index.exists():
            return
        UI_DIR.mkdir(parents=True, exist_ok=True)
        index.write_text(
            self._minimal_html(),
            encoding="utf-8",
        )
        logger.info(f"Created minimal UI at {index}")

    @staticmethod
    def _minimal_html() -> str:
        return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NEXUS SOC Dashboard</title>
<style>
  :root{--bg:#0a0a0f;--panel:#12121a;--border:#1e1e2e;
        --cyan:#00f5ff;--green:#00ff88;--red:#ff3366;
        --yellow:#ffcc00;--text:#e0e0ff;--dim:#666699}
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--bg);color:var(--text);font-family:'Courier New',monospace;
       min-height:100vh;padding:20px}
  h1{color:var(--cyan);text-align:center;letter-spacing:4px;margin-bottom:20px;
     text-shadow:0 0 20px var(--cyan)}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px}
  .card{background:var(--panel);border:1px solid var(--border);border-radius:8px;
        padding:20px;transition:border-color .3s}
  .card:hover{border-color:var(--cyan)}
  .card h3{color:var(--cyan);font-size:.85rem;letter-spacing:2px;margin-bottom:12px;
           border-bottom:1px solid var(--border);padding-bottom:8px}
  .status{display:flex;align-items:center;gap:8px;margin-bottom:8px}
  .dot{width:8px;height:8px;border-radius:50%;background:var(--green);
       box-shadow:0 0 8px var(--green);animation:pulse 2s infinite}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
  .log-line{color:var(--dim);font-size:.8rem;padding:4px 0;border-bottom:1px solid #1a1a2e}
  .log-line.ok{color:var(--green)} .log-line.err{color:var(--red)}
  #refresh{background:none;border:1px solid var(--cyan);color:var(--cyan);
           padding:6px 16px;border-radius:4px;cursor:pointer;font-family:inherit;
           letter-spacing:1px;margin-top:10px}
  #refresh:hover{background:var(--cyan);color:var(--bg)}
  footer{text-align:center;margin-top:30px;color:var(--dim);font-size:.75rem;
         letter-spacing:2px}
</style>
</head>
<body>
<h1>⬡ NEXUS SOC DASHBOARD</h1>
<div class="grid">
  <div class="card">
    <h3>▸ AGENT STATUS</h3>
    <div class="status"><div class="dot"></div><span id="agent-status">Initializing...</span></div>
    <div style="color:var(--dim);font-size:.8rem">Last updated: <span id="ts">—</span></div>
  </div>
  <div class="card">
    <h3>▸ RECENT EXECUTIONS</h3>
    <div id="executions"><span style="color:var(--dim)">Loading...</span></div>
  </div>
  <div class="card">
    <h3>▸ WORKFLOWS</h3>
    <div id="workflows"><span style="color:var(--dim)">Loading...</span></div>
  </div>
</div>
<div style="text-align:center;margin-top:20px">
  <button id="refresh" onclick="loadAll()">↺ REFRESH</button>
</div>
<footer>NEXUS v1.0 · Autonomous Security Operations Agent · Authorized Use Only</footer>
<script>
async function fetchJson(url){try{const r=await fetch(url);return r.json()}catch{return null}}
function timeAgo(ts){const d=Date.now()/1000-ts;
  if(d<60)return`${~~d}s ago`;if(d<3600)return`${~~(d/60)}m ago`;return`${~~(d/3600)}h ago`}
async function loadStatus(){
  const d=await fetchJson('/api/status');
  if(d){document.getElementById('agent-status').textContent=d.status.toUpperCase();
        document.getElementById('ts').textContent=timeAgo(d.timestamp)}}
async function loadExecLog(){
  const data=await fetchJson('/api/executions');
  const el=document.getElementById('executions');
  if(!data||!data.length){el.innerHTML='<span style="color:var(--dim)">No executions yet</span>';return}
  el.innerHTML=data.slice(-5).reverse().map(e=>
    `<div class="log-line ${e.success?'ok':'err'}">${e.success?'✓':'✗'} ${e.tool} (${e.duration}s)</div>`
  ).join('')}
async function loadWorkflows(){
  const data=await fetchJson('/api/workflows');
  const el=document.getElementById('workflows');
  if(!data||!data.length){el.innerHTML='<span style="color:var(--dim)">No workflows yet</span>';return}
  el.innerHTML=data.slice(-3).reverse().map(w=>
    `<div class="log-line ${w.success?'ok':'err'}">${w.success?'✓':'✗'} ${w.steps?.length||0} steps (${w.duration}s)</div>`
  ).join('')}
async function loadAll(){await Promise.all([loadStatus(),loadExecLog(),loadWorkflows()])}
loadAll();
setInterval(loadAll,10000);
</script>
</body>
</html>"""


# Singleton
dashboard = DashboardLauncher()
