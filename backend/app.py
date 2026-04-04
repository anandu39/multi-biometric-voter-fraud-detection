"""
app.py — EVRS Backend Entry Point
Works locally and on Render (free tier).
"""

import os
from dotenv import load_dotenv
load_dotenv()
from flask import Flask
from flask_cors import CORS
from database import get_db_connection
from routes.voter_routes import voter_bp
from routes.officer_routes import officer_bp
from routes.otp_routes import otp_bp
from routes.biometric_routes import biometric_bp
from routes.booth_routes import booth_bp
from routes.admin_routes import admin_bp          # ← Gap 3 fix: was missing

app = Flask(__name__)

# ── CORS — allow all origins in dev; restrict in prod via env var ──────────
ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "*")
CORS(app, resources={r"/api/*": {"origins": ALLOWED_ORIGIN}})

# ── Register blueprints ───────────────────────────────────────────────────
app.register_blueprint(voter_bp)
app.register_blueprint(officer_bp)
app.register_blueprint(otp_bp)
app.register_blueprint(biometric_bp)
app.register_blueprint(booth_bp)
app.register_blueprint(admin_bp)                  # ← Gap 3 fix: all /api/admin/* routes now active

# ── Path resolution — works both locally and on Render ───────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))          # backend/
ROOT_DIR = os.path.dirname(BASE_DIR)                            # project root

# On Render, use /tmp for writable storage (ephemeral but works for demo)
IS_RENDER = os.getenv("RENDER", "") == "true"
UPLOAD_BASE = "/tmp/evrs_uploads" if IS_RENDER else os.path.join(ROOT_DIR, "uploads")
DB_BASE     = "/tmp"             if IS_RENDER else os.path.join(ROOT_DIR, "database")


def init_db():
    """Create all tables from schema.sql if they don't exist."""
    conn = get_db_connection()
    schema_path = os.path.join(BASE_DIR, "..", "database", "schema.sql")
    if not os.path.exists(schema_path):
        schema_path = os.path.join(BASE_DIR, "schema.sql")   # fallback
    with open(schema_path, "r") as f:
        conn.executescript(f.read())
    conn.close()
    print("[EVRS] Database initialised.")


def ensure_upload_dirs():
    for folder in ["faces", "iris", "fingerprints", "booth_captures"]:
        os.makedirs(os.path.join(UPLOAD_BASE, folder), exist_ok=True)
    print(f"[EVRS] Upload dirs ready at {UPLOAD_BASE}")


# ── Routes ────────────────────────────────────────────────────────────────

@app.route("/")
def home():
    return {"status": "running", "system": "EVRS v3", "render": IS_RENDER}


@app.route("/api/health")
def health():
    return {"status": "ok"}


@app.route("/api/stats")
def stats():
    conn = get_db_connection()
    try:
        total_voters    = conn.execute("SELECT COUNT(*) FROM voters").fetchone()[0]
        total_officers  = conn.execute("SELECT COUNT(*) FROM officers WHERE is_active=1").fetchone()[0]
        biometrics_done = conn.execute("SELECT COUNT(*) FROM biometrics WHERE face_image_path IS NOT NULL").fetchone()[0]
        fraud_total     = conn.execute("SELECT COUNT(*) FROM fraud_alerts").fetchone()[0]
        return {
            "total_voters":    total_voters,
            "total_officers":  total_officers,
            "biometrics_done": biometrics_done,
            "fraud_alerts":    fraud_total
        }
    finally:
        conn.close()


# ── Startup ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    ensure_upload_dirs()
    port = int(os.getenv("PORT", 5000))
    debug = not IS_RENDER   # No debug on Render
    app.run(host="0.0.0.0", port=port, debug=debug)