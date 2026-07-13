from flask import Flask, render_template, request, redirect, url_for, session, g
import sqlite3
import re
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import get_db, init_db, seed_db, close_db


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
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password") or request.form.get("password_confirm")

        # 1. Validate empty fields
        if not name or not email or not password:
            error = "All fields are required."
            return render_template("register.html", error=error, name=name, email=email)

        # 2. Validate email format
        if not EMAIL_REGEX.match(email):
            error = "Invalid email format."
            return render_template("register.html", error=error, name=name, email=email)

        # 3. Validate password length (min 8 characters)
        if len(password) < 8:
            error = "Password must be at least 8 characters long."
            return render_template("register.html", error=error, name=name, email=email)

        # 4. Validate password confirmation (if present in the form submit)
        if confirm_password is not None and confirm_password != password:
            error = "Passwords do not match."
            return render_template("register.html", error=error, name=name, email=email)

        conn = get_db()
        cursor = conn.cursor()

        # 5. Check if email is already registered (Application-level unique check)
        cursor.execute("SELECT id FROM users WHERE email = ?;", (email,))
        if cursor.fetchone() is not None:
            error = "Email already registered"
            return render_template("register.html", error=error, name=name, email=email)

        # 6. Insert the new user
        password_hash = generate_password_hash(password)
        try:
            cursor.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?);",
                (name, email, password_hash)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            # Enforce database-level unique check safety
            error = "Email already registered"
            return render_template("register.html", error=error, name=name, email=email)

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
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not email or not password:
            error = "Both email and password are required."
            return render_template("login.html", error=error, email=email)

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?;", (email,))
        user = cursor.fetchone()

        if user is None or not check_password_hash(user["password_hash"], password):
            error = "Invalid email or password."
            return render_template("login.html", error=error, email=email)

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
    return "Profile page — coming in Step 4"


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
