from flask import Blueprint, request, jsonify
from models.voter_model import create_voter_with_documents
from database import get_db_connection

voter_bp = Blueprint("voter_bp", __name__)


# -------------------------------------------------
# REGISTER VOTER
# -------------------------------------------------

@voter_bp.route("/api/register-voter", methods=["POST"])
def register_voter():

    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid request"}), 400

    required = ["name", "dob", "gender", "phone", "email", "address"]

    for field in required:
        if field not in data:
            return jsonify({"error": f"{field} is required"}), 400

    documents = data.get("documents", [])

    if len(documents) == 0:
        return jsonify({"error": "At least one identity document required"}), 400

    allowed_docs = ["AADHAAR", "PASSPORT", "VOTER_ID", "DRIVING_LICENSE"]

    for doc in documents:
        if doc["type"] not in allowed_docs:
            return jsonify({"error": "Invalid document type"}), 400

    try:

        voter_id = create_voter_with_documents(data, documents)

        return jsonify({
            "message": "Voter registered successfully",
            "voter_id": voter_id
        }), 201

    except ValueError as e:

        return jsonify({"error": str(e)}), 400

    except Exception as e:

        return jsonify({
            "error": "Server error",
            "details": str(e)
        }), 500


# -------------------------------------------------
# GET ALL VOTERS
# -------------------------------------------------

@voter_bp.route("/api/voters", methods=["GET"])
def get_voters():

    conn = get_db_connection()
    cursor = conn.cursor()

    try:

        voters_rows = cursor.execute("""
            SELECT voter_id, name, dob, gender, address, phone, email, status, created_at
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

            voter_dict = dict(voter)

            voter_dict["documents"] = docs_map.get(voter["voter_id"], [])

            result.append(voter_dict)

        return jsonify({"voters": result}), 200

    except Exception as e:

        conn.close()

        return jsonify({
            "error": "Failed to retrieve data",
            "details": str(e)
        }), 500