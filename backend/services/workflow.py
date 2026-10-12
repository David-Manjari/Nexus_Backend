from backend.db import get_db
from backend.integrations.payment_client import simulate_payment
from backend.services.audit import record_audit

def process_disbursement(disbursement_id, simulated_result="paid"):
    connection = get_db()

    try:
        connection.execute("BEGIN IMMEDIATE")

        row = connection.execute(
            "SELECT * FROM disbursements WHERE id = ?",
            (disbursement_id,),
        ).fetchone()

        if row is None:
            raise LookupError("Disbursement not found.")

        if row["status"] != "pending":
            raise ValueError(
                f"Only pending payouts can be processed. "
                f"Current status: {row['status']}."
            )

        connection.execute(
            """
            UPDATE disbursements
            SET status = 'processing', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (disbursement_id,),
        )
        connection.commit()

        result = simulate_payment(
            row["amount"],
            row["currency"],
            simulated_result,
        )

        connection.execute("BEGIN IMMEDIATE")
        failure_reason = (
            result["message"] if result["status"] == "failed" else None
        )

        connection.execute(
            """
            UPDATE disbursements
            SET status = ?,
                payment_reference = ?,
                failure_reason = ?,
                updated_at = CURRENT_TIMESTAMP,
                paid_at = CASE
                    WHEN ? = 'paid' THEN CURRENT_TIMESTAMP
                    ELSE NULL
                END
            WHERE id = ?
            """,
            (
                result["status"],
                result["payment_reference"],
                failure_reason,
                result["status"],
                disbursement_id,
            ),
        )

        connection.execute(
            """
            INSERT INTO payment_history
                (disbursement_id, reference, payment_reference,
                 amount, currency, status, message)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                disbursement_id,
                row["reference"],
                result["payment_reference"],
                row["amount"],
                row["currency"],
                result["status"],
                result["message"],
            ),
        )

        connection.execute(
            """
            INSERT INTO audit_logs (disbursement_id, action, details)
            VALUES (?, ?, ?)
            """,
            (
                disbursement_id,
                "payout_" + result["status"],
                result["message"],
            ),
        )

        connection.commit()

        updated = connection.execute(
            "SELECT * FROM disbursements WHERE id = ?",
            (disbursement_id,),
        ).fetchone()

        return dict(updated), result

    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
