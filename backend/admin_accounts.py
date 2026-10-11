import argparse
import os
import re
from getpass import getpass

import psycopg
from psycopg.rows import dict_row
from werkzeug.security import generate_password_hash


ROLES = ("admin", "manager", "finance", "staff")
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,64}$")
MIN_PASSWORD_LENGTH = 12
BOOTSTRAP_LOCK_ID = 726381942105


def connect_database(database_url=None):
    """Connect to the existing PostgreSQL database configured by DATABASE_URL."""
    database_url = database_url or os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set")
    return psycopg.connect(database_url, connect_timeout=10, row_factory=dict_row)


def _validate_account(username, email, password, role):
    username = username.strip()
    email = email.strip()

    if not USERNAME_PATTERN.fullmatch(username):
        raise ValueError("Username must be 3-64 letters, digits, '.', '_' or '-'.")
    if not email or len(email) > 254 or "@" not in email:
        raise ValueError("A valid email address is required.")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if role not in ROLES:
        raise ValueError(f"Role must be one of: {', '.join(ROLES)}.")

    return username, email


def create_account(admin_user_id, username, email, password, role, *, database_url=None):
    """Create an account after verifying the requesting user is an admin.

    Call this from the backend handler for the admin-only account creation page.
    The role is checked against the database, rather than trusted from the caller.
    """
    username, email = _validate_account(username, email, password, role)
    with connect_database(database_url) as connection:
        admin = connection.execute(
            'SELECT role FROM "Users" WHERE user_id = %s',
            (admin_user_id,),
        ).fetchone()
        if admin is None or admin["role"] != "admin":
            raise PermissionError("Only an admin account can create accounts.")

        account = connection.execute(
            """
            INSERT INTO "Users" (username, email, password_hash, role)
            VALUES (%s, %s, %s, %s)
            RETURNING user_id, username, email, role
            """,
            (username, email, generate_password_hash(password), role),
        ).fetchone()
        return account


def bootstrap_first_admin(username, email, password, *, database_url=None):
    """Create the initial admin once, only if the Users table has no admin yet."""
    username, email = _validate_account(username, email, password, "admin")
    with connect_database(database_url) as connection:
        connection.execute("SELECT pg_advisory_xact_lock(%s)", (BOOTSTRAP_LOCK_ID,))
        existing_admin = connection.execute(
            'SELECT 1 FROM "Users" WHERE role = %s LIMIT 1',
            ("admin",),
        ).fetchone()
        if existing_admin is not None:
            raise RuntimeError("An admin account already exists; bootstrap is disabled.")

        account = connection.execute(
            """
            INSERT INTO "Users" (username, email, password_hash, role)
            VALUES (%s, %s, %s, %s)
            RETURNING user_id, username, email, role
            """,
            (username, email, generate_password_hash(password), "admin"),
        ).fetchone()
        return account


def main():
    parser = argparse.ArgumentParser(
        description="One-time setup for the first admin in the existing Users table."
    )
    parser.add_argument(
        "command",
        choices=("bootstrap-admin",),
        help="Create an initial admin only if no admin exists yet.",
    )
    parser.add_argument("--username", required=True)
    parser.add_argument("--email", required=True)
    args = parser.parse_args()

    password = getpass("Initial admin password: ")
    confirmation = getpass("Confirm password: ")
    if password != confirmation:
        parser.error("Passwords do not match.")

    account = bootstrap_first_admin(args.username, args.email, password)
    print(f"Created initial admin account {account['username']} (user ID {account['user_id']}).")


if __name__ == "__main__":
    main()
