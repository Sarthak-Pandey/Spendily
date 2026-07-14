import sqlite3
from datetime import datetime, timedelta
import calendar

class FinancialAnalyticsEngine:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_category_spending(self, user_id, date_from=None, date_to=None):
        """
        Returns a dictionary mapping category names to total spent in float.
        """
        if date_from and date_to:
            cursor = self.conn.execute("""
                SELECT category, SUM(amount) as total
                FROM expenses
                WHERE user_id = ? AND date BETWEEN ? AND ?
                GROUP BY category;
            """, (user_id, date_from, date_to))
        else:
            cursor = self.conn.execute("""
                SELECT category, SUM(amount) as total
                FROM expenses
                WHERE user_id = ?
                GROUP BY category;
            """, (user_id,))
        
        return {row["category"]: row["total"] for row in cursor.fetchall()}

    def get_monthly_spending_trend(self, user_id, months=6):
        """
        Returns monthly spend history for the past N months.
        Ordered oldest to newest: [{'month': 'YYYY-MM', 'amount': 1500.00}]
        """
        # Calculate YYYY-MM values to select
        today = datetime.now()
        months_list = []
        for i in range(months - 1, -1, -1):
            y = today.year
            m = today.month - i
            while m <= 0:
                m += 12
                y -= 1
            months_list.append(f"{y:04d}-{m:02d}")
            
        cursor = self.conn.execute("""
            SELECT strftime('%Y-%m', date) as month, SUM(amount) as total
            FROM expenses
            WHERE user_id = ?
            GROUP BY month
            ORDER BY month ASC;
        """, (user_id,))
        
        db_data = {row["month"]: row["total"] for row in cursor.fetchall()}
        
        trend = []
        for m in months_list:
            trend.append({
                "month": m,
                "amount": db_data.get(m, 0.0)
            })
        return trend

    def get_month_over_month_change(self, user_id):
        """
        Compares this month's spending vs. last month's spending.
        """
        today = datetime.now()
        this_month_prefix = today.strftime("%Y-%m-")
        
        y = today.year
        m = today.month - 1
        if m == 0:
            m = 12
            y -= 1
        last_month_prefix = f"{y:04d}-{m:02d}-"
        
        cursor_this = self.conn.execute("""
            SELECT SUM(amount) as total
            FROM expenses
            WHERE user_id = ? AND date LIKE ?;
        """, (user_id, this_month_prefix + "%"))
        row_this = cursor_this.fetchone()
        this_month_total = row_this["total"] if row_this and row_this["total"] is not None else 0.0
        
        cursor_last = self.conn.execute("""
            SELECT SUM(amount) as total
            FROM expenses
            WHERE user_id = ? AND date LIKE ?;
        """, (user_id, last_month_prefix + "%"))
        row_last = cursor_last.fetchone()
        last_month_total = row_last["total"] if row_last and row_last["total"] is not None else 0.0
        
        pct_change = 0.0
        if last_month_total > 0:
            pct_change = round(((this_month_total - last_month_total) / last_month_total) * 100, 1)
        elif this_month_total > 0:
            pct_change = 100.0
            
        return {
            "this_month_amount": this_month_total,
            "last_month_amount": last_month_total,
            "percentage_change": pct_change
        }
