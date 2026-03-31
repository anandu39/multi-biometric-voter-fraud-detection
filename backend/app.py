import os
from flask import Flask
from flask_cors import CORS
from database import get_db_connection
from routes.voter_routes import voter_bp
from routes.officer_routes import officer_bp
from routes.otp_routes import otp_bp
from routes.biometric_routes import biometric_bp
from routes.booth_routes import booth_bp

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

app.register_blueprint(voter_bp)
app.register_blueprint(officer_bp)
app.register_blueprint(otp_bp)
app.register_blueprint(biometric_bp)
app.register_blueprint(booth_bp)

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def init_db():
    conn = get_db_connection()
    schema_path = os.path.join(ROOT_DIR, "database", "schema.sql")
    with open(schema_path, "r") as f:
        conn.executescript(f.read())
    conn.close()
    print("[EVRS] Database initialised.")

def ensure_upload_dirs():
    for folder in ["uploads/faces", "uploads/iris", "uploads/fingerprints", "uploads/booth_captures"]:
        os.makedirs(os.path.join(ROOT_DIR, folder), exist_ok=True)
    print("[EVRS] Upload directories ready.")

@app.route("/")
def home():
    return {"status": "running", "system": "EVRS v3 - Phase 2 Active"}

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
        return {"total_voters": total_voters, "total_officers": total_officers,
                "biometrics_done": biometrics_done, "fraud_alerts": fraud_total}
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()
    ensure_upload_dirs()
    app.run(debug=True)