"""Session-based login and logout routes.

Register ``sessions_bp`` with the Flask application and configure its secret key
from a secure environment variable before serving requests.
"""

from flask import Blueprint, jsonify, request, session

from ..admin_accounts import MIN_PASSWORD_LENGTH
from ..user_login import AuthenticationError, authenticate_user


sessions_bp = Blueprint("sessions", __name__)


@sessions_bp.post("/login")
def login():
    """Authenticate a user and persist their identity in the Flask session."""
    data = request.get_json(silent=True) if request.is_json else request.form
    if not hasattr(data, "get"):
        data = {}
    identifier = data.get("identifier") or data.get("username") or data.get("email")
    password = data.get("password")

    if not isinstance(identifier, str) or not identifier.strip():
        return jsonify(error="Username or email is required."), 400
    if not isinstance(password, str) or not password:
        return jsonify(error="Password is required."), 400
    if len(password) < MIN_PASSWORD_LENGTH:
        return jsonify(
            error=f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
        ), 400

    try:
        user = authenticate_user(identifier, password)
    except AuthenticationError as error:
        return jsonify(error=str(error)), error.status_code

    session.clear()
    session.permanent = True
    session["user_id"] = user["user_id"]
    session["username"] = user["username"]
    session["role"] = user["role"]

    return jsonify(
        message="Logged in successfully.",
        user={
            "user_id": user["user_id"],
            "username": user["username"],
            "email": user["email"],
            "role": user["role"],
        },
    ), 200


@sessions_bp.post("/logout")
def logout():
    """Clear the current user's session."""
    session.clear()
    return jsonify(message="Logged out successfully."), 200
