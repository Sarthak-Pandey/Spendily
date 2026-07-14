import pytest
import sqlite3
from app import app as flask_app
from database.db import get_db, init_db, seed_db, create_user
from database.queries import insert_expense, get_expense_by_id, update_expense

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
def add_test_expense(user_id, amount, category, date_str, description):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO expenses (user_id, amount, category, date, description)
        VALUES (?, ?, ?, ?, ?);
    """, (user_id, amount, category, date_str, description))
    conn.commit()
    return cursor.lastrowid

# ------------------------------------------------------------------ #
# Unit Tests for queries.py get/update expense                       #
# ------------------------------------------------------------------ #

def test_get_expense_by_id_owner(app):
    with app.app_context():
        import random
        r = random.randint(100000, 999999)
        uid = create_user("User A", f"a_{r}@spendly.com", "pass123")
        eid = add_test_expense(uid, 50.0, "Food", "2026-03-20", "Lunch")
        
        expense = get_expense_by_id(eid, uid)
        assert expense is not None
        assert expense["amount"] == 50.0
        assert expense["description"] == "Lunch"

def test_get_expense_by_id_wrong_user(app):
    with app.app_context():
        import random
        r = random.randint(100000, 999999)
        uid_a = create_user("User A", f"a_{r}@spendly.com", "pass123")
        uid_b = create_user("User B", f"b_{r}@spendly.com", "pass123")
        eid = add_test_expense(uid_a, 50.0, "Food", "2026-03-20", "Lunch")
        
        # User B tries to fetch User A's expense
        expense = get_expense_by_id(eid, uid_b)
        assert expense is None

def test_get_expense_by_id_nonexistent(app):
    with app.app_context():
        import random
        r = random.randint(100000, 999999)
        uid = create_user("User A", f"a_{r}@spendly.com", "pass123")
        
        expense = get_expense_by_id(99999, uid)
        assert expense is None

def test_update_expense_owner(app):
    with app.app_context():
        import random
        r = random.randint(100000, 999999)
        uid = create_user("User A", f"a_{r}@spendly.com", "pass123")
        eid = add_test_expense(uid, 50.0, "Food", "2026-03-20", "Lunch")
        
        affected = update_expense(eid, uid, 75.50, "Transport", "2026-03-21", "Taxi ride")
        assert affected == 1
        
        # Verify in DB
        conn = get_db()
        row = conn.execute("SELECT * FROM expenses WHERE id = ?;", (eid,)).fetchone()
        conn.close()
        assert row["amount"] == 75.50
        assert row["category"] == "Transport"
        assert row["description"] == "Taxi ride"

def test_update_expense_wrong_user(app):
    with app.app_context():
        import random
        r = random.randint(100000, 999999)
        uid_a = create_user("User A", f"a_{r}@spendly.com", "pass123")
        uid_b = create_user("User B", f"b_{r}@spendly.com", "pass123")
        eid = add_test_expense(uid_a, 50.0, "Food", "2026-03-20", "Lunch")
        
        # User B tries to update User A's expense
        affected = update_expense(eid, uid_b, 75.50, "Transport", "2026-03-21", "Taxi ride")
        assert affected == 0
        
        # Verify DB remained unchanged
        conn = get_db()
        row = conn.execute("SELECT * FROM expenses WHERE id = ?;", (eid,)).fetchone()
        conn.close()
        assert row["amount"] == 50.0

# ------------------------------------------------------------------ #
# Route Tests for /expenses/<id>/edit                                #
# ------------------------------------------------------------------ #

def test_edit_expense_route_get_unauthenticated(client):
    response = client.get("/expenses/1/edit")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]

def test_edit_expense_route_get_owner(client, app):
    # Create randomized user & log in
    with app.app_context():
        import random
        r = random.randint(100000, 999999)
        email = f"edit_{r}@spendly.com"
        password = "pass"
        uid = create_user("Tester", email, password)
        eid = add_test_expense(uid, 50.0, "Food", "2026-03-20", "Lunch")
        
    client.post("/login", data={"email": email, "password": password})
    
    response = client.get(f"/expenses/{eid}/edit")
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "50.0" in html
    assert "Lunch" in html
    assert "Food" in html
    assert "Save Changes" in html

def test_edit_expense_route_get_wrong_user(client, app):
    with app.app_context():
        import random
        r = random.randint(100000, 999999)
        uid_a = create_user("User A", f"a_{r}@spendly.com", "pass")
        uid_b = create_user("User B", f"b_{r}@spendly.com", "pass")
        eid = add_test_expense(uid_a, 50.0, "Food", "2026-03-20", "Lunch")
        
    # Log in as User B
    client.post("/login", data={"email": f"b_{r}@spendly.com", "password": "pass"})
    
    # Try to GET User A's expense
    response = client.get(f"/expenses/{eid}/edit")
    assert response.status_code == 404

def test_edit_expense_route_get_nonexistent(client, app):
    with app.app_context():
        import random
        r = random.randint(100000, 999999)
        email = f"tester_{r}@spendly.com"
        uid = create_user("Tester", email, "pass")
        
    client.post("/login", data={"email": email, "password": "pass"})
    response = client.get("/expenses/99999/edit")
    assert response.status_code == 404

def test_edit_expense_route_post_unauthenticated(client):
    response = client.post("/expenses/1/edit", data={
        "amount": "50.0",
        "category": "Food",
        "date": "2026-03-20"
    })
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]

def test_edit_expense_route_post_owner_valid(client, app):
    with app.app_context():
        import random
        r = random.randint(100000, 999999)
        email = f"edit_post_{r}@spendly.com"
        password = "pass"
        uid = create_user("Tester", email, password)
        eid = add_test_expense(uid, 50.0, "Food", "2026-03-20", "Lunch")
        
    client.post("/login", data={"email": email, "password": password})
    
    response = client.post(f"/expenses/{eid}/edit", data={
        "amount": "80.99",
        "category": "Bills",
        "date": "2026-03-21",
        "description": "Electricity"
    })
    assert response.status_code == 302
    assert "/profile" in response.headers["Location"]
    
    # Verify in DB
    with app.app_context():
        conn = get_db()
        row = conn.execute("SELECT * FROM expenses WHERE id = ?;", (eid,)).fetchone()
        conn.close()
        assert row["amount"] == 80.99
        assert row["category"] == "Bills"
        assert row["description"] == "Electricity"

def test_edit_expense_route_post_wrong_user(client, app):
    with app.app_context():
        import random
        r = random.randint(100000, 999999)
        uid_a = create_user("User A", f"a_{r}@spendly.com", "pass")
        uid_b = create_user("User B", f"b_{r}@spendly.com", "pass")
        eid = add_test_expense(uid_a, 50.0, "Food", "2026-03-20", "Lunch")
        
    client.post("/login", data={"email": f"b_{r}@spendly.com", "password": "pass"})
    
    response = client.post(f"/expenses/{eid}/edit", data={
        "amount": "80.0",
        "category": "Bills",
        "date": "2026-03-21"
    })
    assert response.status_code == 404

def test_edit_expense_route_post_missing_amount(client, app):
    with app.app_context():
        import random
        r = random.randint(100000, 999999)
        email = f"edit_err_{r}@spendly.com"
        uid = create_user("Tester", email, "pass")
        eid = add_test_expense(uid, 50.0, "Food", "2026-03-20", "Lunch")
        
    client.post("/login", data={"email": email, "password": "pass"})
    
    response = client.post(f"/expenses/{eid}/edit", data={
        "amount": "",
        "category": "Food",
        "date": "2026-03-20"
    })
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "Amount is required." in html

def test_edit_expense_route_post_zero_amount(client, app):
    with app.app_context():
        import random
        r = random.randint(100000, 999999)
        email = f"edit_err_{r}@spendly.com"
        uid = create_user("Tester", email, "pass")
        eid = add_test_expense(uid, 50.0, "Food", "2026-03-20", "Lunch")
        
    client.post("/login", data={"email": email, "password": "pass"})
    
    response = client.post(f"/expenses/{eid}/edit", data={
        "amount": "0",
        "category": "Food",
        "date": "2026-03-20"
    })
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "Amount must be a positive number greater than 0." in html

def test_edit_expense_route_post_invalid_category(client, app):
    with app.app_context():
        import random
        r = random.randint(100000, 999999)
        email = f"edit_err_{r}@spendly.com"
        uid = create_user("Tester", email, "pass")
        eid = add_test_expense(uid, 50.0, "Food", "2026-03-20", "Lunch")
        
    client.post("/login", data={"email": email, "password": "pass"})
    
    response = client.post(f"/expenses/{eid}/edit", data={
        "amount": "50.0",
        "category": "BadCategory",
        "date": "2026-03-20"
    })
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "Invalid category selected." in html

def test_edit_expense_route_post_invalid_date(client, app):
    with app.app_context():
        import random
        r = random.randint(100000, 999999)
        email = f"edit_err_{r}@spendly.com"
        uid = create_user("Tester", email, "pass")
        eid = add_test_expense(uid, 50.0, "Food", "2026-03-20", "Lunch")
        
    client.post("/login", data={"email": email, "password": "pass"})
    
    response = client.post(f"/expenses/{eid}/edit", data={
        "amount": "50.0",
        "category": "Food",
        "date": "not-a-date"
    })
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "Date must be in YYYY-MM-DD format." in html
