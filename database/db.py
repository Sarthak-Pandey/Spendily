import os
import sqlite3
from datetime import datetime
from flask import g, has_app_context
from werkzeug.security import generate_password_hash

DATABASE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
    'spendly.db'
)

def get_db():
    """
    Returns a SQLite database connection.
    If running within a Flask application context, the connection is cached
    on flask.g to be reused within the same request.
    """
    if has_app_context():
        if 'db' not in g:
            g.db = sqlite3.connect(DATABASE_PATH)
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON;")
        return g.db
    else:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

def close_db(e=None):
    """
    Closes the database connection stored in flask.g, if it exists.
    """
    if has_app_context():
        db = g.pop('db', None)
        if db is not None:
            db.close()

def init_db():
    """
    Creates the database tables if they do not already exist.
    """
    conn = get_db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                date TEXT NOT NULL,
                description TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            );
        """)
        conn.commit()
    finally:
        if not has_app_context():
            conn.close()

def seed_db():
    """
    Seeds the database with a demo user and initial sample expenses if empty.
    """
    conn = get_db()
    try:
        cursor = conn.cursor()
        # Check if users table already contains data
        cursor.execute("SELECT 1 FROM users LIMIT 1;")
        if cursor.fetchone() is not None:
            return  # already seeded, return early
        
        # Insert demo user
        password_hash = generate_password_hash("demo123")
        cursor.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?);",
            ("Demo User", "demo@spendly.com", password_hash)
        )
        demo_user_id = cursor.lastrowid
        
        # Insert 8 sample expenses across categories: Food, Transport, Bills, Health, Entertainment, Shopping, Other
        current_year_month = datetime.now().strftime("%Y-%m")
        expenses_data = [
            (demo_user_id, 1250.00, "Bills", f"{current_year_month}-01", "Monthly Apartment Rent"),
            (demo_user_id, 45.50, "Food", f"{current_year_month}-02", "Lunch at office cafeteria"),
            (demo_user_id, 15.00, "Transport", f"{current_year_month}-04", "Metro card recharge"),
            (demo_user_id, 120.00, "Shopping", f"{current_year_month}-06", "Summer clothes shopping"),
            (demo_user_id, 85.00, "Health", f"{current_year_month}-08", "Medical prescription checkout"),
            (demo_user_id, 35.00, "Entertainment", f"{current_year_month}-09", "Weekend movie ticket"),
            (demo_user_id, 10.50, "Other", f"{current_year_month}-11", "Newspaper subscription"),
            (demo_user_id, 28.30, "Food", f"{current_year_month}-12", "Grocery items and snacks"),
        ]
        
        cursor.executemany(
            """
            INSERT INTO expenses (user_id, amount, category, date, description)
            VALUES (?, ?, ?, ?, ?);
            """,
            expenses_data
        )
        conn.commit()
    finally:
        if not has_app_context():
            conn.close()
def create_user(name, email, password):
    """
    Hashes the password with werkzeug, inserts a row into users, returns the new user's id.
    Raises sqlite3.IntegrityError if the email is already taken (UNIQUE constraint).
    """
    conn = get_db()
    cursor = conn.cursor()
    password_hash = generate_password_hash(password)
    cursor.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?);",
        (name, email, password_hash)
    )
    conn.commit()
    return cursor.lastrowid

def get_user_by_email(email):
    """
    Returns a user row or None.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?;", (email,))
    return cursor.fetchone()
