import pytest
import sqlite3
from app import app as flask_app
from database.db import get_db, init_db, seed_db, create_user
from database.queries import insert_expense

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

# Helper to clear cached connections in tests
def _close_conn(conn):
    try:
        conn.close()
    except Exception:
        pass

# ------------------------------------------------------------------ #
# Unit Tests for queries.py insert_expense                           #
# ------------------------------------------------------------------ #

def test_insert_expense_valid(app):
    with app.app_context():
        import random
        rand_val = random.randint(100000, 999999)
        test_user_id = create_user("Test Add", f"add_{rand_val}@spendly.com", "pass123")
        row_id = insert_expense(test_user_id, 50.0, "Food", "2026-03-20", "Lunch")
        assert row_id is not None
        
        # Verify in DB
        conn = get_db()
        row = conn.execute("SELECT * FROM expenses WHERE id = ?;", (row_id,)).fetchone()
        conn.close()
        assert row is not None
        assert row["amount"] == 50.0
        assert row["category"] == "Food"
        assert row["date"] == "2026-03-20"
        assert row["description"] == "Lunch"

def test_insert_expense_null_description(app):
    with app.app_context():
        import random
        rand_val = random.randint(100000, 999999)
        test_user_id = create_user("Test Add Null", f"add_null_{rand_val}@spendly.com", "pass123")
        row_id = insert_expense(test_user_id, 100.0, "Bills", "2026-03-21", "")
        assert row_id is not None
        
        conn = get_db()
        row = conn.execute("SELECT * FROM expenses WHERE id = ?;", (row_id,)).fetchone()
        conn.close()
        assert row is not None
        assert row["description"] is None

# ------------------------------------------------------------------ #
# Route Tests for /expenses/add                                     #
# ------------------------------------------------------------------ #

def test_add_expense_route_get_unauthenticated(client):
    response = client.get("/expenses/add")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]

def test_add_expense_route_get_authenticated(client, app):
    client.post("/login", data={"email": "demo@spendly.com", "password": "demo123"})
    
    response = client.get("/expenses/add")
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "<form" in html
    assert "Food" in html
    assert "Transport" in html
    assert "Bills" in html
    assert "Save Expense" in html

def test_add_expense_route_post_unauthenticated(client):
    response = client.post("/expenses/add", data={
        "amount": "50.0",
        "category": "Food",
        "date": "2026-03-20"
    })
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]

def test_add_expense_route_post_authenticated_valid(client, app):
    # Create randomized user
    with app.app_context():
        import random
        rand_val = random.randint(100000, 999999)
        email = f"add_route_{rand_val}@spendly.com"
        password = "pass123"
        test_user_id = create_user("Test Add Route", email, password)
        
    client.post("/login", data={"email": email, "password": password})
    
    response = client.post("/expenses/add", data={
        "amount": "120.50",
        "category": "Shopping",
        "date": "2026-03-20",
        "description": "Weekly shopping"
    })
    assert response.status_code == 302
    assert "/profile" in response.headers["Location"]

    # Verify database state
    with app.app_context():
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM expenses WHERE user_id = ? AND amount = 120.50 ORDER BY id DESC LIMIT 1;", (test_user_id,)
        ).fetchone()
        conn.close()
        assert row is not None
        assert row["category"] == "Shopping"
        assert row["date"] == "2026-03-20"
        assert row["description"] == "Weekly shopping"

def test_add_expense_route_post_missing_amount(client, app):
    client.post("/login", data={"email": "demo@spendly.com", "password": "demo123"})
    response = client.post("/expenses/add", data={
        "amount": "",
        "category": "Food",
        "date": "2026-03-20"
    })
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "Amount is required." in html

def test_add_expense_route_post_zero_amount(client, app):
    client.post("/login", data={"email": "demo@spendly.com", "password": "demo123"})
    response = client.post("/expenses/add", data={
        "amount": "0",
        "category": "Food",
        "date": "2026-03-20"
    })
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "Amount must be a positive number greater than 0." in html

def test_add_expense_route_post_non_numeric_amount(client, app):
    client.post("/login", data={"email": "demo@spendly.com", "password": "demo123"})
    response = client.post("/expenses/add", data={
        "amount": "not-a-number",
        "category": "Food",
        "date": "2026-03-20"
    })
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "Amount must be a valid number." in html

def test_add_expense_route_post_invalid_category(client, app):
    client.post("/login", data={"email": "demo@spendly.com", "password": "demo123"})
    response = client.post("/expenses/add", data={
        "amount": "50.0",
        "category": "InvalidCat",
        "date": "2026-03-20"
    })
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "Invalid category selected." in html

def test_add_expense_route_post_invalid_date(client, app):
    client.post("/login", data={"email": "demo@spendly.com", "password": "demo123"})
    response = client.post("/expenses/add", data={
        "amount": "50.0",
        "category": "Food",
        "date": "2026-not-a-date"
    })
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "Date must be in YYYY-MM-DD format." in html
