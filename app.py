"""
Test Evaluations Tracker — Flask + SQLAlchemy + Login
======================================================
All site config lives in config.json (same folder as app.py).
That's the only file you ever need to edit.
"""

import os, json, socket
from functools import wraps
from flask import (Flask, jsonify, request, render_template,
                   abort, session, redirect, url_for)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from datetime import datetime

# ── Load config.json ─────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

cfg = load_config()

# ── Resolve URI — force IPv4 for Supabase on IPv6-broken hosts ───────────────
def ipv4_uri(uri: str) -> str:
    """
    Replace the hostname in a DB URI with its IPv4 address.
    Supabase returns an IPv6 address on some resolvers;
    this guarantees we always connect over IPv4.
    """
    try:
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(uri)
        hostname = parsed.hostname
        # getaddrinfo with AF_INET forces IPv4 only
        results = socket.getaddrinfo(hostname, parsed.port or 5432,
                                     socket.AF_INET, socket.SOCK_STREAM)
        ipv4 = results[0][4][0]
        # Rebuild netloc with IPv4
        netloc = f"{parsed.username}:{parsed.password}@{ipv4}:{parsed.port or 5432}"
        return urlunparse(parsed._replace(netloc=netloc))
    except Exception as e:
        print(f"[WARN] IPv4 resolution failed ({e}), using original URI")
        return uri

raw_uri      = cfg["database"]["uri"]
DATABASE_URI = ipv4_uri(raw_uri)
SECRET_KEY   = os.environ.get("SECRET_KEY", os.urandom(24).hex())

# ── App setup ────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"]        = DATABASE_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"]                     = SECRET_KEY
# Pool settings suitable for containers / Supabase
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping":    True,   # test connection before use
    "pool_recycle":     300,    # recycle connections every 5 min
    "connect_args": {
        "sslmode":         "require",
        "connect_timeout": 10,
    },
}

db = SQLAlchemy(app)

# ── Model ────────────────────────────────────────────────────────────────────
class TestEntry(db.Model):
    __tablename__ = "test_entries"

    id         = db.Column(db.Integer,    primary_key=True)
    name       = db.Column(db.String(200), nullable=False)
    type       = db.Column(db.String(10),  nullable=False)
    date       = db.Column(db.String(20),  nullable=True)
    marks      = db.Column(db.Float,       nullable=False)
    total      = db.Column(db.Float,       nullable=False)
    batch      = db.Column(db.Integer,     nullable=True)
    centre     = db.Column(db.Integer,     nullable=True)
    air        = db.Column(db.Integer,     nullable=True)
    notes      = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime,    default=datetime.utcnow)

    def to_dict(self):
        return {
            "id":     self.id,
            "name":   self.name,
            "type":   self.type,
            "date":   self.date or "",
            "marks":  self.marks,
            "total":  self.total,
            "batch":  self.batch,
            "centre": self.centre,
            "air":    self.air,
            "notes":  self.notes or "",
        }

# ── Auto-create tables ────────────────────────────────────────────────────────
with app.app_context():
    db.create_all()
    print(f"[DB] Connected → {cfg['database']['uri']}")
    print(f"[DB] Tables ready.")

# ── Auth helper ───────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def get_cfg():
    """Always re-read config so live edits take effect instantly."""
    return load_config()

# ── Auth routes ───────────────────────────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    cfg = get_cfg()
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if (username == cfg["auth"]["username"] and
                password == cfg["auth"]["password"]):
            session["logged_in"] = True
            session["username"]  = username
            return redirect(url_for("index"))
        error = "Invalid credentials"
    return render_template("login.html", cfg=cfg, error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ── Main page ─────────────────────────────────────────────────────────────────
@app.route("/")
@login_required
def index():
    cfg = get_cfg()
    return render_template("index.html", cfg=cfg)

# ── API — protected ───────────────────────────────────────────────────────────
@app.route("/api/entries", methods=["GET", "POST"])
@login_required
def entries():
    if request.method == "GET":
        rows = TestEntry.query.order_by(TestEntry.created_at.asc()).all()
        return jsonify([r.to_dict() for r in rows])

    data = request.get_json(force=True)
    if not data:
        abort(400, "JSON body required")

    name  = str(data.get("name", "")).strip()
    marks = data.get("marks")
    total = data.get("total")
    if not name:              abort(400, "name is required")
    if marks is None or total is None: abort(400, "marks and total are required")

    entry = TestEntry(
        name   = name,
        type   = data.get("type", "minor"),
        date   = data.get("date") or None,
        marks  = float(marks),
        total  = float(total),
        batch  = int(data["batch"])  if data.get("batch")  else None,
        centre = int(data["centre"]) if data.get("centre") else None,
        air    = int(data["air"])    if data.get("air")    else None,
        notes  = str(data.get("notes", "")).strip() or None,
    )
    db.session.add(entry)
    db.session.commit()
    return jsonify(entry.to_dict()), 201

@app.route("/api/entries/<int:entry_id>", methods=["DELETE"])
@login_required
def delete_entry(entry_id):
    entry = TestEntry.query.get_or_404(entry_id)
    db.session.delete(entry)
    db.session.commit()
    return jsonify({"deleted": entry_id})

@app.route("/api/entries/all", methods=["DELETE"])
@login_required
def delete_all():
    count = TestEntry.query.delete()
    db.session.commit()
    return jsonify({"deleted": count})

# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, port=5000)
