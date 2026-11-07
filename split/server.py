"""Split: tiny backend for the two-person expenses app.

Serves index.html and a small JSON API at POST /api/<name>. Data lives in one
SQLite file (DB_PATH). Python standard library only, no dependencies.
Every API call must carry the shared PIN; the first PIN ever used becomes it.
"""
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
import time
import uuid
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DB_PATH = os.environ.get("DB_PATH", "/data/split.db")
PORT = int(os.environ.get("PORT", "8765"))
HERE = os.path.dirname(os.path.abspath(__file__))
MODES = {"equal", "full", "exact", "percent", "settle"}
lock = threading.Lock()  # one writer at a time keeps things simple


class ApiError(Exception):
    pass


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    with db() as c:
        c.executescript("""
            create table if not exists settings (
              id integer primary key check (id = 1),
              name_a text not null default 'Sam',
              name_b text not null default 'Partner',
              pin_hash text);
            insert or ignore into settings (id) values (1);
            create table if not exists entries (
              id text primary key,
              created_at real not null,
              spent_on text not null,
              description text not null,
              amount integer not null check (amount > 0),        -- cents
              paid_by text not null check (paid_by in ('a','b')),
              share_a integer not null check (share_a >= 0),     -- cents person A consumed
              share_b integer not null check (share_b >= 0),     -- cents person B consumed
              split_mode text not null,
              check (share_a + share_b = amount));
        """)


def hash_pin(pin, salt=None):
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(salt), 200_000).hex()
    return f"{salt}${h}"


def check_pin(c, pin):
    pin = pin or ""
    stored = c.execute("select pin_hash from settings where id = 1").fetchone()["pin_hash"]
    if stored is None:
        if len(pin) < 6:
            raise ApiError("PIN must be at least 6 characters")
        c.execute("update settings set pin_hash = ? where id = 1", (hash_pin(pin),))
        return
    salt = stored.split("$", 1)[0]
    if not hmac.compare_digest(hash_pin(pin, salt), stored):
        time.sleep(1)  # slow down guessing
        raise ApiError("Wrong PIN")


def cents(v):
    try:
        return round(float(v) * 100)
    except (TypeError, ValueError):
        raise ApiError("Invalid amount")


def api_list(c, a):
    s = c.execute("select name_a, name_b from settings where id = 1").fetchone()
    rows = c.execute("select * from entries order by spent_on desc, created_at desc").fetchall()
    entries = [{**dict(r), "amount": r["amount"] / 100, "share_a": r["share_a"] / 100,
                "share_b": r["share_b"] / 100} for r in rows]
    return {"settings": dict(s), "entries": entries}


def api_save(c, a):
    amount, share_a, share_b = cents(a.get("p_amount")), cents(a.get("p_share_a")), cents(a.get("p_share_b"))
    desc = str(a.get("p_description") or "").strip()[:80]
    paid_by, mode = a.get("p_paid_by"), a.get("p_split_mode")
    try:
        spent_on = date.fromisoformat(str(a.get("p_spent_on"))).isoformat()
    except ValueError:
        raise ApiError("Invalid date")
    if not desc:
        raise ApiError("Add a description")
    if amount <= 0 or share_a < 0 or share_b < 0 or share_a + share_b != amount:
        raise ApiError("Shares must add up to the amount")
    if paid_by not in ("a", "b") or mode not in MODES:
        raise ApiError("Invalid entry")
    entry_id = a.get("p_id")
    if entry_id:
        cur = c.execute("""update entries set spent_on=?, description=?, amount=?, paid_by=?, share_a=?,
                           share_b=?, split_mode=? where id=?""",
                        (spent_on, desc, amount, paid_by, share_a, share_b, mode, entry_id))
        if cur.rowcount == 0:
            raise ApiError("Entry not found")
    else:
        entry_id = str(uuid.uuid4())
        c.execute("insert into entries values (?,?,?,?,?,?,?,?,?)",
                  (entry_id, time.time(), spent_on, desc, amount, paid_by, share_a, share_b, mode))
    return entry_id


def api_delete(c, a):
    c.execute("delete from entries where id = ?", (a.get("p_id"),))


def api_settings_save(c, a):
    name_a = str(a.get("p_name_a") or "").strip()[:20]
    name_b = str(a.get("p_name_b") or "").strip()[:20]
    if not name_a or not name_b:
        raise ApiError("Both names are needed")
    c.execute("update settings set name_a = ?, name_b = ? where id = 1", (name_a, name_b))
    new_pin = a.get("p_new_pin")
    if new_pin:
        if len(new_pin) < 6:
            raise ApiError("PIN must be at least 6 characters")
        c.execute("update settings set pin_hash = ? where id = 1", (hash_pin(new_pin),))


API = {"split_list": api_list, "split_save": api_save, "split_delete": api_delete,
       "split_settings_save": api_settings_save}


class Handler(BaseHTTPRequestHandler):
    def send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.split("?")[0] in ("/", "/index.html"):
            with open(os.path.join(HERE, "index.html"), "rb") as f:
                return self.send(200, f.read(), "text/html; charset=utf-8")
        if self.path == "/health":
            return self.send(200, {"ok": True})
        self.send(404, {"error": "Not found"})

    def do_POST(self):
        fn = API.get(self.path.removeprefix("/api/"))
        if not fn:
            return self.send(404, {"error": "Not found"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length > 100_000:
                raise ApiError("Request too large")
            args = json.loads(self.rfile.read(length) or b"{}")
            with lock, db() as c:  # commits on success, rolls back on error
                check_pin(c, args.get("p_pin"))
                result = fn(c, args)
            self.send(200, {"data": result})
        except ApiError as e:
            self.send(400, {"error": str(e)})
        except (json.JSONDecodeError, sqlite3.IntegrityError):
            self.send(400, {"error": "Invalid request"})

    def log_message(self, fmt, *args):
        pass  # keep logs quiet; nothing sensitive is printed


if __name__ == "__main__":
    init_db()
    print(f"Split listening on :{PORT}, data in {DB_PATH}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
