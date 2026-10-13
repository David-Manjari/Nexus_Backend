"""Admin-only user account activity API."""

from flask import Blueprint, jsonify, session

from ..auth import roles_required
from ..services.audit import AuditSchemaNotConfigured, get_account_activity


users_bp = Blueprint("users", __name__)


@users_bp.get("/accounts/activity")
@roles_required("admin")
def account_activity():
    """List other user accounts, their status, and last login time."""
    try:
        accounts = get_account_activity(session["user_id"])
    except AuditSchemaNotConfigured as error:
        return jsonify(error=str(error)), 503

    return jsonify(accounts=accounts), 200