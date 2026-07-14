from flask import Flask, render_template, request, redirect, url_for, session, g, flash, abort
import sqlite3
import re
from datetime import datetime, timedelta
import calendar
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import get_db, init_db, seed_db, close_db, create_user, get_user_by_email
from database.queries import (
    get_user_by_id,
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
    insert_expense,
    get_expense_by_id,
    update_expense,
    delete_expense
)


EMAIL_REGEX = re.compile(r"^[^@]+@[^@]+\.[^@]+$")

app = Flask(__name__)
app.secret_key = "spendly-secret-key-for-session-management"

from blueprints.ai_coach import ai_coach_bp
app.register_blueprint(ai_coach_bp)


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

    # Get query params
    raw_date_from = request.args.get("date_from", "").strip()
    raw_date_to = request.args.get("date_to", "").strip()

    date_from = None
    date_to = None

    # Validate dates if both are provided
    if raw_date_from and raw_date_to:
        try:
            dt_from = datetime.strptime(raw_date_from, "%Y-%m-%d")
            dt_to = datetime.strptime(raw_date_to, "%Y-%m-%d")
            
            if dt_from > dt_to:
                flash("Start date must be before end date.", "error")
            else:
                date_from = raw_date_from
                date_to = raw_date_to
        except ValueError:
            # Silently fall back to no filter
            pass

    # Dynamic calculation of presets
    today = datetime.now()
    _, last_day = calendar.monthrange(today.year, today.month)
    this_month_start = today.replace(day=1).strftime("%Y-%m-%d")
    this_month_end = today.replace(day=last_day).strftime("%Y-%m-%d")
    
    last_3_start = (today - timedelta(days=90)).strftime("%Y-%m-%d")
    last_3_end = today.strftime("%Y-%m-%d")
    
    last_6_start = (today - timedelta(days=180)).strftime("%Y-%m-%d")
    last_6_end = today.strftime("%Y-%m-%d")

    # Determine active preset
    if not date_from or not date_to:
        active_preset = "all-time"
    elif date_from == this_month_start and date_to == this_month_end:
        active_preset = "this-month"
    elif date_from == last_3_start and date_to == last_3_end:
        active_preset = "last-3-months"
    elif date_from == last_6_start and date_to == last_6_end:
        active_preset = "last-6-months"
    else:
        active_preset = "custom"

    # Query helpers with date parameters
    raw_stats = get_summary_stats(user_id, date_from, date_to)
    stats = {
        "total_spent": f"₹{raw_stats['total_spent']:,.2f}",
        "transaction_count": raw_stats["transaction_count"],
        "top_category": raw_stats["top_category"]
    }

    raw_transactions = get_recent_transactions(user_id, limit=10, date_from=date_from, date_to=date_to)
    transactions = [
        {
            "id": tx["id"],
            "date": tx["date"],
            "description": tx["description"],
            "category": tx["category"],
            "amount": f"₹{tx['amount']:,.2f}"
        }
        for tx in raw_transactions
    ]

    raw_breakdown = get_category_breakdown(user_id, date_from, date_to)
    category_breakdown = [
        {
            "category": item["name"],
            "amount": f"₹{item['amount']:,.2f}",
            "percentage": item["pct"]
        }
        for item in raw_breakdown
    ]

    presets = {
        "this_month": {"start": this_month_start, "end": this_month_end},
        "last_3": {"start": last_3_start, "end": last_3_end},
        "last_6": {"start": last_6_start, "end": last_6_end}
    }

    return render_template(
        "profile.html",
        user_info=user_info,
        stats=stats,
        transactions=transactions,
        category_breakdown=category_breakdown,
        presets=presets,
        active_preset=active_preset,
        date_from=date_from,
        date_to=date_to
    )


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    categories = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]

    if request.method == "POST":
        amount_raw = request.form.get("amount", "").strip()
        category = request.form.get("category", "").strip()
        date_raw = request.form.get("date", "").strip()
        description = request.form.get("description", "")

        # 1. Validate amount
        if not amount_raw:
            flash("Amount is required.", "error")
            return render_template("add_expense.html", categories=categories, amount=amount_raw, category=category, date=date_raw, description=description)
        try:
            amount = float(amount_raw)
            if amount <= 0:
                flash("Amount must be a positive number greater than 0.", "error")
                return render_template("add_expense.html", categories=categories, amount=amount_raw, category=category, date=date_raw, description=description)
        except ValueError:
            flash("Amount must be a valid number.", "error")
            return render_template("add_expense.html", categories=categories, amount=amount_raw, category=category, date=date_raw, description=description)

        # 2. Validate category
        if not category:
            flash("Category is required.", "error")
            return render_template("add_expense.html", categories=categories, amount=amount_raw, category=category, date=date_raw, description=description)
        if category not in categories:
            flash("Invalid category selected.", "error")
            return render_template("add_expense.html", categories=categories, amount=amount_raw, category=category, date=date_raw, description=description)

        # 3. Validate date
        if not date_raw:
            flash("Date is required.", "error")
            return render_template("add_expense.html", categories=categories, amount=amount_raw, category=category, date=date_raw, description=description)
        try:
            datetime.strptime(date_raw, "%Y-%m-%d")
        except ValueError:
            flash("Date must be in YYYY-MM-DD format.", "error")
            return render_template("add_expense.html", categories=categories, amount=amount_raw, category=category, date=date_raw, description=description)

        # Optional description check
        if description and len(description) > 200:
            flash("Description must be 200 characters or less.", "error")
            return render_template("add_expense.html", categories=categories, amount=amount_raw, category=category, date=date_raw, description=description)

        # Insert expense
        insert_expense(user_id, amount, category, date_raw, description)
        flash("Expense added successfully!", "success")
        return redirect(url_for("profile"))

    # GET request
    today_str = datetime.now().strftime("%Y-%m-%d")
    return render_template("add_expense.html", categories=categories, date=today_str)


@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
def edit_expense(id):
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    # Fetch the expense, verifying ownership
    expense = get_expense_by_id(id, user_id)
    if not expense:
        abort(404)

    categories = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]

    if request.method == "POST":
        amount_raw = request.form.get("amount", "").strip()
        category = request.form.get("category", "").strip()
        date_raw = request.form.get("date", "").strip()
        description = request.form.get("description", "")

        # Construct dictionary for form re-rendering on validation error
        edited_expense = {
            "id": id,
            "amount": amount_raw,
            "category": category,
            "date": date_raw,
            "description": description
        }

        # 1. Validate amount
        if not amount_raw:
            flash("Amount is required.", "error")
            return render_template("edit_expense.html", categories=categories, expense=edited_expense)
        try:
            amount = float(amount_raw)
            if amount <= 0:
                flash("Amount must be a positive number greater than 0.", "error")
                return render_template("edit_expense.html", categories=categories, expense=edited_expense)
        except ValueError:
            flash("Amount must be a valid number.", "error")
            return render_template("edit_expense.html", categories=categories, expense=edited_expense)

        # 2. Validate category
        if not category:
            flash("Category is required.", "error")
            return render_template("edit_expense.html", categories=categories, expense=edited_expense)
        if category not in categories:
            flash("Invalid category selected.", "error")
            return render_template("edit_expense.html", categories=categories, expense=edited_expense)

        # 3. Validate date
        if not date_raw:
            flash("Date is required.", "error")
            return render_template("edit_expense.html", categories=categories, expense=edited_expense)
        try:
            datetime.strptime(date_raw, "%Y-%m-%d")
        except ValueError:
            flash("Date must be in YYYY-MM-DD format.", "error")
            return render_template("edit_expense.html", categories=categories, expense=edited_expense)

        # Optional description check
        if description and len(description) > 200:
            flash("Description must be 200 characters or less.", "error")
            return render_template("edit_expense.html", categories=categories, expense=edited_expense)

        # Update expense
        update_expense(id, user_id, amount, category, date_raw, description)
        flash("Expense updated successfully!", "success")
        return redirect(url_for("profile"))

    # GET request
    return render_template("edit_expense.html", categories=categories, expense=expense)


@app.route("/expenses/<int:id>/delete", methods=["POST"])
def delete_expense_route(id):
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    # Fetch the expense, verifying ownership
    expense = get_expense_by_id(id, user_id)
    if not expense:
        abort(404)

    # Perform deletion
    delete_expense(id, user_id)
    flash("Expense deleted successfully!", "success")
    return redirect(url_for("profile"))


# Register teardown helper to close DB connections
app.teardown_appcontext(close_db)

# Initialize and seed database inside application context
with app.app_context():
    init_db()
    seed_db()


if __name__ == "__main__":
    app.run(debug=True, port=5001)
