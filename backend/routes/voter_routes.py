from flask import Blueprint, request, jsonify
from models.voter_model import create_voter_with_documents
from database import get_db_connection

voter_bp = Blueprint("voter_bp", __name__)


# ─────────────────────────────────────────
# REGISTER VOTER
# ─────────────────────────────────────────

@voter_bp.route("/api/register-voter", methods=["POST"])
def register_voter():

    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid request body"}), 400

    required = ["name", "dob", "gender", "phone", "address"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"'{field}' is required"}), 400

    documents = data.get("documents", [])
    if not documents:
        return jsonify({"error": "At least one identity document is required"}), 400

    allowed_docs = {"AADHAAR", "PASSPORT", "VOTER_ID", "DRIVING_LICENSE", "PAN", "RATION_CARD"}
    for doc in documents:
        if doc.get("type") not in allowed_docs:
            return jsonify({"error": f"Invalid document type: {doc.get('type')}"}), 400
        if not doc.get("number"):
            return jsonify({"error": "Document number is required"}), 400

    try:
        voter_id = create_voter_with_documents(data, documents)
        return jsonify({
            "message": "Voter enrolled successfully",
            "voter_id": voter_id
        }), 201

    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    except Exception as e:
        return jsonify({"error": "Server error", "details": str(e)}), 500


# ─────────────────────────────────────────
# GET ALL VOTERS (with documents)
# ─────────────────────────────────────────

@voter_bp.route("/api/voters", methods=["GET"])
def get_voters():

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        voters_rows = cursor.execute("""
            SELECT voter_id, name, dob, gender, parent_name, occupation,
                   phone, email, street, ward_number, panchayat, taluk,
                   district, state, pincode, constituency, address,
                   status, officer_id, created_at
            FROM voters
            ORDER BY voter_id DESC
        """).fetchall()

        docs_rows = cursor.execute("""
            SELECT voter_id, document_type, document_number, verified
            FROM identity_documents
        """).fetchall()

        conn.close()

        docs_map = {}
        for doc in docs_rows:
            vid = doc["voter_id"]
            if vid not in docs_map:
                docs_map[vid] = []
            docs_map[vid].append(dict(doc))

        result = []
        for voter in voters_rows:
            vd = dict(voter)
            vd["documents"] = docs_map.get(voter["voter_id"], [])
            result.append(vd)

        return jsonify({"voters": result}), 200

    except Exception as e:
        conn.close()
        return jsonify({"error": "Failed to retrieve voters", "details": str(e)}), 500


# ─────────────────────────────────────────
# GET SINGLE VOTER
# ─────────────────────────────────────────

@voter_bp.route("/api/voters/<int:voter_id>", methods=["GET"])
def get_voter(voter_id):
    conn = get_db_connection()
    try:
        voter = conn.execute(
            "SELECT * FROM voters WHERE voter_id = ?", (voter_id,)
        ).fetchone()

        if not voter:
            return jsonify({"error": "Voter not found"}), 404

        docs = conn.execute(
            "SELECT * FROM identity_documents WHERE voter_id = ?", (voter_id,)
        ).fetchall()

        voter_dict = dict(voter)
        voter_dict["documents"] = [dict(d) for d in docs]
        return jsonify(voter_dict), 200

    finally:
        conn.close()