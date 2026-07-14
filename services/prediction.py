import sqlite3
import calendar
from datetime import datetime

class PredictionEngine:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def project_monthly_spending(self, user_id, month_str=None):
        """
        Projects total spending for a month using linear extrapolation.
        """
        today = datetime.now()
        if not month_str:
            month_str = today.strftime("%Y-%m")
        
        try:
            target_date = datetime.strptime(month_str, "%Y-%m")
        except ValueError:
            target_date = today
            month_str = today.strftime("%Y-%m")
            
        _, total_days = calendar.monthrange(target_date.year, target_date.month)
        
        if target_date.year == today.year and target_date.month == today.month:
            days_elapsed = today.day
        else:
            days_elapsed = total_days
            
        cursor = self.conn.execute("""
            SELECT SUM(amount) as total
            FROM expenses
            WHERE user_id = ? AND date LIKE ?;
        """, (user_id, month_str + "-%"))
        row = cursor.fetchone()
        spent_so_far = row["total"] if row and row["total"] is not None else 0.0
        
        projected = 0.0
        if days_elapsed > 0:
            projected = round((spent_so_far / days_elapsed) * total_days, 2)
            
        return {
            "spent_so_far": spent_so_far,
            "days_elapsed": days_elapsed,
            "total_days": total_days,
            "projected_total": projected,
            "difference": round(projected - spent_so_far, 2)
        }
