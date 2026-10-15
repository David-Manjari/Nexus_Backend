"""Tests for the asset inventory routes (Member 3).

These run against the real PostgreSQL database in DATABASE_URL. Every test
creates its own throwaway users and assets and removes them afterwards, so
your normal data is left alone. If DATABASE_URL is not set, or the database is
not running, the tests are skipped.

Run:  pytest tests/test_assets.py -v
"""

import base64
import io
import os
import uuid

import psycopg
import pytest

from backend.app import create_app
from backend.db import connect_database
from backend.routes import assets as assets_module

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"), reason="DATABASE_URL is not set"
)

# A valid 1x1 PNG image.
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
MISSING_ID = 2_000_000_000


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def app():
    try:
        application = create_app(secret_key="test-secret-key")
    except psycopg.OperationalError as error:
        pytest.skip(f"Database is not available: {error}")
    application.config.update(TESTING=True)
    return application


@pytest.fixture(autouse=True)
def isolated_uploads(tmp_path, monkeypatch):
    """Send uploaded images to a temporary folder instead of backend/uploads."""
    monkeypatch.setattr(assets_module, "UPLOAD_DIR", str(tmp_path))


def _cleanup(user_ids):
    with connect_database() as connection:
        asset_ids = [
            row["asset_id"]
            for row in connection.execute(
                'SELECT asset_id FROM "Assets" WHERE added_by = ANY(%s)', (user_ids,)
            ).fetchall()
        ]
        if asset_ids:
            connection.execute(
                'DELETE FROM "Asset_Assignments" WHERE asset_id = ANY(%s)', (asset_ids,)
            )
            connection.execute(
                "DELETE FROM \"Audit_Log\" WHERE entity_type = 'asset' AND entity_id = ANY(%s)",
                (asset_ids,),
            )
            connection.execute('DELETE FROM "Assets" WHERE asset_id = ANY(%s)', (asset_ids,))
        connection.execute(
            'DELETE FROM "Asset_Assignments" WHERE user_id = ANY(%s) OR assigned_by = ANY(%s)',
            (user_ids, user_ids),
        )
        connection.execute('DELETE FROM "Users" WHERE user_id = ANY(%s)', (user_ids,))


@pytest.fixture
def users():
    """One throwaway user per role. Everything they create is removed afterwards."""
    tag = uuid.uuid4().hex[:8]
    ids, names = {}, {}
    with connect_database() as connection:
        for role in ("store_manager", "staff", "manager"):
            username = f"t_{role}_{tag}"
            row = connection.execute(
                'INSERT INTO "Users" (username, email, password_hash, role) '
                "VALUES (%s, %s, %s, %s) RETURNING user_id",
                (username, f"{username}@example.com", "not-a-real-hash", role),
            ).fetchone()
            ids[role], names[role] = row["user_id"], username
    try:
        yield {"tag": tag, "names": names, **ids}
    finally:
        _cleanup(list(ids.values()))


def _login(client, user_id):
    with client.session_transaction() as session:
        session["user_id"] = user_id


@pytest.fixture
def anonymous(app):
    return app.test_client()


@pytest.fixture
def store(app, users):
    client = app.test_client()
    _login(client, users["store_manager"])
    return client


@pytest.fixture
def staff(app, users):
    client = app.test_client()
    _login(client, users["staff"])
    return client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _create(client, tag, kind="tool", **overrides):
    unique = uuid.uuid4().hex[:8]
    payload = {"asset_type": kind, "name": f"Test {kind} {tag}-{unique}"}
    if kind == "tool":
        payload["serial_no"] = f"SN-{tag}-{unique}"
    if kind == "vehicle":
        payload["plate_no"] = f"K{unique.upper()}"
    payload.update(overrides)
    response = client.post("/assets", json=payload)
    assert response.status_code == 201, response.get_data(as_text=True)
    return response.get_json()["asset"]


def _rows(query, params=()):
    with connect_database() as connection:
        return connection.execute(query, params).fetchall()


def _status(client, asset_id):
    return client.get(f"/assets/{asset_id}").get_json()["asset"]["status"]


# ---------------------------------------------------------------------------
# Access rules
# ---------------------------------------------------------------------------
def test_login_is_required(anonymous):
    assert anonymous.get("/assets").status_code == 401
    assert anonymous.post("/assets", json={"asset_type": "tool", "name": "x"}).status_code == 401


def test_staff_and_managers_can_read_but_not_write(app, store, staff, users):
    asset = _create(store, users["tag"])
    url = f"/assets/{asset['asset_id']}"

    assert staff.get("/assets").status_code == 200
    assert staff.get(url).status_code == 200
    assert staff.post("/assets", json={"asset_type": "tool", "name": "Nope"}).status_code == 403
    assert staff.patch(url, json={"condition": "bad"}).status_code == 403
    assert staff.post(f"{url}/assign", json={"user_id": users["staff"]}).status_code == 403

    manager = app.test_client()
    _login(manager, users["manager"])
    assert manager.get("/assets").status_code == 200
    assert manager.post("/assets", json={"asset_type": "tool", "name": "Nope"}).status_code == 403


# ---------------------------------------------------------------------------
# Create, read, update
# ---------------------------------------------------------------------------
def test_store_manager_can_create_and_fetch_a_tool(store, users):
    asset = _create(store, users["tag"], category="Power tool", brand="Bosch")
    assert asset["status"] == "available"
    assert asset["added_by"] == users["store_manager"]
    assert asset["category"] == "Power tool"
    assert asset["image_url"] is None

    fetched = store.get(f"/assets/{asset['asset_id']}")
    assert fetched.status_code == 200
    assert fetched.get_json()["asset"]["name"] == asset["name"]

    found = store.get("/assets", query_string={"q": asset["serial_no"]}).get_json()["assets"]
    assert [item["asset_id"] for item in found] == [asset["asset_id"]]


@pytest.mark.parametrize(
    "payload, field",
    [
        ({"asset_type": "boat", "name": "X"}, "asset_type"),
        ({"asset_type": "tool"}, "name"),
        ({"asset_type": "vehicle", "name": "Truck"}, "plate_no"),
        ({"asset_type": "vehicle", "name": "Truck", "plate_no": "K1", "mileage": -5}, "mileage"),
    ],
)
def test_create_rejects_bad_input(store, payload, field):
    response = store.post("/assets", json=payload)
    assert response.status_code == 400
    assert field in response.get_json()["error"]


def test_duplicate_serial_number_is_rejected(store, users):
    asset = _create(store, users["tag"])
    response = store.post(
        "/assets",
        json={"asset_type": "tool", "name": "Copy", "serial_no": asset["serial_no"]},
    )
    assert response.status_code == 409


def test_vehicle_details_are_stored_filtered_and_updated(store, users):
    vehicle = _create(store, users["tag"], kind="vehicle", make="Toyota", model="Hilux", mileage=45000)
    assert (vehicle["make"], vehicle["model"], vehicle["mileage"]) == ("Toyota", "Hilux", 45000)

    only_vehicles = store.get(
        "/assets", query_string={"type": "vehicle", "q": vehicle["name"]}
    ).get_json()["assets"]
    assert [item["asset_id"] for item in only_vehicles] == [vehicle["asset_id"]]
    only_tools = store.get(
        "/assets", query_string={"type": "tool", "q": vehicle["name"]}
    ).get_json()["assets"]
    assert only_tools == []

    by_plate = store.get("/assets", query_string={"q": vehicle["plate_no"]}).get_json()["assets"]
    assert [item["asset_id"] for item in by_plate] == [vehicle["asset_id"]]

    duplicate = store.post(
        "/assets",
        json={"asset_type": "vehicle", "name": "Second", "plate_no": vehicle["plate_no"]},
    )
    assert duplicate.status_code == 409

    updated = store.patch(f"/assets/{vehicle['asset_id']}", json={"mileage": 46000})
    assert updated.status_code == 200
    assert updated.get_json()["asset"]["mileage"] == 46000

    tool = _create(store, users["tag"])
    assert store.patch(f"/assets/{tool['asset_id']}", json={"plate_no": "X1"}).status_code == 400


def test_update_asset_rules(store, users):
    asset = _create(store, users["tag"])
    url = f"/assets/{asset['asset_id']}"

    changed = store.patch(url, json={"condition": "fair", "brand": "Makita"})
    assert changed.status_code == 200
    assert changed.get_json()["asset"]["condition"] == "fair"
    assert changed.get_json()["asset"]["brand"] == "Makita"

    assert store.patch(url, json={"status": "assigned"}).status_code == 400
    assert store.patch(url, json={"status": "nonsense"}).status_code == 400
    assert store.patch(url, json={}).status_code == 400
    assert store.patch(url, json={"name": "  "}).status_code == 400

    moved = store.patch(url, json={"status": "maintenance"})
    assert moved.status_code == 200
    assert moved.get_json()["asset"]["status"] == "maintenance"


def test_unknown_ids_return_404(store, users):
    assert store.get(f"/assets/{MISSING_ID}").status_code == 404
    assert store.get(f"/assets/{MISSING_ID}/history").status_code == 404
    assert store.patch(f"/assets/{MISSING_ID}", json={"name": "x"}).status_code == 404
    assert store.post(
        f"/assets/{MISSING_ID}/assign", json={"user_id": users["staff"]}
    ).status_code == 404
    assert store.post(f"/assignments/{MISSING_ID}/return", json={}).status_code == 404


def test_list_filters(store, users):
    category = f"cat-{users['tag']}"
    tool = _create(store, users["tag"], category=category)
    vehicle = _create(store, users["tag"], kind="vehicle", category=category)
    store.patch(f"/assets/{tool['asset_id']}", json={"status": "maintenance"})

    def ids(**query):
        query["category"] = category
        found = store.get("/assets", query_string=query).get_json()["assets"]
        return {item["asset_id"] for item in found}

    assert ids() == {tool["asset_id"], vehicle["asset_id"]}
    assert ids(type="vehicle") == {vehicle["asset_id"]}
    assert ids(status="maintenance") == {tool["asset_id"]}
    assert ids(status="available") == {vehicle["asset_id"]}


# ---------------------------------------------------------------------------
# Lending: assign, history, return
# ---------------------------------------------------------------------------
def test_assign_history_and_return_flow(store, users):
    asset = _create(store, users["tag"])
    asset_id, staff_id = asset["asset_id"], users["staff"]
    assign_url = f"/assets/{asset_id}/assign"

    response = store.post(assign_url, json={"user_id": staff_id, "due_back": "2026-12-31"})
    assert response.status_code == 201
    assignment_id = response.get_json()["assignment_id"]
    assert _status(store, asset_id) == "assigned"

    assert store.post(assign_url, json={"user_id": staff_id}).status_code == 409
    assert store.patch(f"/assets/{asset_id}", json={"status": "maintenance"}).status_code == 409

    history = store.get(f"/assets/{asset_id}/history").get_json()["history"]
    assert len(history) == 1
    assert history[0]["assigned_to"] == users["names"]["staff"]
    assert history[0]["assigned_by"] == users["store_manager"]
    assert history[0]["returned_at"] is None

    notes = _rows(
        'SELECT message, notif_type FROM "Notifications" WHERE user_id = %s', (staff_id,)
    )
    assert len(notes) == 1
    assert asset["name"] in notes[0]["message"]
    assert notes[0]["notif_type"] == "asset_assigned"

    returned = store.post(f"/assignments/{assignment_id}/return", json={"return_condition": "good"})
    assert returned.status_code == 200
    assert _status(store, asset_id) == "available"
    assert store.post(f"/assignments/{assignment_id}/return", json={}).status_code == 409

    history = store.get(f"/assets/{asset_id}/history").get_json()["history"]
    assert history[0]["returned_at"] is not None
    assert history[0]["return_condition"] == "good"

    assert store.post(assign_url, json={"user_id": staff_id}).status_code == 201


def test_assign_rejects_bad_input(store, users):
    asset = _create(store, users["tag"])
    url = f"/assets/{asset['asset_id']}/assign"

    assert store.post(url, json={}).status_code == 400
    assert store.post(url, json={"user_id": users["staff"], "due_back": "next week"}).status_code == 400
    assert store.post(url, json={"user_id": users["staff"], "project_id": "abc"}).status_code == 400
    assert store.post(url, json={"user_id": MISSING_ID}).status_code == 404
    assert _status(store, asset["asset_id"]) == "available"


def test_returning_damaged_asset_sends_it_to_maintenance(store, users):
    asset = _create(store, users["tag"])
    url = f"/assets/{asset['asset_id']}/assign"
    assignment_id = store.post(url, json={"user_id": users["staff"]}).get_json()["assignment_id"]

    returned = store.post(
        f"/assignments/{assignment_id}/return",
        json={"return_condition": "damaged", "send_to_maintenance": True},
    )
    assert returned.status_code == 200

    fetched = store.get(f"/assets/{asset['asset_id']}").get_json()["asset"]
    assert fetched["status"] == "maintenance"
    assert fetched["condition"] == "damaged"

    blocked = store.post(url, json={"user_id": users["staff"]})
    assert blocked.status_code == 409
    assert "maintenance" in blocked.get_json()["error"]


def test_every_action_is_written_to_the_audit_log(store, users):
    asset = _create(store, users["tag"])
    asset_id = asset["asset_id"]
    store.patch(f"/assets/{asset_id}", json={"condition": "fair"})
    assignment_id = store.post(
        f"/assets/{asset_id}/assign", json={"user_id": users["staff"]}
    ).get_json()["assignment_id"]
    store.post(f"/assignments/{assignment_id}/return", json={})

    rows = _rows(
        'SELECT action, user_id FROM "Audit_Log" '
        "WHERE entity_type = 'asset' AND entity_id = %s ORDER BY audit_id",
        (asset_id,),
    )
    assert [row["action"] for row in rows] == [
        "asset_created", "asset_updated", "asset_assigned", "asset_returned",
    ]
    assert {row["user_id"] for row in rows} == {users["store_manager"]}


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------
def test_image_upload_download_and_replace(store, staff, users, tmp_path):
    response = store.post(
        "/assets",
        data={
            "asset_type": "tool",
            "name": f"Photo tool {users['tag']}",
            "image": (io.BytesIO(PNG_BYTES), "photo.png"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 201
    asset = response.get_json()["asset"]
    assert asset["image_path"].endswith(".png")
    assert asset["image_url"] == f"/assets/images/{asset['image_path']}"
    assert (tmp_path / asset["image_path"]).exists()

    downloaded = staff.get(asset["image_url"])
    assert downloaded.status_code == 200
    assert downloaded.data == PNG_BYTES
    assert downloaded.mimetype == "image/png"

    replaced = store.patch(
        f"/assets/{asset['asset_id']}",
        data={"image": (io.BytesIO(PNG_BYTES), "new.png")},
        content_type="multipart/form-data",
    )
    assert replaced.status_code == 200
    new_path = replaced.get_json()["asset"]["image_path"]
    assert new_path != asset["image_path"]
    assert (tmp_path / new_path).exists()
    assert not (tmp_path / asset["image_path"]).exists()


def test_image_rules(store, anonymous, tmp_path):
    wrong_type = store.post(
        "/assets",
        data={"asset_type": "tool", "name": "x", "image": (io.BytesIO(b"hello"), "notes.txt")},
        content_type="multipart/form-data",
    )
    assert wrong_type.status_code == 400
    assert "PNG, JPG or WEBP" in wrong_type.get_json()["error"]

    too_big = store.post(
        "/assets",
        data={
            "asset_type": "tool",
            "name": "x",
            "image": (io.BytesIO(b"0" * (assets_module.MAX_IMAGE_BYTES + 1)), "big.png"),
        },
        content_type="multipart/form-data",
    )
    assert too_big.status_code == 400

    assert list(tmp_path.iterdir()) == []
    assert anonymous.get("/assets/images/anything.png").status_code == 401