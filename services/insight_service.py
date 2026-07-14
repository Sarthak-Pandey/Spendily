import sqlite3
from datetime import datetime
from services.analytics import FinancialAnalyticsEngine
from services.budgets import BudgetAnalyzer
from services.prediction import PredictionEngine
from services.savings import SavingsCalculator
from services.llm_formatter import InsightLLMFormatter

class FinancialInsightService:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.analytics = FinancialAnalyticsEngine(conn)
        self.budgets = BudgetAnalyzer(conn)
        self.predictions = PredictionEngine(conn)
        self.savings = SavingsCalculator(conn)
        self.formatter = InsightLLMFormatter(conn)

    def is_insights_dirty(self, user_id):
        """
        Checks if the insights_dirty flag is set for a user.
        """
        row = self.conn.execute("SELECT insights_dirty FROM users WHERE id = ?;", (user_id,)).fetchone()
        return row["insights_dirty"] == 1 if row else True

    def generate_insights(self, user_id):
        """
        Generates and saves insights for a user. Clears dirty flag.
        """
        self.conn.execute("""
            DELETE FROM insights
            WHERE user_id = ? AND read = 0 AND dismissed = 0;
        """, (user_id,))
        
        insights_to_save = []
        
        # 1. Month-over-Month change (Info)
        mom = self.analytics.get_month_over_month_change(user_id)
        if mom["this_month_amount"] > 0 or mom["last_month_amount"] > 0:
            metrics = {
                "this_spent": mom["this_month_amount"],
                "last_spent": mom["last_month_amount"],
                "pct_change": mom["percentage_change"]
            }
            formatted = self.formatter.format_insight("info", metrics)
            insights_to_save.append({
                "type": "info",
                "importance": 50,
                "confidence": 1.0,
                "category": None,
                **formatted
            })
            
        # 2. Budget adherence (Warning / Critical)
        current_month = datetime.now().strftime("%Y-%m")
        budget_data = self.budgets.get_budget_adherence(user_id, current_month)
        for b in budget_data["budgets"]:
            if b["status"] in ["warning", "over"]:
                type_str = "critical" if b["status"] == "over" else "warning"
                metrics = {
                    "category": b["category"],
                    "spent": b["spent"],
                    "limit": b["limit"],
                    "pct_used": b["pct_used"]
                }
                formatted = self.formatter.format_insight(type_str, metrics)
                insights_to_save.append({
                    "type": type_str,
                    "importance": 95 if type_str == "critical" else 80,
                    "confidence": 1.0,
                    "category": b["category"],
                    **formatted
                })
                
        # 3. Savings opportunities (Success)
        savings_ops = self.savings.find_savings_opportunities(user_id)
        for op in savings_ops:
            metrics = {
                "category": op["category"],
                "annual_saving": op["potential_annual_savings"],
                "monthly_saving": op["potential_monthly_savings"]
            }
            formatted = self.formatter.format_insight("success", metrics)
            insights_to_save.append({
                "type": "success",
                "importance": 70,
                "confidence": 1.0,
                "category": op["category"],
                **formatted
            })
            
        # Save all generated insights
        cursor = self.conn.cursor()
        current_time = datetime.now().isoformat()
        for ins in insights_to_save:
            cursor.execute("""
                INSERT INTO insights (user_id, type, title, description, action, importance, confidence, category, created_at, read, dismissed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0);
            """, (
                user_id,
                ins["type"],
                ins["title"],
                ins["description"],
                ins["action"],
                ins["importance"],
                ins["confidence"],
                ins["category"],
                current_time
            ))
            
        self.conn.execute("UPDATE users SET insights_dirty = 0 WHERE id = ?;", (user_id,))
        self.conn.commit()
        return len(insights_to_save)
