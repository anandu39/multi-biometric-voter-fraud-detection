"""
otp_routes.py
--------------
OTP generation and verification.
SMS is sent via Fast2SMS (free tier — 100 SMS/day, no transactional approval needed for dev).

Setup:
1. Register at https://www.fast2sms.com
2. Copy your API key from Dashboard → Dev API
3. Set FAST2SMS_KEY=your_key in .env file (or Render env vars)

Dev mode: If FAST2SMS_KEY is not set, OTP is printed to terminal and returned in the API response.
"""

import os
import random
import time
import requests
from flask import Blueprint, request, jsonify
from database import get_db_connection

otp_bp = Blueprint("otp_bp", __name__)

OTP_EXPIRY_SECONDS = 300          # 5 minutes
FAST2SMS_KEY = os.getenv("FAST2SMS_KEY", "")   # Set in .env or Render environment variables
# DEV_MODE = not bool(FAST2SMS_KEY)               # Auto-detected: dev if no key
DEV_MODE = True

def generate_otp() -> str:
    return str(random.randint(100000, 999999))


def send_sms_fast2sms(mobile: str, otp: str) -> bool:
    """
    Send OTP via Fast2SMS Quick SMS API.
    Free tier: 100 SMS/day, no DLT registration needed.
    Sign up at https://www.fast2sms.com → copy API key.
    """
    try:
        response = requests.post(
            "https://www.fast2sms.com/dev/bulkV2",
            headers={
                "authorization": FAST2SMS_KEY,
                "Content-Type": "application/json"
            },
            json={
                "route": "q",                   # Quick SMS route (free tier)
                "message": f"Your EVRS OTP is {otp}. Valid for 5 minutes. Do not share with anyone.",
                "language": "english",
                "flash": 0,
                "numbers": mobile
            },
            timeout=8
        )
        result = response.json()
        if result.get("return") is True:
            print(f"[SMS] OTP sent to {mobile} via Fast2SMS")
            return True
        else:
            print(f"[SMS] Fast2SMS error: {result}")
            return False
    except Exception as e:
        print(f"[SMS] Fast2SMS request failed: {e}")
        return False


def send_otp_message(mobile: str, otp: str) -> bool:
    """Route OTP through Fast2SMS in prod, print in dev."""
    if DEV_MODE:
        print(f"\n{'='*40}")
        print(f"[DEV MODE] OTP for +91 {mobile} → {otp}")
        print(f"{'='*40}\n")
        return True
    return send_sms_fast2sms(mobile, otp)


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
        # Invalidate any previous OTPs for this number
        conn.execute(
            "UPDATE otp_store SET used = 1 WHERE mobile = ? AND used = 0",
            (mobile,)
        )
        conn.execute(
            "INSERT INTO otp_store (mobile, otp, expires_at) VALUES (?, ?, ?)",
            (mobile, otp, expires_at)
        )
        conn.commit()

        success = send_otp_message(mobile, otp)
        if not success:
            return jsonify({"error": "Failed to send OTP. Try again."}), 500

        response = {"message": f"OTP sent to +91 {mobile}"}
        if DEV_MODE:
            response["otp"] = otp          # Only expose OTP in dev mode
            response["dev_mode"] = True

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
            return jsonify({"error": "Invalid OTP. Please check and try again."}), 400

        if int(time.time()) > row["expires_at"]:
            return jsonify({"error": "OTP has expired. Please request a new one."}), 400

        conn.execute("UPDATE otp_store SET used = 1 WHERE id = ?", (row["id"],))
        conn.commit()

        return jsonify({"message": "OTP verified successfully", "verified": True}), 200

    finally:
        conn.close()