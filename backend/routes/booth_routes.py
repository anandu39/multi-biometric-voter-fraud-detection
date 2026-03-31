"""
booth_routes.py
---------------
Poll booth election-day verification module.

POST /api/booth/login           — Booth officer login + booth selection
POST /api/booth/lookup-voter    — Search voter by name / voter_id / phone
POST /api/booth/verify-face     — Upload live face → match against stored embedding
POST /api/booth/confirm-vote    — Officer confirms voter; marks as voted
GET  /api/booth/voting-log      — Today's voting log for a booth
GET  /api/booth/stats           — Live booth statistics
"""

import os
import uuid
import json
from flask import Blueprint, request, jsonify
from database import get_db_connection
from utils.face_matcher import generate_embedding, verify_voter_face
from models.biometric_model import get_biometrics_for_voter, log_fraud_alert

booth_bp = Blueprint("booth_bp", __name__)

ROOT_DIR   = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UPLOAD_DIR = os.path.join(ROOT_DIR, "uploads", "booth_captures")

ALLOWED_EXT = {"jpg", "jpeg", "png", "webp"}


def allowed(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


# ── BOOTH OFFICER LOGIN ──────────────────────────────────────────────────────

@booth_bp.route("/api/booth/login", methods=["POST"])
def booth_login():
    """
    Reuses the officer credentials, then sets booth context.
    Body: { identifier, password, state, district, ward_number, booth_name }
    """
    import hashlib
    data = request.get_json() or {}

    identifier = data.get("identifier", "").strip()
    password   = data.get("password", "")
    state      = data.get("state", "").strip()
    district   = data.get("district", "").strip()
    ward       = data.get("ward_number", "").strip()
    booth_name = data.get("booth_name", "").strip()

    if not all([identifier, password, state, district, ward]):
        return jsonify({"error": "All fields are required"}), 400

    conn = get_db_connection()
    try:
        pw_hash = hashlib.sha256(password.encode()).hexdigest()
        officer = conn.execute("""
            SELECT officer_id, name, role, district
            FROM officers
            WHERE (mobile = ? OR emp_id = ?) AND password_hash = ? AND is_active = 1
        """, (identifier, identifier.upper(), pw_hash)).fetchone()

        if not officer:
            return jsonify({"error": "Invalid credentials or officer inactive"}), 401

        return jsonify({
            "message": "Booth login successful",
            "officer_id": officer["officer_id"],
            "officer_name": officer["name"],
            "role": officer["role"],
            "booth_context": {
                "state":       state,
                "district":    district,
                "ward_number": ward,
                "booth_name":  booth_name or f"Booth — Ward {ward}"
            }
        }), 200

    finally:
        conn.close()


# ── VOTER LOOKUP ─────────────────────────────────────────────────────────────

@booth_bp.route("/api/booth/lookup-voter", methods=["POST"])
def lookup_voter():
    """
    Search for a voter by voter_id, name, or phone within a ward/district.
    Body: { query, ward_number, district, state }
    """
    data     = request.get_json() or {}
    query    = data.get("query", "").strip()
    ward     = data.get("ward_number", "").strip()
    district = data.get("district", "").strip()
    state    = data.get("state", "").strip()

    if not query:
        return jsonify({"error": "Search query is required"}), 400

    conn = get_db_connection()
    try:
        # Try numeric voter_id first
        if query.isdigit():
            rows = conn.execute("""
                SELECT v.*, b.face_image_path, b.face_embedding,
                       vl.voted_at, vl.booth_name
                FROM voters v
                LEFT JOIN biometrics b ON v.voter_id = b.voter_id
                LEFT JOIN voting_log vl ON v.voter_id = vl.voter_id
                    AND date(vl.voted_at) = date('now')
                WHERE v.voter_id = ?
            """, (int(query),)).fetchall()
        else:
            # Search by name or phone, filtered by booth location if provided
            like = f"%{query}%"
            params = [like, like]
            location_clause = ""
            if ward:
                location_clause += " AND v.ward_number = ?"
                params.append(ward)
            if district:
                location_clause += " AND v.district = ?"
                params.append(district)

            rows = conn.execute(f"""
                SELECT v.*, b.face_image_path, b.face_embedding,
                       vl.voted_at, vl.booth_name
                FROM voters v
                LEFT JOIN biometrics b ON v.voter_id = b.voter_id
                LEFT JOIN voting_log vl ON v.voter_id = vl.voter_id
                    AND date(vl.voted_at) = date('now')
                WHERE (v.name LIKE ? OR v.phone LIKE ?)
                {location_clause}
                ORDER BY v.name
                LIMIT 10
            """, params).fetchall()

        results = []
        for r in rows:
            d = dict(r)
            # Don't send raw embedding to frontend
            d.pop("face_embedding", None)
            d["has_face"] = bool(r["face_image_path"])
            d["already_voted"] = bool(r["voted_at"])
            results.append(d)

        return jsonify({"results": results, "count": len(results)}), 200

    finally:
        conn.close()


# ── FACE VERIFICATION ────────────────────────────────────────────────────────

@booth_bp.route("/api/booth/verify-face", methods=["POST"])
def verify_face():
    """
    Upload a live photo and compare against stored voter embedding.
    Expects multipart/form-data: voter_id (int), live_face (image file)
    """
    voter_id = request.form.get("voter_id")
    if not voter_id:
        return jsonify({"error": "voter_id is required"}), 400

    try:
        voter_id = int(voter_id)
    except ValueError:
        return jsonify({"error": "voter_id must be an integer"}), 400

    live_file = request.files.get("live_face")
    if not live_file or not allowed(live_file.filename):
        return jsonify({"error": "Valid live face image required"}), 400

    # Get stored biometrics
    bio = get_biometrics_for_voter(voter_id)
    if not bio or not bio.get("face_embedding"):
        return jsonify({
            "error": "No stored face embedding for this voter. Biometric registration required first.",
            "no_biometrics": True
        }), 404

    # Check if already voted today
    conn = get_db_connection()
    try:
        already_voted = conn.execute("""
            SELECT voted_at, booth_name FROM voting_log
            WHERE voter_id = ? AND date(voted_at) = date('now')
        """, (voter_id,)).fetchone()
    finally:
        conn.close()

    if already_voted:
        return jsonify({
            "match": False,
            "fraud": True,
            "fraud_reason": "ALREADY_VOTED",
            "already_voted_at": already_voted["voted_at"],
            "already_voted_booth": already_voted["booth_name"],
            "message": "⚠️ This voter has already cast their vote today!",
            "score": 0.0,
            "confidence_label": "—"
        }), 200

    # Save live capture temporarily
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext      = live_file.filename.rsplit(".", 1)[1].lower()
    tmp_path = os.path.join(UPLOAD_DIR, f"live_{voter_id}_{uuid.uuid4().hex[:8]}.{ext}")
    live_file.save(tmp_path)

    # Generate embedding for live face
    live_embedding = generate_embedding(tmp_path)

    # Clean up temp file
    try:
        os.remove(tmp_path)
    except Exception:
        pass

    if live_embedding is None:
        return jsonify({
            "error": "Could not detect a face in the captured photo. Please try again with better lighting."
        }), 422

    # Compare
    result = verify_voter_face(live_embedding, bio["face_embedding"])

    fraud = not result["match"]

    if fraud:
        log_fraud_alert(
            voter_id=voter_id,
            matched_voter_id=None,
            face_score=result["score"],
            iris_score=0.0,
            fingerprint_score=0.0,
            final_score=result["score"],
            reason=f"Booth face mismatch. Similarity: {result['score']:.2%}. Confidence: {result['confidence_label']}"
        )

    return jsonify({
        "match":             result["match"],
        "score":             result["score"],
        "score_percent":     f"{result['score'] * 100:.1f}%",
        "confidence_label":  result["confidence_label"],
        "fraud":             fraud,
        "fraud_reason":      "FACE_MISMATCH" if fraud else None,
        "voter_id":          voter_id
    }), 200


# ── CONFIRM VOTE ─────────────────────────────────────────────────────────────

@booth_bp.route("/api/booth/confirm-vote", methods=["POST"])
def confirm_vote():
    """
    Officer manually confirms the voter is allowed through.
    Body: { voter_id, officer_id, booth_name, ward_number, district, state,
            override_reason (optional) }
    """
    data = request.get_json() or {}

    voter_id      = data.get("voter_id")
    officer_id    = data.get("officer_id")
    booth_name    = data.get("booth_name", "Unknown Booth")
    ward_number   = data.get("ward_number", "")
    override_reason = data.get("override_reason")

    if not voter_id or not officer_id:
        return jsonify({"error": "voter_id and officer_id are required"}), 400

    conn = get_db_connection()
    try:
        # Double-check not already voted
        existing = conn.execute(
            "SELECT vote_id FROM voting_log WHERE voter_id = ? AND date(voted_at) = date('now')",
            (voter_id,)
        ).fetchone()

        if existing:
            return jsonify({"error": "Voter has already been confirmed today"}), 409

        conn.execute("""
            INSERT INTO voting_log
                (voter_id, officer_id, booth_name, ward_number, override_reason)
            VALUES (?, ?, ?, ?, ?)
        """, (voter_id, officer_id, booth_name, ward_number, override_reason))
        conn.commit()

        return jsonify({
            "message": "Vote confirmed successfully",
            "voter_id": voter_id
        }), 201

    finally:
        conn.close()


# ── VOTING LOG ───────────────────────────────────────────────────────────────

@booth_bp.route("/api/booth/voting-log", methods=["GET"])
def voting_log():
    ward     = request.args.get("ward_number", "")
    district = request.args.get("district", "")

    conn = get_db_connection()
    try:
        params = []
        clauses = ["date(vl.voted_at) = date('now')"]

        if ward:
            clauses.append("vl.ward_number = ?")
            params.append(ward)
        if district:
            clauses.append("v.district = ?")
            params.append(district)

        where = " AND ".join(clauses)

        rows = conn.execute(f"""
            SELECT vl.*, v.name, v.phone, v.gender
            FROM voting_log vl
            JOIN voters v ON vl.voter_id = v.voter_id
            WHERE {where}
            ORDER BY vl.voted_at DESC
        """, params).fetchall()

        return jsonify({"log": [dict(r) for r in rows], "count": len(rows)}), 200

    finally:
        conn.close()


# ── BOOTH STATS ──────────────────────────────────────────────────────────────

@booth_bp.route("/api/booth/stats", methods=["GET"])
def booth_stats():
    ward     = request.args.get("ward_number", "")
    district = request.args.get("district", "")

    conn = get_db_connection()
    try:
        params_loc = []
        loc_clause = ""
        if ward:
            loc_clause += " AND v.ward_number = ?"
            params_loc.append(ward)
        if district:
            loc_clause += " AND v.district = ?"
            params_loc.append(district)

        total_registered = conn.execute(
            f"SELECT COUNT(*) FROM voters v WHERE status = 'active' {loc_clause}",
            params_loc
        ).fetchone()[0]

        voted_today = conn.execute(
            f"""SELECT COUNT(*) FROM voting_log vl
                JOIN voters v ON vl.voter_id = v.voter_id
                WHERE date(vl.voted_at) = date('now') {loc_clause}""",
            params_loc
        ).fetchone()[0]

        fraud_today = conn.execute(
            "SELECT COUNT(*) FROM fraud_alerts WHERE date(alert_date) = date('now')"
        ).fetchone()[0]

        turnout = round((voted_today / total_registered * 100), 1) if total_registered else 0

        return jsonify({
            "total_registered": total_registered,
            "voted_today":      voted_today,
            "pending_vote":     total_registered - voted_today,
            "turnout_percent":  turnout,
            "fraud_alerts_today": fraud_today
        }), 200

    finally:
        conn.close()