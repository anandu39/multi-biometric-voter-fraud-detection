"""
face_matcher.py
---------------
Handles all face embedding generation and comparison using DeepFace + VGG-Face.

Key design:
- Embeddings are stored as JSON arrays in the biometrics table
- On registration: new face is compared against ALL stored embeddings
- On booth verification: incoming face is compared against ONE stored embedding
- Threshold: 0.70 cosine similarity = duplicate flag during registration
- Returns structured results so routes can decide what to do
"""

import os
import json
import numpy as np

# ── Config ──────────────────────────────────────────────────────────────────
FACE_MODEL       = "VGG-Face"
FACE_DETECTOR    = "opencv"          # fastest detector, works offline
SIMILARITY_THRESHOLD_REGISTRATION = 0.70   # flag duplicate if >= this
SIMILARITY_THRESHOLD_BOOTH         = 0.65   # allow voter if >= this


def _cosine_similarity(a: list, b: list) -> float:
    """Cosine similarity between two embedding vectors."""
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    dot = np.dot(va, vb)
    norm = np.linalg.norm(va) * np.linalg.norm(vb)
    if norm == 0:
        return 0.0
    return float(dot / norm)


def generate_embedding(image_path: str) -> list | None:
    """
    Generate a face embedding from an image file.
    Returns a list of floats, or None if no face detected.
    """
    try:
        from deepface import DeepFace
        result = DeepFace.represent(
            img_path=image_path,
            model_name=FACE_MODEL,
            detector_backend=FACE_DETECTOR,
            enforce_detection=True
        )
        return result[0]["embedding"]
    except Exception as e:
        print(f"[DeepFace] Embedding failed for {image_path}: {e}")
        return None


def check_duplicate_registration(new_embedding: list, existing_records: list) -> dict:
    """
    Compare a new embedding against all stored embeddings.

    existing_records: list of dicts with keys: voter_id, face_embedding (JSON string)

    Returns:
        {
            "is_duplicate": bool,
            "matched_voter_id": int | None,
            "score": float,           # highest similarity found
            "all_matches": list        # all records above 0.5 similarity
        }
    """
    best_score = 0.0
    best_match = None
    all_matches = []

    for record in existing_records:
        emb_json = record.get("face_embedding")
        if not emb_json:
            continue
        try:
            stored_emb = json.loads(emb_json)
            score = _cosine_similarity(new_embedding, stored_emb)
            if score >= 0.50:
                all_matches.append({
                    "voter_id": record["voter_id"],
                    "score": round(score, 4)
                })
            if score > best_score:
                best_score = score
                best_match = record["voter_id"]
        except Exception:
            continue

    is_duplicate = best_score >= SIMILARITY_THRESHOLD_REGISTRATION

    return {
        "is_duplicate": is_duplicate,
        "matched_voter_id": best_match if is_duplicate else None,
        "score": round(best_score, 4),
        "all_matches": sorted(all_matches, key=lambda x: x["score"], reverse=True)
    }


def verify_voter_face(live_embedding: list, stored_embedding_json: str) -> dict:
    """
    Verify a live face against a single stored voter embedding (booth use).

    Returns:
        {
            "match": bool,
            "score": float,
            "confidence_label": str   # "High" / "Medium" / "Low" / "No Match"
        }
    """
    try:
        stored_emb = json.loads(stored_embedding_json)
        score = _cosine_similarity(live_embedding, stored_emb)
    except Exception:
        return {"match": False, "score": 0.0, "confidence_label": "Error"}

    match = score >= SIMILARITY_THRESHOLD_BOOTH

    if score >= 0.85:
        label = "High"
    elif score >= 0.70:
        label = "Medium"
    elif score >= 0.65:
        label = "Low"
    else:
        label = "No Match"

    return {
        "match": match,
        "score": round(score, 4),
        "confidence_label": label
    }