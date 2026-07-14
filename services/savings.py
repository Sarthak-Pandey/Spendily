import sqlite3
from datetime import datetime, timedelta

class SavingsCalculator:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def find_savings_opportunities(self, user_id):
        """
        Scans recent expenses to identify high frequency categories and maps 20% reduction targets.
        """
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        cursor = self.conn.execute("""
            SELECT category, COUNT(*) as cnt, SUM(amount) as total
            FROM expenses
            WHERE user_id = ? AND date >= ?
            GROUP BY category;
        """, (user_id, thirty_days_ago))
        rows = cursor.fetchall()
        
        opportunities = []
        for r in rows:
            cat = r["category"]
            cnt = r["cnt"]
            total = r["total"]
            
            if cat in ["Food", "Shopping", "Entertainment"] and cnt >= 4:
                monthly_saving = round(total * 0.20, 2)
                annual_saving = round(monthly_saving * 12, 2)
                opportunities.append({
                    "type": "reduction",
                    "category": cat,
                    "title": f"Reduce {cat} spending",
                    "message": f"You made {cnt} transactions in {cat} totaling ₹{total:,.2f} in the last 30 days. Trimming this by 20% would save ₹{monthly_saving:,.2f} per month.",
                    "potential_monthly_savings": monthly_saving,
                    "potential_annual_savings": annual_saving
                })
        return opportunities
