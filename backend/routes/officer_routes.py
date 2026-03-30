from flask import Blueprint, request, jsonify
from database import get_db_connection
import hashlib
import sqlite3

officer_bp = Blueprint("officer_bp", __name__)


def hash_password(password: str) -> str:
    """Simple SHA-256 hash. Replace with bcrypt in production."""
    return hashlib.sha256(password.encode()).hexdigest()


# ─────────────────────────────────────────
# REGISTER OFFICER
# ─────────────────────────────────────────

@officer_bp.route("/api/officer/register", methods=["POST"])
def register_officer():

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    required = ["name", "emp_id", "mobile", "district", "role", "password"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"'{field}' is required"}), 400

    allowed_roles = {"registration_officer", "booth_officer", "supervisor"}
    if data["role"] not in allowed_roles:
        return jsonify({"error": "Invalid role"}), 400

    if len(data["password"]) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO officers (name, emp_id, mobile, district, role, password_hash)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            data["name"].strip(),
            data["emp_id"].strip().upper(),
            data["mobile"].strip(),
            data["district"].strip(),
            data["role"],
            hash_password(data["password"])
        ))
        conn.commit()
        return jsonify({"message": "Officer registered successfully"}), 201

    except sqlite3.IntegrityError as e:
        err_str = str(e)
        if "emp_id" in err_str:
            return jsonify({"error": "Employee ID already registered"}), 400
        if "mobile" in err_str:
            return jsonify({"error": "Mobile number already registered"}), 400
        return jsonify({"error": "Duplicate entry detected"}), 400

    except Exception as e:
        return jsonify({"error": "Registration failed", "details": str(e)}), 500

    finally:
        conn.close()


# ─────────────────────────────────────────
# OFFICER LOGIN
# ─────────────────────────────────────────

@officer_bp.route("/api/officer/login", methods=["POST"])
def login_officer():

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request"}), 400

    identifier = data.get("identifier", "").strip()
    password = data.get("password", "")

    if not identifier or not password:
        return jsonify({"error": "Credentials required"}), 400

    conn = get_db_connection()
    try:
        # Match by mobile OR emp_id
        officer = conn.execute("""
            SELECT * FROM officers
            WHERE (mobile = ? OR emp_id = ?) AND is_active = 1
        """, (identifier, identifier.upper())).fetchone()

        if not officer:
            return jsonify({"error": "Officer not found or inactive"}), 401

        if officer["password_hash"] != hash_password(password):
            return jsonify({"error": "Incorrect password"}), 401

        return jsonify({
            "message": "Login successful",
            "officer_id": officer["officer_id"],
            "name": officer["name"],
            "role": officer["role"],
            "district": officer["district"]
        }), 200

    finally:
        conn.close()