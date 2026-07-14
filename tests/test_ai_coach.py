import pytest
import sqlite3
import datetime
from app import app as flask_app
from database.db import get_db, init_db, seed_db, create_user
from services.analytics import FinancialAnalyticsEngine
from services.budgets import BudgetAnalyzer
from services.prediction import PredictionEngine
from services.savings import SavingsCalculator
from services.insight_service import FinancialInsightService

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

# Helper to create an active budget
def add_test_budget(user_id, category, limit, period_start):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO budgets (user_id, category, monthly_limit, period_start, active)
        VALUES (?, ?, ?, ?, 1);
    """, (user_id, category, limit, period_start))
    conn.commit()
    return cursor.lastrowid

# ------------------------------------------------------------------ #
# Unit Tests for Analytics, Budgets, Predictions, Savings            #
# ------------------------------------------------------------------ #

def test_financial_analytics_mom(app):
    with app.app_context():
        import random
        r = random.randint(100000, 999999)
        uid = create_user("User A", f"an_{r}@spendly.com", "pass")
        
        # Insert expenses for current month and last month
        import datetime
        today = datetime.datetime.now()
        this_month_date = today.strftime("%Y-%m-10")
        
        # Last month
        lm_year = today.year
        lm_month = today.month - 1
        if lm_month == 0:
            lm_month = 12
            lm_year -= 1
        last_month_date = f"{lm_year:04d}-{lm_month:02d}-15"
        
        add_test_expense(uid, 100.0, "Food", this_month_date, "Groceries")
        add_test_expense(uid, 200.0, "Food", last_month_date, "Groceries Last Month")
        
        engine = FinancialAnalyticsEngine(get_db())
        mom = engine.get_month_over_month_change(uid)
        assert mom["this_month_amount"] == 100.0
        assert mom["last_month_amount"] == 200.0
        assert mom["percentage_change"] == -50.0

def test_budget_analyzer_adherence(app):
    with app.app_context():
        import random
        r = random.randint(100000, 999999)
        uid = create_user("User A", f"bg_{r}@spendly.com", "pass")
        current_month = datetime.datetime.now().strftime("%Y-%m")
        
        # Add budget limit
        add_test_budget(uid, "Food", 500.0, current_month)
        # Add expense exceeding budget limit
        add_test_expense(uid, 600.0, "Food", current_month + "-05", "Exceeded Lunch")
        
        analyzer = BudgetAnalyzer(get_db())
        data = analyzer.get_budget_adherence(uid, current_month)
        
        assert data["adherence_score"] == 0.0
        assert len(data["budgets"]) == 1
        assert data["budgets"][0]["spent"] == 600.0
        assert data["budgets"][0]["status"] == "over"

def test_prediction_engine_extrapolate(app):
    with app.app_context():
        import random
        r = random.randint(100000, 999999)
        uid = create_user("User A", f"pr_{r}@spendly.com", "pass")
        current_month = datetime.datetime.now().strftime("%Y-%m")
        
        # Insert expense for today
        add_test_expense(uid, 100.0, "Food", current_month + "-01", "Day 1 spend")
        
        engine = PredictionEngine(get_db())
        pred = engine.project_monthly_spending(uid, current_month)
        
        # If today is day 10, total projected should be (100 / 10) * days_in_month
        assert pred["spent_so_far"] == 100.0

def test_savings_opportunities_high_freq(app):
    with app.app_context():
        import random
        r = random.randint(100000, 999999)
        uid = create_user("User A", f"sv_{r}@spendly.com", "pass")
        
        # Insert 5 Food transactions in the last 10 days
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        for i in range(5):
            add_test_expense(uid, 50.0, "Food", today_str, f"Transaction {i}")
            
        calc = SavingsCalculator(get_db())
        ops = calc.find_savings_opportunities(uid)
        
        assert len(ops) == 1
        assert ops[0]["category"] == "Food"
        assert ops[0]["potential_monthly_savings"] == 50.0 # 20% of 250.0

def test_insight_service_orchestration(app):
    with app.app_context():
        import random
        r = random.randint(100000, 999999)
        uid = create_user("User A", f"in_{r}@spendly.com", "pass")
        current_month = datetime.datetime.now().strftime("%Y-%m")
        
        # Create budgets and expenses to trigger insights
        add_test_budget(uid, "Food", 200.0, current_month)
        add_test_expense(uid, 300.0, "Food", current_month + "-05", "Spent Food")
        
        service = FinancialInsightService(get_db())
        assert service.is_insights_dirty(uid) is True
        
        count = service.generate_insights(uid)
        assert count > 0
        assert service.is_insights_dirty(uid) is False
        
        # Confirm insight exists in database
        conn = get_db()
        row = conn.execute("SELECT * FROM insights WHERE user_id = ? AND type = ?;", (uid, "critical")).fetchone()
        assert row is not None
        assert row["type"] == "critical" # Over budget

# ------------------------------------------------------------------ #
# Route Tests for AI Coach Dashboard and APIs                        #
# ------------------------------------------------------------------ #

def test_ai_dashboard_route_unauthenticated(client):
    response = client.get("/ai/dashboard")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]

def test_ai_dashboard_route_authenticated(client, app):
    with app.app_context():
        import random
        r = random.randint(100000, 999999)
        email = f"dash_{r}@spendly.com"
        uid = create_user("Tester", email, "pass")
        # Add seed transactions
        current_month = datetime.datetime.now().strftime("%Y-%m")
        add_test_expense(uid, 50.0, "Food", current_month + "-01", "Coffee")
        
    client.post("/login", data={"email": email, "password": "pass"})
    
    response = client.get("/ai/dashboard")
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "AI Financial Coach" in html
    assert "Financial Health Score" in html
    assert "Month Projection" in html

def test_api_ai_insights_endpoint(client, app):
    with app.app_context():
        import random
        r = random.randint(100000, 999999)
        email = f"api_{r}@spendly.com"
        uid = create_user("Tester", email, "pass")
        current_month = datetime.datetime.now().strftime("%Y-%m")
        add_test_expense(uid, 50.0, "Food", current_month + "-01", "Coffee")
        
    client.post("/login", data={"email": email, "password": "pass"})
    
    response = client.get("/api/ai/insights")
    assert response.status_code == 200
    data = response.json
    assert isinstance(data, list)

def test_api_ai_read_and_dismiss_insight(client, app):
    with app.app_context():
        import random
        r = random.randint(100000, 999999)
        email = f"actions_{r}@spendly.com"
        uid = create_user("Tester", email, "pass")
        
        # Directly insert raw insight to test API actions
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO insights (user_id, type, title, description, action, importance, confidence, read, dismissed)
            VALUES (?, 'info', 'Test Title', 'Test Desc', 'Action', 50, 1.0, 0, 0);
        """, (uid,))
        conn.commit()
        iid = cursor.lastrowid
        
    client.post("/login", data={"email": email, "password": "pass"})
    
    # Read insight
    response_read = client.post(f"/api/ai/insights/{iid}/read")
    assert response_read.status_code == 200
    assert response_read.json["success"] is True
    
    # Verify read in DB
    with app.app_context():
        conn = get_db()
        row = conn.execute("SELECT read FROM insights WHERE id = ?;", (iid,)).fetchone()
        assert row["read"] == 1
        
    # Dismiss insight
    response_dismiss = client.post(f"/api/ai/insights/{iid}/dismiss")
    assert response_dismiss.status_code == 200
    assert response_dismiss.json["success"] is True
    
    # Verify dismissed in DB
    with app.app_context():
        conn = get_db()
        row = conn.execute("SELECT dismissed FROM insights WHERE id = ?;", (iid,)).fetchone()
        assert row["dismissed"] == 1
