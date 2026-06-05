"""
Test Evaluations Tracker — Flask + SQLAlchemy + Login
======================================================
All site config lives in config.json (same folder as app.py).
That's the only file you ever need to edit.
"""

import os, json
from functools import wraps
from flask import (Flask, jsonify, request, render_template,
                   abort, session, redirect, url_for)
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# ── Load config.json ─────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

cfg = load_config()

DATABASE_URI = cfg["database"]["uri"]
SECRET_KEY   = os.environ.get("SECRET_KEY", os.urandom(24).hex())

# ── App setup ────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"]        = DATABASE_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"]                     = SECRET_KEY

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

with app.app_context():
    db.create_all()
    print(f"[DB] Connected → {DATABASE_URI}")

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
