from backend.db import get_db

def record_audit(disbursement_id, action, details=""):
    connection = get_db()
    try:
        connection.execute(
            """
            INSERT INTO audit_logs (disbursement_id, action, details)
            VALUES (?, ?, ?)
            """,
            (disbursement_id, action, details),
        )
        connection.commit()
    finally:
        connection.close()

def get_audit_history(disbursement_id):
    connection = get_db()
    try:
        rows = connection.execute(
            """
            SELECT * FROM audit_logs
            WHERE disbursement_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (disbursement_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()
