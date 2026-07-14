import pytest
import sqlite3
from app import app as flask_app
from database.db import get_db, init_db, seed_db, create_user
from database.queries import get_expense_by_id, delete_expense

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
# Unit Tests for queries.py delete_expense                           #
# ------------------------------------------------------------------ #

def test_delete_expense_valid(app):
    with app.app_context():
        import random
        r = random.randint(100000, 999999)
        uid = create_user("User A", f"del_{r}@spendly.com", "pass123")
        eid = add_test_expense(uid, 50.0, "Food", "2026-03-20", "Lunch")
        
        # Verify row exists
        conn = get_db()
        row = conn.execute("SELECT * FROM expenses WHERE id = ?;", (eid,)).fetchone()
        assert row is not None
        
        # Delete row
        affected = delete_expense(eid, uid)
        assert affected == 1
        
        # Verify row is removed
        conn = get_db()
        row_del = conn.execute("SELECT * FROM expenses WHERE id = ?;", (eid,)).fetchone()
        assert row_del is None

def test_delete_expense_wrong_user(app):
    with app.app_context():
        import random
        r = random.randint(100000, 999999)
        uid_a = create_user("User A", f"a_{r}@spendly.com", "pass123")
        uid_b = create_user("User B", f"b_{r}@spendly.com", "pass123")
        eid = add_test_expense(uid_a, 50.0, "Food", "2026-03-20", "Lunch")
        
        # User B tries to delete User A's expense
        affected = delete_expense(eid, uid_b)
        assert affected == 0
        
        # Verify row still exists in DB
        conn = get_db()
        row = conn.execute("SELECT * FROM expenses WHERE id = ?;", (eid,)).fetchone()
        assert row is not None

def test_delete_expense_nonexistent(app):
    with app.app_context():
        import random
        r = random.randint(100000, 999999)
        uid = create_user("User A", f"a_{r}@spendly.com", "pass123")
        
        affected = delete_expense(99999, uid)
        assert affected == 0

# ------------------------------------------------------------------ #
# Route Tests for POST /expenses/<id>/delete                        #
# ------------------------------------------------------------------ #

def test_delete_expense_route_post_unauthenticated(client):
    response = client.post("/expenses/1/delete")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]

def test_delete_expense_route_post_owner(client, app):
    with app.app_context():
        import random
        r = random.randint(100000, 999999)
        email = f"del_route_{r}@spendly.com"
        password = "pass"
        uid = create_user("Tester", email, password)
        eid = add_test_expense(uid, 50.0, "Food", "2026-03-20", "Lunch")
        
    client.post("/login", data={"email": email, "password": password})
    
    response = client.post(f"/expenses/{eid}/delete")
    assert response.status_code == 302
    assert "/profile" in response.headers["Location"]
    
    # Verify in DB
    with app.app_context():
        conn = get_db()
        row = conn.execute("SELECT * FROM expenses WHERE id = ?;", (eid,)).fetchone()
        assert row is None

def test_delete_expense_route_post_wrong_user(client, app):
    with app.app_context():
        import random
        r = random.randint(100000, 999999)
        uid_a = create_user("User A", f"a_{r}@spendly.com", "pass")
        uid_b = create_user("User B", f"b_{r}@spendly.com", "pass")
        eid = add_test_expense(uid_a, 50.0, "Food", "2026-03-20", "Lunch")
        
    client.post("/login", data={"email": f"b_{r}@spendly.com", "password": "pass"})
    
    # Try to delete User A's expense
    response = client.post(f"/expenses/{eid}/delete")
    assert response.status_code == 404
    
    # Verify row still exists
    with app.app_context():
        conn = get_db()
        row = conn.execute("SELECT * FROM expenses WHERE id = ?;", (eid,)).fetchone()
        assert row is not None

def test_delete_expense_route_post_nonexistent(client, app):
    with app.app_context():
        import random
        r = random.randint(100000, 999999)
        email = f"tester_{r}@spendly.com"
        uid = create_user("Tester", email, "pass")
        
    client.post("/login", data={"email": email, "password": "pass"})
    response = client.post("/expenses/99999/delete")
    assert response.status_code == 404

def test_delete_expense_route_get_any_user(client):
    # GET request must return 405 Method Not Allowed
    response = client.get("/expenses/1/delete")
    assert response.status_code == 405
