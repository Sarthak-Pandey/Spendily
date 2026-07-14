import pytest
import sqlite3
from datetime import datetime, timedelta
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

# Helper to insert custom expense for test user
def insert_expense(user_id, amount, category, date_str, description):
    conn = get_db()
    conn.execute("""
        INSERT INTO expenses (user_id, amount, category, date, description)
        VALUES (?, ?, ?, ?, ?);
    """, (user_id, amount, category, date_str, description))
    conn.commit()

# ------------------------------------------------------------------ #
# Unit Tests for queries.py with Date Filters                        #
# ------------------------------------------------------------------ #

def test_queries_with_date_range(app):
    with app.app_context():
        # Let's seed specific expenses for a new test user to isolate dates
        import random
        rand_val = random.randint(100000, 999999)
        test_user_id = create_user("Filter User", f"filter_{rand_val}@spendly.com", "pass123")
            
        # Insert test expenses
        # 1. Food: 100.00 on 2026-05-10
        # 2. Bills: 500.00 on 2026-06-15
        # 3. Transport: 50.00 on 2026-07-01
        insert_expense(test_user_id, 100.00, "Food", "2026-05-10", "Lunch")
        insert_expense(test_user_id, 500.00, "Bills", "2026-06-15", "Internet")
        insert_expense(test_user_id, 50.00, "Transport", "2026-07-01", "Metro")

        # Test 1: get_summary_stats with date range covering only Bills and Transport (2026-06-01 to 2026-07-05)
        stats = get_summary_stats(test_user_id, "2026-06-01", "2026-07-05")
        assert stats["transaction_count"] == 2
        assert stats["total_spent"] == 550.00
        assert stats["top_category"] == "Bills"

        # Test 2: get_summary_stats with range having no expenses
        stats_empty = get_summary_stats(test_user_id, "2026-01-01", "2026-02-01")
        assert stats_empty["transaction_count"] == 0
        assert stats_empty["total_spent"] == 0.0
        assert stats_empty["top_category"] == "—"

        # Test 3: get_recent_transactions in date range (2026-05-01 to 2026-06-30)
        txs = get_recent_transactions(test_user_id, limit=10, date_from="2026-05-01", date_to="2026-06-30")
        assert len(txs) == 2
        assert txs[0]["category"] == "Bills"  # 2026-06-15 (newest in range)
        assert txs[1]["category"] == "Food"   # 2026-05-10

        # Test 4: get_category_breakdown in date range (2026-05-01 to 2026-06-30)
        # Total = 600.00
        # Bills = 500.00 (83.33% -> 83%)
        # Food = 100.00 (16.66% -> 17%)
        breakdown = get_category_breakdown(test_user_id, "2026-05-01", "2026-06-30")
        assert len(breakdown) == 2
        assert breakdown[0]["name"] == "Bills"
        assert breakdown[0]["pct"] == 83
        assert breakdown[1]["name"] == "Food"
        assert breakdown[1]["pct"] == 17
        assert sum(item["pct"] for item in breakdown) == 100

        # Test 5: get_category_breakdown with no expenses in range
        breakdown_empty = get_category_breakdown(test_user_id, "2026-01-01", "2026-02-01")
        assert breakdown_empty == []

# ------------------------------------------------------------------ #
# Route Tests for /profile with Filters                              #
# ------------------------------------------------------------------ #

def test_route_date_filters(client, app):
    # Log in as demo user
    client.post("/login", data={
        "email": "demo@spendly.com",
        "password": "demo123"
    })

    # Test 1: GET /profile without parameters (default all-time)
    response = client.get("/profile")
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "Monthly Summary" in html
    assert "Bills" in html  # Seed top category
    assert "All Time" in html

    # Test 2: GET /profile with invalid range (start date > end date)
    response = client.get("/profile?date_from=2026-07-10&date_to=2026-07-01")
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    # Should flash warning error
    assert "Start date must be before end date." in html
    # Should fall back to unfiltered (showing Bills)
    assert "Bills" in html 

    # Test 3: GET /profile with malformed date parameter
    response = client.get("/profile?date_from=invalid-date&date_to=2026-07-01")
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    # Should silently fall back to unfiltered (no warning shown, but shows default data)
    assert "Start date must be before end date." not in html
    assert "Bills" in html

    # Test 4: GET /profile with valid date range
    # Let's check a range where we know only certain seed expenses exist.
    # In db.py:
    # - Rent: 1250.00 on YYYY-MM-01 (Bills)
    # - Lunch: 45.50 on YYYY-MM-02 (Food)
    # - Metro: 15.00 on YYYY-MM-04 (Transport)
    current_year_month = datetime.now().strftime("%Y-%m")
    date_from = f"{current_year_month}-02"
    date_to = f"{current_year_month}-05"
    
    response = client.get(f"/profile?date_from={date_from}&date_to={date_to}")
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    
    # In this range, Rent (1250) is excluded. Total spent should be 45.50 + 15.00 = 60.50.
    assert "₹60.50" in html
    # Transaction count is 2 (Lunch and Metro)
    assert "2" in html
    # Top category is Food (45.50 vs 15.00)
    assert "Food" in html
