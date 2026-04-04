"""
admin_routes.py
---------------
Admin/Supervisor approval system.

PDF Requirement: Admin Management Module
- Admin can Approve / Reject voter registrations
- Admin can view all pending voters (status = 'pending_approval')
- Admin can update voter status
- Fraud alert review with approve/dismiss
- Admin reports
"""

from flask import Blueprint, request, jsonify
from database import get_db_connection

admin_bp = Blueprint("admin_bp", __name__)


# ── GET PENDING VOTERS (awaiting admin approval) ─────────────────────────────

@admin_bp.route("/api/admin/pending-voters", methods=["GET"])
def pending_voters():
    """
    Returns all voters with status = 'pending_approval'.
    These are newly registered voters waiting for supervisor/admin to approve.
    """
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT v.voter_id, v.name, v.dob, v.gender, v.phone, v.email,
                   v.street, v.ward_number, v.panchayat, v.district, v.state,
                   v.pincode, v.constituency, v.status, v.officer_id, v.created_at,
                   o.name as registered_by,
                   b.face_image_path,
                   (SELECT COUNT(*) FROM identity_documents WHERE voter_id = v.voter_id) as doc_count
            FROM voters v
            LEFT JOIN officers o ON v.officer_id = o.officer_id
            LEFT JOIN biometrics b ON v.voter_id = b.voter_id
            WHERE v.status = 'pending_approval'
            ORDER BY v.created_at DESC
        """).fetchall()

        docs_rows = conn.execute("""
            SELECT voter_id, document_type, document_number
            FROM identity_documents
            WHERE voter_id IN (
                SELECT voter_id FROM voters WHERE status = 'pending_approval'
            )
        """).fetchall()

        docs_map = {}
        for d in docs_rows:
            vid = d["voter_id"]
            if vid not in docs_map:
                docs_map[vid] = []
            docs_map[vid].append(dict(d))

        result = []
        for r in rows:
            rd = dict(r)
            rd["documents"] = docs_map.get(r["voter_id"], [])
            result.append(rd)

        return jsonify({"pending": result, "count": len(result)}), 200
    finally:
        conn.close()


# ── APPROVE VOTER ─────────────────────────────────────────────────────────────

@admin_bp.route("/api/admin/approve-voter", methods=["POST"])
def approve_voter():
    """
    Supervisor approves a voter registration.
    Changes voter status from 'pending_approval' → 'active'.
    Body: { voter_id, officer_id, remarks (optional) }
    """
    data = request.get_json() or {}
    voter_id = data.get("voter_id")
    officer_id = data.get("officer_id")
    remarks = data.get("remarks", "Approved by supervisor")

    if not voter_id or not officer_id:
        return jsonify({"error": "voter_id and officer_id are required"}), 400

    conn = get_db_connection()
    try:
        voter = conn.execute(
            "SELECT voter_id, name, status FROM voters WHERE voter_id = ?", (voter_id,)
        ).fetchone()

        if not voter:
            return jsonify({"error": "Voter not found"}), 404

        if voter["status"] == "active":
            return jsonify({"error": "Voter is already approved"}), 400

        conn.execute("""
            UPDATE voters SET status = 'active' WHERE voter_id = ?
        """, (voter_id,))

        conn.execute("""
            INSERT INTO admin_actions (voter_id, officer_id, action, remarks)
            VALUES (?, ?, 'approved', ?)
        """, (voter_id, officer_id, remarks))

        conn.commit()

        return jsonify({
            "message": f"Voter #{voter_id} ({voter['name']}) approved successfully",
            "voter_id": voter_id,
            "new_status": "active"
        }), 200
    finally:
        conn.close()


# ── REJECT VOTER ──────────────────────────────────────────────────────────────

@admin_bp.route("/api/admin/reject-voter", methods=["POST"])
def reject_voter():
    """
    Supervisor rejects a voter registration.
    Changes voter status to 'rejected'.
    Body: { voter_id, officer_id, reason }
    """
    data = request.get_json() or {}
    voter_id = data.get("voter_id")
    officer_id = data.get("officer_id")
    reason = data.get("reason", "")

    if not voter_id or not officer_id:
        return jsonify({"error": "voter_id and officer_id are required"}), 400
    if not reason:
        return jsonify({"error": "Rejection reason is required"}), 400

    conn = get_db_connection()
    try:
        voter = conn.execute(
            "SELECT voter_id, name, status FROM voters WHERE voter_id = ?", (voter_id,)
        ).fetchone()

        if not voter:
            return jsonify({"error": "Voter not found"}), 404

        conn.execute("""
            UPDATE voters SET status = 'rejected' WHERE voter_id = ?
        """, (voter_id,))

        conn.execute("""
            INSERT INTO admin_actions (voter_id, officer_id, action, remarks)
            VALUES (?, ?, 'rejected', ?)
        """, (voter_id, officer_id, reason))

        conn.commit()

        return jsonify({
            "message": f"Voter #{voter_id} ({voter['name']}) rejected",
            "voter_id": voter_id,
            "new_status": "rejected"
        }), 200
    finally:
        conn.close()


# ── ADMIN ACTIONS LOG ─────────────────────────────────────────────────────────

@admin_bp.route("/api/admin/actions", methods=["GET"])
def admin_actions():
    """All approve/reject actions by supervisors."""
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT aa.*, v.name as voter_name, o.name as officer_name
            FROM admin_actions aa
            LEFT JOIN voters v ON aa.voter_id = v.voter_id
            LEFT JOIN officers o ON aa.officer_id = o.officer_id
            ORDER BY aa.action_date DESC
            LIMIT 200
        """).fetchall()
        return jsonify({"actions": [dict(r) for r in rows]}), 200
    finally:
        conn.close()


# ── ADMIN DASHBOARD STATS ─────────────────────────────────────────────────────

@admin_bp.route("/api/admin/stats", methods=["GET"])
def admin_stats():
    """Summary stats for admin dashboard."""
    conn = get_db_connection()
    try:
        total = conn.execute("SELECT COUNT(*) FROM voters").fetchone()[0]
        active = conn.execute("SELECT COUNT(*) FROM voters WHERE status='active'").fetchone()[0]
        pending = conn.execute("SELECT COUNT(*) FROM voters WHERE status='pending_approval'").fetchone()[0]
        rejected = conn.execute("SELECT COUNT(*) FROM voters WHERE status='rejected'").fetchone()[0]
        fraud_total = conn.execute("SELECT COUNT(*) FROM fraud_alerts").fetchone()[0]
        fraud_today = conn.execute(
            "SELECT COUNT(*) FROM fraud_alerts WHERE date(alert_date) = date('now')"
        ).fetchone()[0]
        biometrics_done = conn.execute(
            "SELECT COUNT(*) FROM biometrics WHERE face_image_path IS NOT NULL"
        ).fetchone()[0]

        return jsonify({
            "total_voters": total,
            "active_voters": active,
            "pending_approval": pending,
            "rejected_voters": rejected,
            "fraud_total": fraud_total,
            "fraud_today": fraud_today,
            "biometrics_done": biometrics_done,
        }), 200
    finally:
        conn.close()


# ── FRAUD ALERT REVIEW ────────────────────────────────────────────────────────

@admin_bp.route("/api/admin/review-fraud-alert", methods=["POST"])
def review_fraud_alert():
    """
    Admin reviews a fraud alert — mark as reviewed or dismissed.
    Body: { alert_id, officer_id, action: 'reviewed'|'dismissed', remarks }
    """
    data = request.get_json() or {}
    alert_id = data.get("alert_id")
    officer_id = data.get("officer_id")
    action = data.get("action", "reviewed")
    remarks = data.get("remarks", "")

    if not alert_id or not officer_id:
        return jsonify({"error": "alert_id and officer_id are required"}), 400

    conn = get_db_connection()
    try:
        conn.execute("""
            UPDATE fraud_alerts
            SET reviewed = 1, reviewed_by = ?, review_remarks = ?, review_date = CURRENT_TIMESTAMP
            WHERE alert_id = ?
        """, (officer_id, remarks, alert_id))
        conn.commit()

        return jsonify({
            "message": f"Fraud alert #{alert_id} marked as {action}",
            "alert_id": alert_id
        }), 200
    finally:
        conn.close()