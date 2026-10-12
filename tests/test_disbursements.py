import pytest

from backend.app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True

    with app.test_client() as test_client:
        yield test_client


def test_flask_application_loads():
    assert app is not None


def test_disbursement_routes_are_registered():
    rules = [
        rule.rule.lower()
        for rule in app.url_map.iter_rules()
    ]

    relevant_routes = [
        route for route in rules
        if any(word in route for word in (
            "disbursement",
            "payout",
            "payment",
            "history",
            "record",
        ))
    ]

    assert relevant_routes, (
        "No disbursement, payout, payment, "
        "history, or record routes were registered."
    )


def test_disbursement_endpoints_respond(client):
    routes = [
        rule for rule in app.url_map.iter_rules()
        if any(word in rule.rule.lower() for word in (
            "disbursement",
            "payout",
            "payment",
            "history",
            "record",
        ))
        and "GET" in rule.methods
        and "HEAD" not in rule.methods
    ]

    assert routes, "No relevant GET endpoints found."

    for rule in routes:
        response = client.get(rule.rule)
        assert response.status_code != 404, (
            f"Endpoint returned 404: {rule.rule}"
        )
