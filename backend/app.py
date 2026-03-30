import os
from flask import Flask
from flask_cors import CORS
from database import get_db_connection
from routes.voter_routes import voter_bp
from routes.officer_routes import officer_bp
from routes.otp_routes import otp_bp

app = Flask(__name__)

CORS(app, resources={r"/api/*": {"origins": "*"}})

init_db()
ensure_upload_dirs()

app.register_blueprint(voter_bp)
app.register_blueprint(officer_bp)
app.register_blueprint(otp_bp)


def init_db():
    conn = get_db_connection()

    schema_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "database",
        "schema.sql"
    )

    with open(schema_path, "r") as f:
        conn.executescript(f.read())

    conn.close()
    print("[EVRS] Database initialised.")


def ensure_upload_dirs():
    base = os.path.dirname(os.path.abspath(__file__))
    for folder in ["uploads/faces", "uploads/iris", "uploads/fingerprints"]:
        path = os.path.join(base, folder)
        os.makedirs(path, exist_ok=True)
    print("[EVRS] Upload directories ready.")


@app.route("/")
def home():
    return {
        "status": "running",
        "system": "EVRS — Multi-Biometric Voter Registration System",
        "version": "2.0"
    }


@app.route("/api/health")
def health():
    return {"status": "ok", "service": "evrs-backend"}


@app.route("/api/stats")
def stats():
    conn = get_db_connection()
    try:
        total_voters = conn.execute("SELECT COUNT(*) FROM voters").fetchone()[0]
        total_officers = conn.execute(
            "SELECT COUNT(*) FROM officers WHERE is_active = 1"
        ).fetchone()[0]
        return {
            "total_voters": total_voters,
            "total_officers": total_officers
        }
    finally:
        conn.close()


if __name__ == "__main__":
    app.run(debug=True)