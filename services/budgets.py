import sqlite3
from datetime import datetime

class BudgetAnalyzer:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create_budget(self, user_id, category, limit, period_start=None):
        """
        Creates or updates a budget limit for a category.
        """
        if not period_start:
            period_start = datetime.now().strftime("%Y-%m")
            
        self.conn.execute("""
            UPDATE budgets
            SET active = 0
            WHERE user_id = ? AND category = ? AND period_start = ?;
        """, (user_id, category, period_start))
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO budgets (user_id, category, monthly_limit, period_start, active)
            VALUES (?, ?, ?, ?, 1);
        """, (user_id, category, limit, period_start))
        self.conn.commit()
        return cursor.lastrowid

    def get_budget_adherence(self, user_id, month_str=None):
        """
        Compares actual spending against budgets for the given month.
        """
        if not month_str:
            month_str = datetime.now().strftime("%Y-%m")
            
        cursor = self.conn.execute("""
            SELECT id, category, monthly_limit
            FROM budgets
            WHERE user_id = ? AND period_start = ? AND active = 1;
        """, (user_id, month_str))
        budgets = cursor.fetchall()
        
        adherence_list = []
        categories_within = 0
        
        for b in budgets:
            category = b["category"]
            limit = b["monthly_limit"]
            
            cursor_spend = self.conn.execute("""
                SELECT SUM(amount) as total
                FROM expenses
                WHERE user_id = ? AND category = ? AND date LIKE ?;
            """, (user_id, category, month_str + "-%"))
            row_spend = cursor_spend.fetchone()
            spent = row_spend["total"] if row_spend and row_spend["total"] is not None else 0.0
            
            pct_used = round((spent / limit) * 100, 1) if limit > 0 else 0.0
            
            if pct_used > 100:
                status = "over"
            elif pct_used >= 80:
                status = "warning"
            else:
                status = "within"
                
            if status != "over":
                categories_within += 1
                
            adherence_list.append({
                "category": category,
                "limit": limit,
                "spent": spent,
                "pct_used": pct_used,
                "status": status
            })
            
        score = 100.0
        if budgets:
            score = round((categories_within / len(budgets)) * 100, 1)
            
        return {
            "budgets": adherence_list,
            "adherence_score": score
        }
