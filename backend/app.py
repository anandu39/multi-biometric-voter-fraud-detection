import os
from flask import Flask
from flask_cors import CORS
from database import get_db_connection
from routes.voter_routes import voter_bp

app = Flask(__name__)

CORS(app, resources={r"/api/*": {"origins": "*"}})

app.register_blueprint(voter_bp)


def init_db():

    conn = get_db_connection()

    schema_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "database",
        "schema.sql"
    )

    with open(schema_path, "r") as f:
        conn.executescript(f.read())

    conn.close()


@app.route("/")
def home():
    return {
        "status": "running",
        "system": "Multi-Biometric Fake Voter Detection"
    }


@app.route("/api/health")
def health():
    return {
        "status": "ok",
        "service": "voter-registration"
    }


if __name__ == "__main__":

    init_db()

    app.run(debug=True)