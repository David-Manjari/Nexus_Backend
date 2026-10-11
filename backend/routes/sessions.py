"""Session-based login and logout routes.

Register ``sessions_bp`` with the Flask application and configure its secret key
from a secure environment variable before serving requests.
"""

from flask import Blueprint, jsonify, request, session

from ..user_login import authenticate_user


sessions_bp = Blueprint("sessions", __name__)


@sessions_bp.post("/login")
def login():
    """Authenticate a user and persist their identity in the Flask session."""
    data = request.get_json() if request.is_json else request.form
    identifier = data.get("identifier") or data.get("username") or data.get("email")
    password = data.get("password")

    if (
        not isinstance(identifier, str)
        or not identifier.strip()
        or not isinstance(password, str)
        or not password
    ):
        return jsonify(error="A username or email and password are required."), 400

    user = authenticate_user(identifier, password)
    if user is None:
        return jsonify(error="Invalid username/email or password."), 401

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
