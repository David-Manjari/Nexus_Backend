import uuid

from flask import Blueprint, jsonify, request

from backend.db import get_db
from backend.services.audit import record_audit, get_audit_history
from backend.services.workflow import process_disbursement

disbursements_bp = Blueprint(
    "disbursements",
    __name__,
    url_prefix="/api",
)

VALID_STATUSES = {"pending", "processing", "paid", "failed"}

@disbursements_bp.get("/disbursements")
def list_disbursements():
    status = request.args.get("status")
    connection = get_db()

    try:
        if status:
            if status not in VALID_STATUSES:
                return jsonify(error="Invalid payout status."), 400

            rows = connection.execute(
                """
                SELECT * FROM disbursements
                WHERE status = ?
                ORDER BY created_at DESC, id DESC
                """,
                (status,),
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT * FROM disbursements
                ORDER BY created_at DESC, id DESC
                """
            ).fetchall()

        return jsonify([dict(row) for row in rows]), 200
    finally:
        connection.close()

@disbursements_bp.get("/disbursements/summary")
def disbursement_summary():
    connection = get_db()

    try:
        rows = connection.execute(
            """
            SELECT status, COUNT(*) AS count,
                   COALESCE(SUM(amount), 0) AS total
            FROM disbursements
            GROUP BY status
            """
        ).fetchall()

        summary = {
            status: {"count": 0, "total": 0.0}
            for status in VALID_STATUSES
        }

        for row in rows:
            summary[row["status"]] = {
                "count": row["count"],
                "total": row["total"],
            }

        return jsonify(summary), 200
    finally:
        connection.close()

@disbursements_bp.post("/disbursements")
def create_disbursement():
    data = request.get_json(silent=True) or {}

    payee = data.get("payee")
    description = data.get("description", "")
    currency = data.get("currency", "KES")

    if not isinstance(payee, str) or not payee.strip():
        return jsonify(error="A payee name is required."), 400

    if not isinstance(description, str):
        return jsonify(error="Description must be text."), 400

    if not isinstance(currency, str) or not currency.strip():
        return jsonify(error="A currency is required."), 400

    try:
        amount = float(data.get("amount"))
    except (TypeError, ValueError):
        return jsonify(error="Amount must be a valid number."), 400

    if amount <= 0 or amount != amount or amount == float("inf"):
        return jsonify(error="Amount must be a finite positive number."), 400

    reference = "NEX-" + uuid.uuid4().hex[:10].upper()
    connection = get_db()

    try:
        cursor = connection.execute(
            """
            INSERT INTO disbursements
                (reference, payee, amount, currency, description)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                reference,
                payee.strip(),
                amount,
                currency.strip().upper(),
                description.strip(),
            ),
        )
        disbursement_id = cursor.lastrowid

        connection.execute(
            """
            INSERT INTO audit_logs (disbursement_id, action, details)
            VALUES (?, 'payout_created', ?)
            """,
            (disbursement_id, f"Payout created for {payee.strip()}."),
        )
        connection.commit()

        row = connection.execute(
            "SELECT * FROM disbursements WHERE id = ?",
            (disbursement_id,),
        ).fetchone()

        return jsonify(dict(row)), 201
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

@disbursements_bp.get("/disbursements/<int:disbursement_id>")
def get_disbursement(disbursement_id):
    connection = get_db()

    try:
        row = connection.execute(
            "SELECT * FROM disbursements WHERE id = ?",
            (disbursement_id,),
        ).fetchone()

        if row is None:
            return jsonify(error="Disbursement not found."), 404

        return jsonify(dict(row)), 200
    finally:
        connection.close()

@disbursements_bp.post("/disbursements/<int:disbursement_id>/process")
def process_payout(disbursement_id):
    data = request.get_json(silent=True) or {}
    simulated_result = data.get("simulated_result", "paid")

    if simulated_result not in ("paid", "failed"):
        return jsonify(
            error="simulated_result must be 'paid' or 'failed'."
        ), 400

    try:
        payout, result = process_disbursement(
            disbursement_id,
            simulated_result,
        )
        return jsonify(
            disbursement=payout,
            payment=result,
        ), 200
    except LookupError as error:
        return jsonify(error=str(error)), 404
    except ValueError as error:
        return jsonify(error=str(error)), 409

@disbursements_bp.get("/disbursements/<int:disbursement_id>/history")
def disbursement_history(disbursement_id):
    connection = get_db()

    try:
        exists = connection.execute(
            "SELECT id FROM disbursements WHERE id = ?",
            (disbursement_id,),
        ).fetchone()

        if exists is None:
            return jsonify(error="Disbursement not found."), 404

        payments = connection.execute(
            """
            SELECT * FROM payment_history
            WHERE disbursement_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (disbursement_id,),
        ).fetchall()

        return jsonify(
            payments=[dict(row) for row in payments],
            audit=get_audit_history(disbursement_id),
        ), 200
    finally:
        connection.close()

@disbursements_bp.get("/payment-history")
def payment_history():
    connection = get_db()

    try:
        rows = connection.execute(
            """
            SELECT * FROM payment_history
            ORDER BY created_at DESC, id DESC
            """
        ).fetchall()

        return jsonify([dict(row) for row in rows]), 200
    finally:
        connection.close()
