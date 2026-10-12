"""Request workflow: stock check, escalation and procurement conversion.

Every function takes an open database connection and runs inside the caller's
transaction, so a request and its follow-up changes are saved or undone together.
"""

REQUESTS = '"Requests"'
ASSETS = '"Assets"'
USERS = '"Users"'
PROCUREMENT = '"Procurement"'

# Who a request is escalated to, by the role of the person who raised it.
# Staff and store managers go to a manager; managers and admins go to an admin.
APPROVER_ROLE = {
    "staff": "manager",
    "store_manager": "manager",
    "manager": "admin",
    "admin": "admin",
}

PROCUREMENT_COLUMNS = (
    "procurement_id, request_id, raised_by, item_name, category, quantity, "
    "estimated_cost, supplier, reason, status, created_at, updated_at"
)


def check_stock(connection, *, asset_id=None, item_name=None, category=None, quantity=1):
    """Say whether what was asked for is in the store right now.

    A specific asset is available when its status is 'available'. A request by
    name is available when enough available assets contain that name (and match
    the category, if one was given).
    Returns {"available": bool, "asset_id": int | None, "matches": int}.
    """
    if asset_id is not None:
        row = connection.execute(
            f"SELECT status FROM {ASSETS} WHERE asset_id = %s", (asset_id,)
        ).fetchone()
        ok = row is not None and row["status"] == "available"
        return {"available": ok, "asset_id": asset_id if ok else None, "matches": int(ok)}

    if not item_name:
        return {"available": False, "asset_id": None, "matches": 0}

    sql = (
        f"SELECT asset_id FROM {ASSETS} "
        "WHERE status = 'available' AND position(lower(%s) in lower(name)) > 0"
    )
    params = [item_name]
    if category:
        sql += " AND lower(category) = lower(%s)"
        params.append(category)
    rows = connection.execute(sql + " ORDER BY asset_id", params).fetchall()
    ok = len(rows) >= max(quantity, 1)
    return {
        "available": ok,
        "asset_id": rows[0]["asset_id"] if ok else None,
        "matches": len(rows),
    }


def pick_approver(connection, requester_role, requester_id):
    """Pick the approver with the fewest open escalated requests, or None."""
    approver_role = APPROVER_ROLE.get(requester_role, "manager")
    row = connection.execute(
        f"""
        SELECT u.user_id
        FROM {USERS} u
        LEFT JOIN {REQUESTS} r ON r.escalated_to = u.user_id AND r.status = 'escalated'
        WHERE u.role = %s AND u.user_id <> %s
        GROUP BY u.user_id
        ORDER BY COUNT(r.request_id), u.user_id
        LIMIT 1
        """,
        (approver_role, requester_id),
    ).fetchone()
    return row["user_id"] if row else None


def escalate_request(connection, request_id, approver_id):
    """Hand a request to an approver and mark it escalated."""
    connection.execute(
        f"""
        UPDATE {REQUESTS}
        SET status = 'escalated', escalated_to = %s, updated_at = NOW()
        WHERE request_id = %s
        """,
        (approver_id, request_id),
    )


def convert_to_procurement(connection, request_id, *, raised_by, **overrides):
    """Turn an asset request into a draft procurement and mark it converted.

    Anything in overrides (item_name, category, quantity, estimated_cost,
    supplier, reason) replaces the value copied from the request.
    Returns the new procurement row.
    """
    req = connection.execute(
        f"""
        SELECT request_id, asset_id, item_name, category, quantity, reason
        FROM {REQUESTS} WHERE request_id = %s FOR UPDATE
        """,
        (request_id,),
    ).fetchone()

    item_name = req["item_name"]
    category = req["category"]
    if req["asset_id"] is not None and not (item_name and category):
        asset = connection.execute(
            f"SELECT name, category FROM {ASSETS} WHERE asset_id = %s", (req["asset_id"],)
        ).fetchone()
        if asset:
            item_name = item_name or asset["name"]
            category = category or asset["category"]

    values = {
        "item_name": item_name,
        "category": category,
        "quantity": req["quantity"],
        "estimated_cost": None,
        "supplier": None,
        "reason": req["reason"],
    }
    values.update({key: value for key, value in overrides.items() if value is not None})

    procurement = connection.execute(
        f"""
        INSERT INTO {PROCUREMENT}
            (request_id, raised_by, item_name, category, quantity,
             estimated_cost, supplier, reason)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING {PROCUREMENT_COLUMNS}
        """,
        (request_id, raised_by, values["item_name"], values["category"],
         values["quantity"], values["estimated_cost"], values["supplier"],
         values["reason"]),
    ).fetchone()
    connection.execute(
        f"UPDATE {REQUESTS} SET status = 'converted', updated_at = NOW() WHERE request_id = %s",
        (request_id,),
    )
    return procurement
