"""User credential authentication."""

from werkzeug.security import check_password_hash

from .admin_accounts import connect_database


def authenticate_user(identifier, password, *, database_url=None):
    """Return a safe user record if the username/email and password are valid."""
    if not isinstance(identifier, str) or not identifier.strip():
        return None
    if not isinstance(password, str) or not password:
        return None

    identifier = identifier.strip()
    with connect_database(database_url) as connection:
        user = connection.execute(
            """
            SELECT user_id, username, email, password_hash, role
            FROM "Users"
            WHERE (username = %s OR email = %s) AND is_active = TRUE
            LIMIT 1
            """,
            (identifier, identifier),
        ).fetchone()

    if user is None or not check_password_hash(user["password_hash"], password):
        return None

    return {
        "user_id": user["user_id"],
        "username": user["username"],
        "email": user["email"],
        "role": user["role"],
    }
