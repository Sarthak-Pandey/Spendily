from flask import Flask, render_template, request, redirect, url_for, session, g, flash, abort
import sqlite3
import re
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import get_db, init_db, seed_db, close_db, create_user, get_user_by_email
from database.queries import (
    get_user_by_id,
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown
)


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

    if session.get("user_id"):
        return redirect(url_for("profile"))

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

    if session.get("user_id"):
        return redirect(url_for("profile"))

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
        return redirect(url_for("profile"))

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
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    db_user = get_user_by_id(user_id)
    if not db_user:
        session.clear()
        return redirect(url_for("login"))

    user_info = {
        "name": db_user["name"],
        "email": db_user["email"],
        "joined": db_user["member_since"]
    }

    raw_stats = get_summary_stats(user_id)
    stats = {
        "total_spent": f"₹{raw_stats['total_spent']:,.2f}",
        "transaction_count": raw_stats["transaction_count"],
        "top_category": raw_stats["top_category"]
    }



    raw_transactions = get_recent_transactions(user_id)
    transactions = [
        {
            "date": tx["date"],
            "description": tx["description"],
            "category": tx["category"],
            "amount": f"₹{tx['amount']:,.2f}"
        }
        for tx in raw_transactions
    ]



    raw_breakdown = get_category_breakdown(user_id)
    category_breakdown = [
        {
            "category": item["name"],
            "amount": f"₹{item['amount']:,.2f}",
            "percentage": item["pct"]
        }
        for item in raw_breakdown
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
