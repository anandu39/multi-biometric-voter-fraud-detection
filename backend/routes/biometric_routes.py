"""
biometric_routes.py
--------------------
Handles biometric image upload, embedding generation, and duplicate detection.

POST /api/biometrics/upload   — Upload face (required), iris, fingerprint
GET  /api/biometrics/pending  — Voters with no biometrics
GET  /api/biometrics/<voter_id> — Get biometric status for a voter
"""

import os
import uuid
import hashlib
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from database import get_db_connection
from models.biometric_model import (
    save_biometrics,
    get_all_face_embeddings,
    get_biometrics_for_voter,
    get_voters_without_biometrics,
    log_fraud_alert
)
from utils.face_matcher import (
    generate_embedding,
    check_duplicate_registration
)

biometric_bp = Blueprint("biometric_bp", __name__)

# ── Upload directory ─────────────────────────────────────────────────────────
ROOT_DIR   = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UPLOAD_DIR = os.path.join(ROOT_DIR, "uploads")

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "bmp"}
MAX_FILE_SIZE_MB = 5


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_file(file, subfolder: str, voter_id: int, label: str) -> str:
    """Save an uploaded file and return its relative path."""
    ext      = file.filename.rsplit(".", 1)[1].lower()
    fname    = f"voter_{voter_id}_{label}_{uuid.uuid4().hex[:8]}.{ext}"
    folder   = os.path.join(UPLOAD_DIR, subfolder)
    os.makedirs(folder, exist_ok=True)
    full_path = os.path.join(folder, fname)
    file.save(full_path)
    return full_path          # return absolute path for embedding; store relative in DB


def relative_path(abs_path: str) -> str:
    """Store only the path from uploads/ onwards."""
    try:
        return os.path.relpath(abs_path, ROOT_DIR)
    except ValueError:
        return abs_path


def file_hash(path: str) -> str:
    """SHA-256 hash of the face image for quick change detection."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ── UPLOAD BIOMETRICS ────────────────────────────────────────────────────────

@biometric_bp.route("/api/biometrics/upload", methods=["POST"])
def upload_biometrics():
    """
    Expects multipart/form-data:
        voter_id   (required, int)
        face       (required, image file)
        iris       (optional, image file)
        fingerprint (optional, image file)
    """
    voter_id = request.form.get("voter_id")
    if not voter_id:
        return jsonify({"error": "voter_id is required"}), 400

    try:
        voter_id = int(voter_id)
    except ValueError:
        return jsonify({"error": "voter_id must be an integer"}), 400

    # Verify voter exists
    conn = get_db_connection()
    voter = conn.execute(
        "SELECT voter_id, name FROM voters WHERE voter_id = ?", (voter_id,)
    ).fetchone()
    conn.close()

    if not voter:
        return jsonify({"error": f"Voter #{voter_id} not found"}), 404

    # ── Face (required) ──────────────────────────────────────────────────────
    face_file = request.files.get("face")
    if not face_file or face_file.filename == "":
        return jsonify({"error": "Face photo is required"}), 400
    if not allowed_file(face_file.filename):
        return jsonify({"error": "Invalid file type. Use JPG, PNG, or WEBP"}), 400

    # Save face
    face_abs = save_file(face_file, "faces", voter_id, "face")

    # Generate face embedding
    face_embedding = generate_embedding(face_abs)
    if face_embedding is None:
        os.remove(face_abs)
        return jsonify({
            "error": "No face detected in the uploaded photo. Please upload a clear, front-facing photo."
        }), 422

    # ── Duplicate check against all stored faces ─────────────────────────────
    existing_embeddings = get_all_face_embeddings(exclude_voter_id=voter_id)
    dup_result = check_duplicate_registration(face_embedding, existing_embeddings)

    duplicate_flag = dup_result["is_duplicate"]
    matched_voter_id = dup_result.get("matched_voter_id")
    face_score = dup_result["score"]

    if duplicate_flag:
        # Log fraud alert
        log_fraud_alert(
            voter_id=voter_id,
            matched_voter_id=matched_voter_id,
            face_score=face_score,
            iris_score=0.0,
            fingerprint_score=0.0,
            final_score=face_score,
            reason=f"Face similarity {face_score:.2%} with Voter #{matched_voter_id} during registration"
        )

    # ── Iris (optional) ──────────────────────────────────────────────────────
    iris_abs = None
    iris_file = request.files.get("iris")
    if iris_file and iris_file.filename and allowed_file(iris_file.filename):
        iris_abs = save_file(iris_file, "iris", voter_id, "iris")

    # ── Fingerprint (optional) ───────────────────────────────────────────────
    fp_abs = None
    fp_file = request.files.get("fingerprint")
    if fp_file and fp_file.filename and allowed_file(fp_file.filename):
        fp_abs = save_file(fp_file, "fingerprints", voter_id, "fp")

    # ── Compute hash of face image ───────────────────────────────────────────
    bio_hash = file_hash(face_abs)

    # ── Save to DB ───────────────────────────────────────────────────────────
    biometric_id = save_biometrics(voter_id, {
        "face_image_path":  relative_path(face_abs),
        "iris_image_path":  relative_path(iris_abs) if iris_abs else None,
        "fingerprint_path": relative_path(fp_abs) if fp_abs else None,
        "face_embedding":   face_embedding,
        "biometric_hash":   bio_hash
    })

    response = {
        "message": "Biometrics saved successfully",
        "biometric_id": biometric_id,
        "voter_id": voter_id,
        "voter_name": voter["name"],
        "face_saved": True,
        "iris_saved": iris_abs is not None,
        "fingerprint_saved": fp_abs is not None,
        "duplicate_detected": duplicate_flag,
    }

    if duplicate_flag:
        response["duplicate_info"] = {
            "matched_voter_id": matched_voter_id,
            "similarity_score": face_score,
            "similarity_percent": f"{face_score * 100:.1f}%",
            "alert": f"HIGH SIMILARITY with Voter #{matched_voter_id}. Fraud alert logged."
        }

    status_code = 201 if not duplicate_flag else 200
    return jsonify(response), status_code


# ── PENDING BIOMETRICS ───────────────────────────────────────────────────────

@biometric_bp.route("/api/biometrics/pending", methods=["GET"])
def pending_biometrics():
    """Return voters who still need biometric capture."""
    try:
        voters = get_voters_without_biometrics()
        return jsonify({"pending": voters, "count": len(voters)}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── BIOMETRIC STATUS FOR ONE VOTER ───────────────────────────────────────────

@biometric_bp.route("/api/biometrics/<int:voter_id>", methods=["GET"])
def biometric_status(voter_id):
    bio = get_biometrics_for_voter(voter_id)
    if not bio:
        return jsonify({"has_biometrics": False, "voter_id": voter_id}), 200

    return jsonify({
        "has_biometrics": True,
        "voter_id": voter_id,
        "face_saved":        bio.get("face_image_path") is not None,
        "iris_saved":        bio.get("iris_image_path") is not None,
        "fingerprint_saved": bio.get("fingerprint_path") is not None,
        "has_embedding":     bio.get("face_embedding") is not None,
        "created_at":        bio.get("created_at")
    }), 200


# ── FRAUD ALERTS LIST ────────────────────────────────────────────────────────

@biometric_bp.route("/api/fraud-alerts", methods=["GET"])
def fraud_alerts():
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT fa.*, v1.name as voter_name, v2.name as matched_name
            FROM fraud_alerts fa
            LEFT JOIN voters v1 ON fa.voter_id = v1.voter_id
            LEFT JOIN voters v2 ON fa.matched_voter_id = v2.voter_id
            ORDER BY fa.alert_date DESC
            LIMIT 100
        """).fetchall()
        return jsonify({"alerts": [dict(r) for r in rows]}), 200
    finally:
        conn.close()