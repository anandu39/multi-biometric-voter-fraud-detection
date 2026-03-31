"""
biometric_model.py
------------------
Database operations for biometric storage and retrieval.
"""

import json
import os
from database import get_db_connection


def get_all_face_embeddings(exclude_voter_id: int = None) -> list:
    """
    Fetch all stored face embeddings for duplicate checking.
    Optionally exclude a specific voter (for re-upload scenarios).
    Returns list of dicts: { voter_id, face_embedding }
    """
    conn = get_db_connection()
    try:
        if exclude_voter_id:
            rows = conn.execute(
                "SELECT voter_id, face_embedding FROM biometrics WHERE face_embedding IS NOT NULL AND voter_id != ?",
                (exclude_voter_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT voter_id, face_embedding FROM biometrics WHERE face_embedding IS NOT NULL"
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def save_biometrics(voter_id: int, data: dict) -> int:
    """
    Insert or update biometric record for a voter.
    data keys: face_image_path, iris_image_path, fingerprint_path,
               face_embedding (list), iris_embedding, biometric_hash
    Returns biometric_id.
    """
    conn = get_db_connection()
    try:
        existing = conn.execute(
            "SELECT biometric_id FROM biometrics WHERE voter_id = ?", (voter_id,)
        ).fetchone()

        face_emb_json = json.dumps(data.get("face_embedding")) if data.get("face_embedding") else None

        if existing:
            conn.execute("""
                UPDATE biometrics SET
                    face_image_path    = COALESCE(?, face_image_path),
                    iris_image_path    = COALESCE(?, iris_image_path),
                    fingerprint_path   = COALESCE(?, fingerprint_path),
                    face_embedding     = COALESCE(?, face_embedding),
                    biometric_hash     = COALESCE(?, biometric_hash)
                WHERE voter_id = ?
            """, (
                data.get("face_image_path"),
                data.get("iris_image_path"),
                data.get("fingerprint_path"),
                face_emb_json,
                data.get("biometric_hash"),
                voter_id
            ))
            conn.commit()
            return existing["biometric_id"]
        else:
            cur = conn.execute("""
                INSERT INTO biometrics
                    (voter_id, face_image_path, iris_image_path, fingerprint_path,
                     face_embedding, biometric_hash)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                voter_id,
                data.get("face_image_path"),
                data.get("iris_image_path"),
                data.get("fingerprint_path"),
                face_emb_json,
                data.get("biometric_hash")
            ))
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()


def get_biometrics_for_voter(voter_id: int) -> dict | None:
    """Return the biometric record for a voter, or None."""
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT * FROM biometrics WHERE voter_id = ?", (voter_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_voters_without_biometrics() -> list:
    """
    Return voters who have NO biometric record at all,
    or have a record with no face_image_path (face is mandatory).
    """
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT v.voter_id, v.name, v.phone, v.ward_number,
                   v.district, v.created_at,
                   b.face_image_path, b.iris_image_path, b.fingerprint_path
            FROM voters v
            LEFT JOIN biometrics b ON v.voter_id = b.voter_id
            WHERE v.status = 'active'
              AND (b.biometric_id IS NULL OR b.face_image_path IS NULL)
            ORDER BY v.voter_id DESC
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def log_fraud_alert(voter_id: int, matched_voter_id: int, face_score: float,
                    iris_score: float, fingerprint_score: float,
                    final_score: float, reason: str):
    """Insert a fraud alert record."""
    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO fraud_alerts
                (voter_id, matched_voter_id, face_score, iris_score,
                 fingerprint_score, final_score, alert_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (voter_id, matched_voter_id, face_score, iris_score,
              fingerprint_score, final_score, reason))
        conn.commit()
    finally:
        conn.close()