from flask import Blueprint, request, jsonify
from database import get_db_connection
import random
import time

otp_bp = Blueprint("otp_bp", __name__)

OTP_EXPIRY_SECONDS = 300  # 5 minutes
DEV_MODE = True  # Set False in production and integrate real SMS gateway


def generate_otp() -> str:
    return str(random.randint(100000, 999999))


def send_sms(mobile: str, otp: str) -> bool:
    """
    Placeholder for SMS gateway integration.
    In production, integrate Twilio / MSG91 / AWS SNS here.

    Example with MSG91:
        import requests
        requests.post("https://api.msg91.com/api/v5/otp", json={
            "authkey": "YOUR_KEY",
            "mobile": "91" + mobile,
            "otp": otp
        })
    """
    print(f"[DEV] OTP for {mobile}: {otp}")
    return True


# ─────────────────────────────────────────
# SEND OTP
# ─────────────────────────────────────────

@otp_bp.route("/api/send-otp", methods=["POST"])
def send_otp():

    data = request.get_json()
    mobile = (data or {}).get("mobile", "").strip()

    if not mobile or len(mobile) != 10 or not mobile.isdigit():
        return jsonify({"error": "Valid 10-digit mobile number required"}), 400

    otp = generate_otp()
    expires_at = int(time.time()) + OTP_EXPIRY_SECONDS

    conn = get_db_connection()
    try:
        # Invalidate old OTPs for this number
        conn.execute(
            "UPDATE otp_store SET used = 1 WHERE mobile = ? AND used = 0",
            (mobile,)
        )

        conn.execute("""
            INSERT INTO otp_store (mobile, otp, expires_at)
            VALUES (?, ?, ?)
        """, (mobile, otp, expires_at))
        conn.commit()

        success = send_sms(mobile, otp)

        if not success:
            return jsonify({"error": "Failed to send OTP"}), 500

        response = {"message": f"OTP sent to +91 {mobile}"}
        if DEV_MODE:
            response["otp"] = otp  # Expose in dev only

        return jsonify(response), 200

    finally:
        conn.close()


# ─────────────────────────────────────────
# VERIFY OTP
# ─────────────────────────────────────────

@otp_bp.route("/api/verify-otp", methods=["POST"])
def verify_otp():

    data = request.get_json()
    mobile = (data or {}).get("mobile", "").strip()
    otp = (data or {}).get("otp", "").strip()

    if not mobile or not otp:
        return jsonify({"error": "Mobile and OTP are required"}), 400

    conn = get_db_connection()
    try:
        row = conn.execute("""
            SELECT * FROM otp_store
            WHERE mobile = ? AND otp = ? AND used = 0
            ORDER BY id DESC LIMIT 1
        """, (mobile, otp)).fetchone()

        if not row:
            return jsonify({"error": "Invalid OTP"}), 400

        if int(time.time()) > row["expires_at"]:
            return jsonify({"error": "OTP has expired. Please request a new one."}), 400

        # Mark as used
        conn.execute(
            "UPDATE otp_store SET used = 1 WHERE id = ?", (row["id"],)
        )
        conn.commit()

        return jsonify({"message": "OTP verified successfully"}), 200

    finally:
        conn.close()