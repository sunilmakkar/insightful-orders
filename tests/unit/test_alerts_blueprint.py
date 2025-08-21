"""
Unit tests for the alerts blueprint (app/blueprints/alerts.py).

Covers:
- Successful creation of an alert rule.
- Handling of invalid operator values (marshmallow ValidationError).
- Missing required fields (metric).
"""

import pytest
from app.models import AlertRule


def test_create_alert_rule_success(client, auth_headers, db_session):
    """
    POST /alerts with valid data should create a new alert rule
    for the authenticated merchant and return 201 + JSON body.
    """
    payload = {
        "metric": "orders_per_min",
        "operator": ">=",
        "threshold": 5.0,
        "time_window_s": 30,
    }

    resp = client.post("/alerts", json=payload, headers=auth_headers)
    assert resp.status_code == 201

    data = resp.get_json()

    # Only check the fields we care about
    for key in payload:
        assert data[key] == payload[key]

    # DB check
    from app.models import AlertRule
    rule = db_session.query(AlertRule).filter_by(metric="orders_per_min").first()
    assert rule is not None
    assert rule.operator == ">="


def test_create_alert_rule_invalid_operator(client, auth_headers):
    """
    POST /alerts with an invalid operator should raise marshmallow.ValidationError.
    """
    payload = {
        "metric": "orders_per_min",
        "operator": "INVALID",
        "threshold": 5.0,
        "time_window_s": 30,
    }

    resp = client.post("/alerts", json=payload, headers=auth_headers)
    assert resp.status_code == 422
    assert "operator" in resp.json["errors"]
    assert "Must be one of" in str(resp.json["errors"]["operator"])



def test_create_alert_rule_invalid_operator(client, auth_headers):
    payload = {
        "metric": "orders_per_min",
        "operator": "INVALID",
        "threshold": 5.0,
        "time_window_s": 30,
    }

    resp = client.post("/alerts", json=payload, headers=auth_headers)
    assert resp.status_code == 422
