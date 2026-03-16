from database import get_db_connection
import sqlite3


def create_voter_with_documents(data, documents):

    conn = get_db_connection()
    cursor = conn.cursor()

    try:

        # Begin transaction
        conn.execute("BEGIN")

        voter_query = """
        INSERT INTO voters
        (name, dob, gender, address, phone, email, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """

        cursor.execute(
            voter_query,
            (
                data["name"],
                data["dob"],
                data["gender"],
                data["address"],
                data["phone"],
                data["email"],
                "active",
            )
        )

        voter_id = cursor.lastrowid

        doc_query = """
        INSERT INTO identity_documents
        (voter_id, document_type, document_number)
        VALUES (?, ?, ?)
        """

        for doc in documents:

            cursor.execute(
                doc_query,
                (
                    voter_id,
                    doc["type"],
                    doc["number"]
                )
            )

        conn.commit()

        return voter_id

    except sqlite3.IntegrityError:

        conn.rollback()
        raise ValueError("Duplicate document detected")

    finally:

        conn.close()