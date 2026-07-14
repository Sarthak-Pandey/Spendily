import pytest
import sqlite3
from app import app as flask_app
from database.db import get_db, init_db, seed_db, create_user
from database.queries import (
    get_user_by_id,
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown
)

@pytest.fixture
def app():
    flask_app.config.update({
        "TESTING": True,
        "SECRET_KEY": "test-key"
    })
    import os
    from database.db import DATABASE_PATH
    if os.path.exists(DATABASE_PATH) and "spendly_test.db" in DATABASE_PATH:
        try:
            os.remove(DATABASE_PATH)
        except Exception:
            pass
    with flask_app.app_context():
        init_db()
        seed_db()
    yield flask_app

@pytest.fixture
def client(app):
    return app.test_client()

# ------------------------------------------------------------------ #
# Unit Tests for queries.py                                          #
# ------------------------------------------------------------------ #

def test_get_user_by_id(app):
    with app.app_context():
        # Test valid user (demo user has id 1)
        user = get_user_by_id(1)
        assert user is not None
        assert user["name"] == "Demo User"
        assert user["email"] == "demo@spendly.com"
        assert "202" in user["member_since"]  # e.g., "July 2026" or current year

        # Test non-existent user
        none_user = get_user_by_id(9999)
        assert none_user is None

def test_get_summary_stats(app):
    with app.app_context():
        # Get demo user stats (demo user id is 1)
        stats = get_summary_stats(1)
        assert stats["transaction_count"] == 8
        assert stats["top_category"] == "Bills"
        
        # Verify total_spent by querying database directly
        conn = get_db()
        expected_total = conn.execute(
            "SELECT SUM(amount) FROM expenses WHERE user_id = 1;"
        ).fetchone()[0]
        assert stats["total_spent"] == expected_total

        # Test a user with no expenses
        # Create a new user first
        try:
            no_exp_user_id = create_user("No Exp User", "noexp@spendly.com", "pass123")
        except sqlite3.IntegrityError:
            # User already exists from previous runs, retrieve it
            conn = get_db()
            row = conn.execute("SELECT id FROM users WHERE email = ?;", ("noexp@spendly.com",)).fetchone()
            no_exp_user_id = row["id"]
            
        stats_empty = get_summary_stats(no_exp_user_id)
        assert stats_empty["total_spent"] == 0
        assert stats_empty["transaction_count"] == 0
        assert stats_empty["top_category"] == "—"

def test_get_recent_transactions(app):
    with app.app_context():
        # Test valid user with expenses
        txs = get_recent_transactions(1, limit=5)
        assert len(txs) <= 5
        assert len(txs) > 0
        for tx in txs:
            assert "date" in tx
            assert "description" in tx
            assert "category" in tx
            assert "amount" in tx
            
        # Verify ordering is newest first (date DESC)
        dates = [tx["date"] for tx in txs]
        sorted_dates = sorted(dates, reverse=True)
        assert dates == sorted_dates

        # Test user with no expenses
        try:
            no_exp_user_id = create_user("No Exp User 2", "noexp2@spendly.com", "pass123")
        except sqlite3.IntegrityError:
            conn = get_db()
            row = conn.execute("SELECT id FROM users WHERE email = ?;", ("noexp2@spendly.com",)).fetchone()
            no_exp_user_id = row["id"]
            
        txs_empty = get_recent_transactions(no_exp_user_id)
        assert txs_empty == []

def test_get_category_breakdown(app):
    with app.app_context():
        # Test valid user with expenses
        breakdown = get_category_breakdown(1)
        assert len(breakdown) > 0
        
        # Verify order by amount DESC
        amounts = [item["amount"] for item in breakdown]
        sorted_amounts = sorted(amounts, reverse=True)
        assert amounts == sorted_amounts
        
        # Verify percentages sum exactly to 100
        pcts = [item["pct"] for item in breakdown]
        assert sum(pcts) == 100

        # Test user with no expenses
        try:
            no_exp_user_id = create_user("No Exp User 3", "noexp3@spendly.com", "pass123")
        except sqlite3.IntegrityError:
            conn = get_db()
            row = conn.execute("SELECT id FROM users WHERE email = ?;", ("noexp3@spendly.com",)).fetchone()
            no_exp_user_id = row["id"]
            
        breakdown_empty = get_category_breakdown(no_exp_user_id)
        assert breakdown_empty == []

# ------------------------------------------------------------------ #
# Route Tests for /profile                                           #
# ------------------------------------------------------------------ #

def test_profile_route_unauthenticated(client):
    # GET /profile without session should redirect to /login
    response = client.get("/profile")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]

def test_profile_route_authenticated(client, app):
    # Log in as demo user
    client.post("/login", data={
        "email": "demo@spendly.com",
        "password": "demo123"
    })
    
    response = client.get("/profile")
    assert response.status_code == 200
    
    html = response.data.decode("utf-8")
    assert "Demo User" in html
    assert "demo@spendly.com" in html
    assert "₹" in html
    assert "Bills" in html  # Top category
    assert "8" in html  # Number of transactions
