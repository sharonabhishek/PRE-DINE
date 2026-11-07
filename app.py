
from flask import (
    Flask, render_template, request,
    redirect, url_for, session, flash
)
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "predine_demo_secret_change_later"

DATABASE = "predine.db"


# DATABASE CONNECTION
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# CREATE TABLES AND DEFAULT DATA
def initialize_database():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'customer'
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS food (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            category TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            food_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            total REAL NOT NULL,
            status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create demo admin account
    admin = conn.execute(
        "SELECT id FROM users WHERE username = ?",
        ("admin",)
    ).fetchone()

    if not admin:
        conn.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            ("admin", generate_password_hash("admin123"), "admin")
        )

    # Default food menu
    count = conn.execute(
        "SELECT COUNT(*) FROM food"
    ).fetchone()[0]

    if count == 0:
        items = [
            ("Veg Burger", "Fresh vegetable burger", 99, "Fast Food"),
            ("Cheese Pizza", "Cheesy delicious pizza", 199, "Fast Food"),
            ("Veg Biryani", "Traditional vegetable biryani", 149, "Indian"),
            ("Paneer Butter Masala", "Creamy paneer curry", 179, "Indian"),
            ("Masala Dosa", "South Indian crispy dosa", 70, "Breakfast"),
            ("Idli Sambar", "Soft idli with sambar", 50, "Breakfast"),
            ("Veg Fried Rice", "Chinese style fried rice", 120, "Chinese"),
            ("Pasta", "Creamy white sauce pasta", 159, "Italian"),
            ("French Fries", "Crispy potato fries", 79, "Snacks"),
            ("Chocolate Cake", "Delicious chocolate dessert", 89, "Dessert"),
            ("Fresh Lime Juice", "Refreshing lime drink", 40, "Drinks"),
            ("Ice Cream", "Vanilla ice cream", 60, "Dessert")
        ]

        conn.executemany(
            "INSERT INTO food (name, description, price, category) VALUES (?, ?, ?, ?)",
            items
        )

    conn.commit()
    conn.close()


# HOME PAGE
@app.route("/")
def home():
    conn = get_db()
    foods = conn.execute(
        "SELECT * FROM food ORDER BY id DESC"
    ).fetchall()
    conn.close()

    return render_template("index.html", foods=foods)


# CUSTOMER REGISTRATION
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        if not username or len(password) < 6:
            flash("Enter a username and password of at least 6 characters.")
            return redirect(url_for("register"))

        conn = get_db()

        try:
            conn.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                (username, generate_password_hash(password), "customer")
            )
            conn.commit()
            flash("Registration successful! Please login.")

        except sqlite3.IntegrityError:
            flash("Username already exists.")

        finally:
            conn.close()

        return redirect(url_for("login"))

    return render_template("register.html")


# CUSTOMER LOGIN
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ? AND role = 'customer'",
            (username,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session.clear()
            session["username"] = user["username"]
            session["role"] = "customer"
            return redirect(url_for("home"))

        flash("Invalid customer username or password.")

    return render_template("login.html")


# CUSTOMER ORDERS
@app.route("/order/<int:food_id>", methods=["POST"])
def place_order(food_id):
    if session.get("role") != "customer":
        flash("Please login as a customer before ordering.")
        return redirect(url_for("login"))

    try:
        quantity = int(request.form["quantity"])
        if not 1 <= quantity <= 20:
            raise ValueError
    except (ValueError, TypeError):
        flash("Please select a quantity between 1 and 20.")
        return redirect(url_for("home"))

    conn = get_db()

    item = conn.execute(
        "SELECT * FROM food WHERE id = ?", (food_id,)
    ).fetchone()

    if item:
        total = item["price"] * quantity

        conn.execute("""
            INSERT INTO orders
            (username, food_name, quantity, total)
            VALUES (?, ?, ?, ?)
        """, (
            session["username"],
            item["name"],
            quantity,
            total
        ))

        conn.commit()
        flash("Your order has been placed successfully!")

    else:
        flash("Food item not found.")

    conn.close()
    return redirect(url_for("my_orders"))


# CUSTOMER ORDER HISTORY
@app.route("/my-orders")
def my_orders():
    if session.get("role") != "customer":
        return redirect(url_for("login"))

    conn = get_db()
    orders = conn.execute(
        "SELECT * FROM orders WHERE username = ? ORDER BY id DESC",
        (session["username"],)
    ).fetchall()
    conn.close()

    return render_template("my_orders.html", orders=orders)


# ADMIN LOGIN
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        conn = get_db()
        admin = conn.execute(
            "SELECT * FROM users WHERE username = ? AND role = 'admin'",
            (username,)
        ).fetchone()
        conn.close()

        if admin and check_password_hash(admin["password"], password):
            session.clear()
            session["username"] = admin["username"]
            session["role"] = "admin"
            return redirect(url_for("admin"))

        flash("Invalid admin credentials.")

    return render_template("admin_login.html")


# ADMIN DASHBOARD
@app.route("/admin")
def admin():
    if session.get("role") != "admin":
        return redirect(url_for("admin_login"))

    conn = get_db()

    foods = conn.execute(
        "SELECT * FROM food ORDER BY id DESC"
    ).fetchall()

    orders = conn.execute(
        "SELECT * FROM orders ORDER BY id DESC"
    ).fetchall()

    total_orders = conn.execute(
        "SELECT COUNT(*) FROM orders"
    ).fetchone()[0]

    pending_orders = conn.execute(
        "SELECT COUNT(*) FROM orders WHERE status = 'Pending'"
    ).fetchone()[0]

    conn.close()

    return render_template(
        "admin.html",
        foods=foods,
        orders=orders,
        total_orders=total_orders,
        pending_orders=pending_orders
    )


# ADMIN ADD FOOD
@app.route("/admin/add-food", methods=["POST"])
def add_food():
    if session.get("role") != "admin":
        return redirect(url_for("admin_login"))

    name = request.form["name"].strip()
    description = request.form["description"].strip()
    category = request.form["category"].strip()

    try:
        price = float(request.form["price"])
        if not name or price <= 0:
            raise ValueError
    except ValueError:
        flash("Enter a valid food name and positive price.")
        return redirect(url_for("admin"))

    conn = get_db()

    conn.execute("""
        INSERT INTO food (name, description, price, category)
        VALUES (?, ?, ?, ?)
    """, (name, description, price, category))

    conn.commit()
    conn.close()

    flash("Food item added successfully!")
    return redirect(url_for("admin"))


# ADMIN DELETE FOOD
@app.route("/admin/delete-food/<int:food_id>", methods=["POST"])
def delete_food(food_id):
    if session.get("role") != "admin":
        return redirect(url_for("admin_login"))

    conn = get_db()
    conn.execute("DELETE FROM food WHERE id = ?", (food_id,))
    conn.commit()
    conn.close()

    flash("Food item deleted.")
    return redirect(url_for("admin"))


# ADMIN ACCEPT OR REJECT ORDER
@app.route("/admin/update-order/<int:order_id>", methods=["POST"])
def update_order(order_id):
    if session.get("role") != "admin":
        return redirect(url_for("admin_login"))

    status = request.form["status"]

    if status not in ("Accepted", "Rejected", "Completed"):
        flash("Invalid order status.")
        return redirect(url_for("admin"))

    conn = get_db()
    conn.execute(
        "UPDATE orders SET status = ? WHERE id = ?",
        (status, order_id)
    )
    conn.commit()
    conn.close()

    flash("Order status updated.")
    return redirect(url_for("admin"))


# LOGOUT
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


if __name__ == "__main__":
    initialize_database()
    import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
