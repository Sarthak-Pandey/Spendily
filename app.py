from flask import Flask, render_template, request, redirect, url_for, session, g, flash, abort
import sqlite3
import re
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import get_db, init_db, seed_db, close_db, create_user, get_user_by_email


EMAIL_REGEX = re.compile(r"^[^@]+@[^@]+\.[^@]+$")

app = Flask(__name__)
app.secret_key = "spendly-secret-key-for-session-management"


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method not in ["GET", "POST"]:
        abort(405)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password") or request.form.get("password_confirm")

        # 1. Validate empty fields
        if not name or not email or not password:
            flash("All fields are required.", "error")
            return render_template("register.html", name=name, email=email)

        # 2. Validate email format
        if not EMAIL_REGEX.match(email):
            flash("Invalid email format.", "error")
            return render_template("register.html", name=name, email=email)

        # 3. Validate password length (min 8 characters)
        if len(password) < 8:
            flash("Password must be at least 8 characters long.", "error")
            return render_template("register.html", name=name, email=email)

        # 4. Validate password confirmation
        if confirm_password is not None and confirm_password != password:
            flash("Passwords do not match.", "error")
            return render_template("register.html", name=name, email=email)

        # 5. Check duplicate email
        if get_user_by_email(email) is not None:
            flash("Email already registered", "error")
            return render_template("register.html", name=name, email=email)

        # 6. Create user
        try:
            create_user(name, email, password)
        except sqlite3.IntegrityError:
            flash("Email already registered", "error")
            return render_template("register.html", name=name, email=email)

        flash("Registration successful! Please sign in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.before_request
def load_logged_in_user():
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
    else:
        conn = get_db()
        g.user = conn.execute("SELECT * FROM users WHERE id = ?;", (user_id,)).fetchone()


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method not in ["GET", "POST"]:
        abort(405)

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Both email and password are required.", "error")
            return render_template("login.html", email=email)

        user = get_user_by_email(email)

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.", "error")
            return render_template("login.html", email=email)

        session.clear()
        session["user_id"] = user["id"]
        return redirect(url_for("landing"))

    return render_template("login.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user_info = {
        "name": "Demo User",
        "email": "demo@spendly.com",
        "joined": "July 2026"
    }

    stats = {
        "total_spent": "₹1,584.10",
        "transaction_count": 8,
        "top_category": "Bills"
    }

    transactions = [
        {"date": "2026-07-01", "description": "Monthly Apartment Rent", "category": "Bills", "amount": "₹1,250.00"},
        {"date": "2026-07-02", "description": "Lunch at office cafeteria", "category": "Food", "amount": "₹45.50"},
        {"date": "2026-07-04", "description": "Metro card recharge", "category": "Transport", "amount": "₹15.00"},
        {"date": "2026-07-06", "description": "Summer clothes shopping", "category": "Shopping", "amount": "₹120.00"},
        {"date": "2026-07-08", "description": "Medical prescription checkout", "category": "Health", "amount": "₹85.00"},
    ]

    category_breakdown = [
        {"category": "Bills", "amount": "₹1,250.00", "percentage": 79},
        {"category": "Shopping", "amount": "₹120.00", "percentage": 8},
        {"category": "Health", "amount": "₹85.00", "percentage": 5},
        {"category": "Food", "amount": "₹45.50", "percentage": 3},
        {"category": "Transport", "amount": "₹15.00", "percentage": 1},
        {"category": "Other", "amount": "₹68.60", "percentage": 4}
    ]

    return render_template(
        "profile.html",
        user_info=user_info,
        stats=stats,
        transactions=transactions,
        category_breakdown=category_breakdown
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


# Register teardown helper to close DB connections
app.teardown_appcontext(close_db)

# Initialize and seed database inside application context
with app.app_context():
    init_db()
    seed_db()


if __name__ == "__main__":
    app.run(debug=True, port=5001)
