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

def get_summary_stats(user_id, date_from=None, date_to=None):
    """
    Calculates summary stats for a user's expenses within an optional date range.
    Returns a dict with 'total_spent', 'transaction_count', and 'top_category'.
    If the user has no expenses within the range, returns:
    {'total_spent': 0, 'transaction_count': 0, 'top_category': '—'}
    """
    conn = get_db()
    try:
        if date_from and date_to:
            row = conn.execute("""
                SELECT SUM(amount) as total, COUNT(*) as count 
                FROM expenses 
                WHERE user_id = ? AND date BETWEEN ? AND ?;
            """, (user_id, date_from, date_to)).fetchone()
        else:
            row = conn.execute("""
                SELECT SUM(amount) as total, COUNT(*) as count 
                FROM expenses 
                WHERE user_id = ?;
            """, (user_id,)).fetchone()
        
        total = row["total"] if row["total"] is not None else 0.0
        count = row["count"] if row["count"] is not None else 0
        
        top_cat = "—"
        if count > 0:
            if date_from and date_to:
                cat_row = conn.execute("""
                    SELECT category 
                    FROM expenses 
                    WHERE user_id = ? AND date BETWEEN ? AND ?
                    GROUP BY category 
                    ORDER BY SUM(amount) DESC 
                    LIMIT 1;
                """, (user_id, date_from, date_to)).fetchone()
            else:
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

def get_recent_transactions(user_id, limit=10, date_from=None, date_to=None):
    """
    Retrieves the most recent transactions for a user (optionally date-filtered),
    sorted by date DESC, then id DESC. Returns a list of dicts.
    """
    conn = get_db()
    try:
        if date_from and date_to:
            rows = conn.execute("""
                SELECT id, date, description, category, amount 
                FROM expenses 
                WHERE user_id = ? AND date BETWEEN ? AND ?
                ORDER BY date DESC, id DESC 
                LIMIT ?;
            """, (user_id, date_from, date_to, limit)).fetchall()
        else:
            rows = conn.execute("""
                SELECT id, date, description, category, amount 
                FROM expenses 
                WHERE user_id = ? 
                ORDER BY date DESC, id DESC 
                LIMIT ?;
            """, (user_id, limit)).fetchall()
        
        return [
            {
                "id": r["id"],
                "date": r["date"],
                "description": r["description"],
                "category": r["category"],
                "amount": r["amount"]
            }
            for r in rows
        ]
    finally:
        _close_conn(conn)

def get_category_breakdown(user_id, date_from=None, date_to=None):
    """
    Groups expenses by category (optionally date-filtered) and returns list of dicts ordered by amount DESC.
    Each dict contains: 'name', 'amount', 'pct' (percentage of total rounded to nearest int).
    Adjusts the largest category to make sure percentages sum exactly to 100%.
    """
    conn = get_db()
    try:
        if date_from and date_to:
            total_row = conn.execute("""
                SELECT SUM(amount) as total 
                FROM expenses 
                WHERE user_id = ? AND date BETWEEN ? AND ?;
            """, (user_id, date_from, date_to)).fetchone()
        else:
            total_row = conn.execute(
                "SELECT SUM(amount) as total FROM expenses WHERE user_id = ?;", 
                (user_id,)
            ).fetchone()
            
        total = total_row["total"] if total_row["total"] is not None else 0.0
        if total == 0.0:
            return []
            
        if date_from and date_to:
            rows = conn.execute("""
                SELECT category, SUM(amount) as amount 
                FROM expenses 
                WHERE user_id = ? AND date BETWEEN ? AND ?
                GROUP BY category 
                ORDER BY amount DESC;
            """, (user_id, date_from, date_to)).fetchall()
        else:
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

def insert_expense(user_id, amount, category, date, description):
    """
    Inserts a new expense row into the database.
    Description is optional (stores None/NULL if empty or blank).
    """
    conn = get_db()
    try:
        desc = None
        if description:
            stripped = description.strip()
            if stripped:
                desc = stripped
                
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO expenses (user_id, amount, category, date, description)
            VALUES (?, ?, ?, ?, ?);
        """, (user_id, amount, category, date, desc))
        last_id = cursor.lastrowid
        cursor.execute("UPDATE users SET insights_dirty = 1 WHERE id = ?;", (user_id,))
        conn.commit()
        return last_id
    finally:
        _close_conn(conn)

def get_expense_by_id(expense_id, user_id):
    """
    Fetches a single expense row scoped to the user_id.
    Returns the matching row as a dict, or None if not found or not owned.
    """
    conn = get_db()
    try:
        row = conn.execute("""
            SELECT id, user_id, amount, category, date, description 
            FROM expenses 
            WHERE id = ? AND user_id = ?;
        """, (expense_id, user_id)).fetchone()
        
        if row:
            return dict(row)
        return None
    finally:
        _close_conn(conn)

def update_expense(expense_id, user_id, amount, category, date, description):
    """
    Updates an existing expense in place, enforcing user ownership.
    Strips description and stores None/NULL if blank.
    """
    conn = get_db()
    try:
        desc = None
        if description:
            stripped = description.strip()
            if stripped:
                desc = stripped
                
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE expenses 
            SET amount = ?, category = ?, date = ?, description = ? 
            WHERE id = ? AND user_id = ?;
        """, (amount, category, date, desc, expense_id, user_id))
        rows_affected = cursor.rowcount
        cursor.execute("UPDATE users SET insights_dirty = 1 WHERE id = ?;", (user_id,))
        conn.commit()
        return rows_affected
    finally:
        _close_conn(conn)

def delete_expense(expense_id, user_id):
    """
    Deletes an expense row scoped to the user_id for ownership safety.
    Returns the number of affected rows.
    """
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM expenses 
            WHERE id = ? AND user_id = ?;
        """, (expense_id, user_id))
        rows_affected = cursor.rowcount
        cursor.execute("UPDATE users SET insights_dirty = 1 WHERE id = ?;", (user_id,))
        conn.commit()
        return rows_affected
    finally:
        _close_conn(conn)
