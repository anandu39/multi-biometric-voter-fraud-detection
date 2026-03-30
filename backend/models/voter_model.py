from database import get_db_connection
import sqlite3


def create_voter_with_documents(data: dict, documents: list) -> int:
    """
    Insert a voter and their identity documents in a single transaction.
    Returns the new voter_id.
    Raises ValueError on duplicate document.
    """

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        conn.execute("BEGIN")

        cursor.execute("""
            INSERT INTO voters (
                name, dob, gender, parent_name, occupation,
                phone, email,
                street, ward_number, panchayat, taluk,
                district, state, pincode, constituency,
                address, status, officer_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data["name"],
            data.get("dob"),
            data.get("gender"),
            data.get("parent_name"),
            data.get("occupation"),
            data.get("phone"),
            data.get("email"),
            data.get("street"),
            data.get("ward_number"),
            data.get("panchayat"),
            data.get("taluk"),
            data.get("district"),
            data.get("state"),
            data.get("pincode"),
            data.get("constituency"),
            data.get("address"),
            "active",
            data.get("officer_id")
        ))

        voter_id = cursor.lastrowid

        for doc in documents:
            cursor.execute("""
                INSERT INTO identity_documents (voter_id, document_type, document_number)
                VALUES (?, ?, ?)
            """, (
                voter_id,
                doc["type"],
                doc["number"]
            ))

        conn.commit()
        return voter_id

    except sqlite3.IntegrityError:
        conn.rollback()
        raise ValueError("A document with this number already exists in the system")

    finally:
        conn.close()