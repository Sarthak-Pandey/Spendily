import sys
from datetime import datetime
from database.db import get_db

def _close_conn(conn):
    """
    Closes the SQLite connection and safely clears it from the Flask application
    context 'g' if active, without importing flask at the module level.
    This ensures that subsequent database calls within the same Flask request
    obtain a fresh connection instead of reusing the closed one.
    """
    try:
        conn.close()
    finally:
        flask = sys.modules.get('flask')
        if flask and flask.has_app_context():
            g = getattr(flask, 'g', None)
            if g is not None:
                try:
                    g.pop('db', None)
                except Exception:
                    try:
                        if getattr(g, 'db', None) == conn:
                            delattr(g, 'db')
                    except Exception:
                        pass

def get_user_by_id(user_id):
    """
    Retrieves user profile info.
    Returns a dict with 'name', 'email', and 'member_since' formatted as 'Month YYYY',
    or None if the user does not exist.
    """
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?;", 
            (user_id,)
        ).fetchone()
        if not row:
            return None
        
        created_str = row["created_at"]
        member_since = "Unknown"
        if created_str:
            date_part = created_str.split()[0].split('T')[0]
            try:
                dt = datetime.strptime(date_part, "%Y-%m-%d")
                member_since = dt.strftime("%B %Y")
            except Exception:
                member_since = created_str
                
        return {
            "name": row["name"],
            "email": row["email"],
            "member_since": member_since
        }
    finally:
        _close_conn(conn)

def get_summary_stats(user_id):
    """
    Calculates summary stats for a user's expenses.
    Returns a dict with 'total_spent', 'transaction_count', and 'top_category'.
    If the user has no expenses, returns:
    {'total_spent': 0, 'transaction_count': 0, 'top_category': '—'}
    """
    conn = get_db()
    try:
        row = conn.execute("""
            SELECT SUM(amount) as total, COUNT(*) as count 
            FROM expenses 
            WHERE user_id = ?;
        """, (user_id,)).fetchone()
        
        total = row["total"] if row["total"] is not None else 0.0
        count = row["count"] if row["count"] is not None else 0
        
        top_cat = "—"
        if count > 0:
            cat_row = conn.execute("""
                SELECT category 
                FROM expenses 
                WHERE user_id = ? 
                GROUP BY category 
                ORDER BY SUM(amount) DESC 
                LIMIT 1;
            """, (user_id,)).fetchone()
            if cat_row:
                top_cat = cat_row["category"]
                
        return {
            "total_spent": total,
            "transaction_count": count,
            "top_category": top_cat
        }
    finally:
        _close_conn(conn)

def get_recent_transactions(user_id, limit=10):
    """
    Retrieves the most recent transactions for a user, sorted by date DESC, then id DESC.
    Returns a list of dicts.
    """
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT date, description, category, amount 
            FROM expenses 
            WHERE user_id = ? 
            ORDER BY date DESC, id DESC 
            LIMIT ?;
        """, (user_id, limit)).fetchall()
        
        return [
            {
                "date": r["date"],
                "description": r["description"],
                "category": r["category"],
                "amount": r["amount"]
            }
            for r in rows
        ]
    finally:
        _close_conn(conn)

def get_category_breakdown(user_id):
    """
    Groups expenses by category and returns list of dicts ordered by amount DESC.
    Each dict contains: 'name', 'amount', 'pct' (percentage of total rounded to nearest int).
    Adjusts the largest category to make sure percentages sum exactly to 100%.
    """
    conn = get_db()
    try:
        total_row = conn.execute(
            "SELECT SUM(amount) as total FROM expenses WHERE user_id = ?;", 
            (user_id,)
        ).fetchone()
        total = total_row["total"] if total_row["total"] is not None else 0.0
        if total == 0.0:
            return []
            
        rows = conn.execute("""
            SELECT category, SUM(amount) as amount 
            FROM expenses 
            WHERE user_id = ? 
            GROUP BY category 
            ORDER BY amount DESC;
        """, (user_id,)).fetchall()
        
        breakdown = []
        pct_sum = 0
        for r in rows:
            amount = r["amount"]
            pct = int(round((amount / total) * 100))
            pct_sum += pct
            breakdown.append({
                "name": r["category"],
                "amount": amount,
                "pct": pct
            })
            
        if breakdown and pct_sum != 100:
            breakdown[0]["pct"] += (100 - pct_sum)
            
        return breakdown
    finally:
        _close_conn(conn)
