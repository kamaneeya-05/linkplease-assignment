"""Tests for rules endpoints."""
import pytest
from app.database import Rule


def test_create_rule(client, db):
    """Test creating a rule."""
    response = client.post(
        "/rules",
        json={
            "keyword": "PRICE",
            "dm_message": "Here's the price list: $99.99",
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["keyword"] == "PRICE"
    assert data["dm_message"] == "Here's the price list: $99.99"
    assert data["rule_id"].startswith("rule_")


def test_create_rule_validation(client):
    """Test rule creation validation."""
    # Missing required fields
    response = client.post(
        "/rules",
        json={"keyword": "PRICE"}
    )
    assert response.status_code == 422


def test_list_rules(client, sample_rule):
    """Test listing rules."""
    response = client.get("/rules")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert data[0]["keyword"] == "PRICE"


def test_rule_case_insensitive_matching(client, db):
    """Test that keywords are stored with original case but matched case-insensitively."""
    # Create rule with mixed case keyword
    response = client.post(
        "/rules",
        json={
            "keyword": "PrIcE",
            "dm_message": "Price info",
        }
    )
    assert response.status_code == 201
    
    # Verify both the keyword and normalized version
    rule = db.query(Rule).first()
    assert rule.keyword == "PrIcE"
    assert rule.keyword_normalized == "price"
