"""A tiny, deliberately vulnerable Flask app used ONLY as a local, reliable
target for the curriculum generator (127.0.0.1) — never exposed externally.
Gives dirsearch/Arjun/XSStrike/sqlmap something real to find on this machine
instead of depending on a third-party demo site's uptime.
"""
import sqlite3
from flask import Flask, request

app = Flask(__name__)

conn = sqlite3.connect(":memory:", check_same_thread=False)
conn.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, price REAL)")
conn.executemany(
    "INSERT INTO products (id, name, price) VALUES (?, ?, ?)",
    [(1, "Widget", 9.99), (2, "Gadget", 19.99), (3, "Gizmo", 29.99)],
)
conn.commit()


@app.route("/")
def index():
    return "<h1>Test Lab</h1><a href='/product?id=1'>product</a> <a href='/search?q=widget'>search</a>"


@app.route("/product")
def product():
    pid = request.args.get("id", "1")
    # Intentionally vulnerable: raw string concatenation into SQL (SQLi test target)
    query = f"SELECT id, name, price FROM products WHERE id = {pid}"
    try:
        rows = conn.execute(query).fetchall()
        return {"query": query, "rows": rows}
    except Exception as e:
        return {"query": query, "error": str(e)}, 500


@app.route("/search")
def search():
    q = request.args.get("q", "")
    # Intentionally vulnerable: unescaped reflection (XSS test target)
    return f"<html><body>Results for: {q}</body></html>"


@app.route("/profile")
def profile():
    token = request.args.get("token")
    if token == "letmein":
        return "welcome back, admin panel unlocked"
    return "who are you?"


# Static-ish endpoints for dirsearch to discover via the custom wordlist
@app.route("/admin")
def admin():
    return "admin panel"


@app.route("/backup")
def backup():
    return "backup listing"


@app.route("/api")
def api():
    return {"status": "ok"}


@app.route("/login")
def login():
    return "login form"


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
