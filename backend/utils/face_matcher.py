"""
face_matcher.py
---------------
Face embedding generation and comparison using DeepFace + Facenet512.

DeepFace is downloaded automatically on first use (~250 MB model weights).
Ensure you have: pip install deepface tf-keras

Thresholds (cosine similarity):
  Registration duplicate:  >= 0.72  → flag as duplicate, REJECT registration
  Booth verification:      >= 0.60  → identity confirmed
"""

import os
import json
import numpy as np

FACE_MODEL                         = "Facenet512"
FACE_DETECTOR                      = "opencv"
SIMILARITY_THRESHOLD_REGISTRATION  = 0.72
SIMILARITY_THRESHOLD_BOOTH         = 0.60

# ── Lazy import — avoids crash if deepface not installed ────────────────────
_deepface = None

def _get_deepface():
    global _deepface
    if _deepface is None:
        try:
            from deepface import DeepFace
            _deepface = DeepFace
        except ImportError:
            _deepface = False
    return _deepface


def _cosine_similarity(a: list, b: list) -> float:
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    dot  = np.dot(va, vb)
    norm = np.linalg.norm(va) * np.linalg.norm(vb)
    return float(dot / norm) if norm > 0 else 0.0


def generate_embedding(image_path: str) -> list | None:
    """
    Generate a 512-d Facenet embedding from an image file.
    Returns list[float] or None if no face detected / DeepFace unavailable.
    """
    df = _get_deepface()
    if not df:
        print("[face_matcher] DeepFace not installed — embedding skipped.")
        return None

    if not os.path.exists(image_path):
        print(f"[face_matcher] File not found: {image_path}")
        return None

    try:
        result = df.represent(
            img_path        = image_path,
            model_name      = FACE_MODEL,
            detector_backend = FACE_DETECTOR,
            enforce_detection = False,   # Don't crash if face is blurry
            align             = True
        )
        if not result:
            return None
        embedding = result[0]["embedding"]
        # Sanity check: non-zero embedding
        if all(v == 0 for v in embedding):
            return None
        return embedding
    except Exception as e:
        print(f"[face_matcher] Embedding failed for {image_path}: {e}")
        return None


def check_duplicate_registration(new_embedding: list, existing_records: list) -> dict:
    """
    Compare a new embedding against ALL stored embeddings.
    Returns:
      { is_duplicate, matched_voter_id, score, all_matches }
    """
    best_score = 0.0
    best_match = None
    all_matches = []

    for record in existing_records:
        emb_json = record.get("face_embedding")
        if not emb_json:
            continue
        try:
            stored_emb = json.loads(emb_json) if isinstance(emb_json, str) else emb_json
            score = _cosine_similarity(new_embedding, stored_emb)
            if score >= 0.50:
                all_matches.append({"voter_id": record["voter_id"], "score": round(score, 4)})
            if score > best_score:
                best_score = score
                best_match = record["voter_id"]
        except Exception:
            continue

    is_duplicate = best_score >= SIMILARITY_THRESHOLD_REGISTRATION

    return {
        "is_duplicate":      is_duplicate,
        "matched_voter_id":  best_match if is_duplicate else None,
        "score":             round(best_score, 4),
        "all_matches":       sorted(all_matches, key=lambda x: x["score"], reverse=True)
    }


def verify_voter_face(live_embedding: list, stored_embedding_json) -> dict:
    """
    Compare a live booth capture against ONE stored voter embedding.
    Returns: { match, score, confidence_label }
    """
    try:
        stored_emb = json.loads(stored_embedding_json) if isinstance(stored_embedding_json, str) else stored_embedding_json
        score = _cosine_similarity(live_embedding, stored_emb)
    except Exception as e:
        print(f"[face_matcher] verify_voter_face error: {e}")
        return {"match": False, "score": 0.0, "confidence_label": "Error"}

    match = score >= SIMILARITY_THRESHOLD_BOOTH

    if score >= 0.85:
        label = "High"
    elif score >= 0.72:
        label = "Medium"
    elif score >= 0.60:
        label = "Low"
    else:
        label = "No Match"

    return {"match": match, "score": round(score, 4), "confidence_label": label}