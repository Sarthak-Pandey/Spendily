from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify, abort
from database.db import get_db
from services.insight_service import FinancialInsightService
from services.budgets import BudgetAnalyzer
from services.prediction import PredictionEngine
from services.savings import SavingsCalculator
from services.analytics import FinancialAnalyticsEngine
from datetime import datetime

ai_coach_bp = Blueprint("ai_coach", __name__)

@ai_coach_bp.route("/ai/dashboard")
def dashboard():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    conn = get_db()
    insight_service = FinancialInsightService(conn)
    
    # Lazy generation check: update insights if marked dirty
    if insight_service.is_insights_dirty(user_id):
        insight_service.generate_insights(user_id)
        
    # Fetch active insights (not dismissed), sorted by importance DESC
    insights = conn.execute("""
        SELECT id, type, title, description, action, importance, confidence, category, read
        FROM insights
        WHERE user_id = ? AND dismissed = 0
        ORDER BY importance DESC, id DESC;
    """, (user_id,)).fetchall()

    # Calculate budgets, predictions, and savings rates
    budget_analyzer = BudgetAnalyzer(conn)
    current_month = datetime.now().strftime("%Y-%m")
    budget_data = budget_analyzer.get_budget_adherence(user_id, current_month)
    
    pred_engine = PredictionEngine(conn)
    prediction = pred_engine.project_monthly_spending(user_id, current_month)
    
    savings_calc = SavingsCalculator(conn)
    savings_ops = savings_calc.find_savings_opportunities(user_id)

    # ---------------------------------------------------------
    # Financial Score Calculation (Ages 0 to 100)
    # Savings Rate Weight (40%): default income proxy = 50,000.00
    # Budget Adherence Weight (30%): % category targets met
    # Spending MoM Consistency Weight (30%): MoM difference score
    # ---------------------------------------------------------
    total_spent = prediction["spent_so_far"]
    income_proxy = 50000.00
    savings_rate = max(0.0, (income_proxy - total_spent) / income_proxy)
    savings_rate_score = savings_rate * 100.0
    
    adherence_score = budget_data["adherence_score"]
    
    analytics = FinancialAnalyticsEngine(conn)
    mom = analytics.get_month_over_month_change(user_id)
    consistency_score = max(0.0, 100.0 - abs(mom["percentage_change"]))
    
    financial_score = int(round(
        (savings_rate_score * 0.4) + 
        (adherence_score * 0.3) + 
        (consistency_score * 0.3)
    ))
    
    # Financial health status categorization
    if financial_score >= 80:
        health_status = "Excellent"
    elif financial_score >= 60:
        health_status = "Good"
    elif financial_score >= 40:
        health_status = "Fair"
    else:
        health_status = "Needs Attention"

    return render_template(
        "ai_coach/dashboard.html",
        insights=insights,
        budgets=budget_data["budgets"],
        prediction=prediction,
        savings_ops=savings_ops,
        financial_score=financial_score,
        health_status=health_status
    )

@ai_coach_bp.route("/api/ai/insights", methods=["GET"])
def get_insights_api():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
        
    conn = get_db()
    insights = conn.execute("""
        SELECT id, type, title, description, action, importance, confidence, category, read, dismissed
        FROM insights
        WHERE user_id = ? AND dismissed = 0
        ORDER BY importance DESC, id DESC;
    """, (user_id,)).fetchall()
    
    return jsonify([dict(row) for row in insights])

@ai_coach_bp.route("/api/ai/insights/<int:id>/read", methods=["POST"])
def read_insight_api(id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
        
    conn = get_db()
    row = conn.execute("SELECT 1 FROM insights WHERE id = ? AND user_id = ?;", (id, user_id)).fetchone()
    if not row:
        return jsonify({"error": "Not Found"}), 404
        
    conn.execute("UPDATE insights SET read = 1 WHERE id = ?;", (id,))
    conn.commit()
    return jsonify({"success": True})

@ai_coach_bp.route("/api/ai/insights/<int:id>/dismiss", methods=["POST"])
def dismiss_insight_api(id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
        
    conn = get_db()
    row = conn.execute("SELECT 1 FROM insights WHERE id = ? AND user_id = ?;", (id, user_id)).fetchone()
    if not row:
        return jsonify({"error": "Not Found"}), 404
        
    conn.execute("UPDATE insights SET dismissed = 1 WHERE id = ?;", (id,))
    conn.commit()
    return jsonify({"success": True})

@ai_coach_bp.route("/api/ai/generate", methods=["POST"])
def generate_insights_api():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
        
    conn = get_db()
    insight_service = FinancialInsightService(conn)
    count = insight_service.generate_insights(user_id)
    return jsonify({"success": True, "generated_count": count})
