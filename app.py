import os
import sqlite3
import base64
from io import BytesIO
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session, g, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
try:
    import qrcode
except ImportError:
    qrcode = None

app = Flask(__name__)
app.secret_key = "supersecretkey_for_demo_only"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "database.db")

ADMIN_EMAIL = "admin@ckfood.com"
ADMIN_PASSWORD = "admin123"

FOOD_CATALOG = [
    ("Veg Deluxe Pizza", "Veg", 299, "images/veg_deluxe_pizza.jpeg", "Fresh vegetables, mozzarella, and homemade sauce."),
    ("Chicken Burger", "Fast Food", 179, "images/chicken_burger.jpeg", "Grilled chicken, lettuce, tomato, and special sauce."),
    ("Paneer Tikka", "Veg", 199, "images/paneer_tikka.jpeg", "Spiced paneer grilled to perfection."),
    ("Mango Shake", "Drinks", 99, "images/mango_shake.jpeg", "Sweet mango blend with creamy yogurt."),
    ("Beef Steak", "Non-Veg", 399, "images/beef_steak.jpeg", "Juicy steak served with herbs and sides."),
    ("French Fries", "Fast Food", 79, "images/french_fries.jpeg", "Crispy golden fries with ketchup."),
    ("Grilled Chicken", "Non-Veg", 299, "images/grilled_chicken.jpeg", "Marinated chicken grilled until tender."),
    ("Cold Coffee", "Drinks", 99, "images/cold_coffee.jpeg", "Iced coffee topped with whipped cream."),
    ("Margherita Pizza", "Veg", 249, "images/margherita_pizza.png", "Classic pizza with tomato sauce, mozzarella, and basil."),
    ("BBQ Chicken Pizza", "Non-Veg", 349, "images/bbq_chicken_pizza.png", "BBQ sauce, grilled chicken, onions, and cheese."),
    ("Caesar Salad", "Veg", 149, "images/caesar_salad.png", "Crisp romaine lettuce with Caesar dressing and croutons."),
    ("Chocolate Cake", "Desserts", 129, "images/chocolate_cake.png", "Rich chocolate cake with creamy frosting."),
    ("Spaghetti Bolognese", "Non-Veg", 279, "images/spaghetti_bolognese.png", "Pasta with meat sauce and parmesan cheese."),
    ("Fish Curry", "Non-Veg", 349, "images/fish_curry.png", "Spicy fish curry served with rice."),
    ("Vanilla Ice Cream", "Desserts", 99, "images/vanilla_ice_cream.png", "Creamy vanilla ice cream scoop."),
]


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE_PATH)
        db.row_factory = sqlite3.Row
    return db


def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def init_db():
    db = get_db()
    db.execute(
        '''
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
        '''
    )
    db.execute(
        '''
        CREATE TABLE IF NOT EXISTS foods(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            image TEXT NOT NULL,
            description TEXT NOT NULL
        )
        '''
    )
    db.execute(
        '''
        CREATE TABLE IF NOT EXISTS orders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            total REAL NOT NULL,
            original_total REAL NOT NULL DEFAULT 0,
            discount REAL NOT NULL DEFAULT 0,
            discount_percentage REAL NOT NULL DEFAULT 0,
            address TEXT NOT NULL,
            phone TEXT NOT NULL,
            payment TEXT NOT NULL,
            status TEXT NOT NULL,
            estimated_delivery_time TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        '''
    )
    db.execute(
        '''
        CREATE TABLE IF NOT EXISTS order_items(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            food_id INTEGER NOT NULL,
            qty INTEGER NOT NULL,
            FOREIGN KEY(order_id) REFERENCES orders(id),
            FOREIGN KEY(food_id) REFERENCES foods(id)
        )
        '''
    )
    db.commit()
    seed_foods(db)
    fix_food_images(db)


def seed_foods(db):
    for food in FOOD_CATALOG:
        existing = db.execute("SELECT id FROM foods WHERE name = ?", (food[0],)).fetchone()
        if not existing:
            db.execute("INSERT INTO foods (name, category, price, image, description) VALUES (?, ?, ?, ?, ?)", food)
    db.commit()


def fix_food_images(db):
    for name, _, _, image, _ in FOOD_CATALOG:
        db.execute("UPDATE foods SET image = ? WHERE name = ?", (image, name))
    db.commit()


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def login_required(func):
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return func(*args, **kwargs)

    wrapper.__name__ = func.__name__
    return wrapper


def admin_required(func):
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            flash("Admin access required.", "warning")
            return redirect(url_for("admin_login"))
        return func(*args, **kwargs)

    wrapper.__name__ = func.__name__
    return wrapper


def calculate_discount(total):
    '''Calculate 20% discount for orders above 300'''
    discount_amount = 0.0
    discount_percentage = 0.0
    if total > 300:
        discount_percentage = 20
        discount_amount = total * (discount_percentage / 100)
    return discount_amount, discount_percentage


def calculate_estimated_delivery():
    '''Calculate estimated delivery time (30-45 minutes from now)'''
    current_time = datetime.now()
    delivery_time = current_time + timedelta(minutes=35)
    return delivery_time


with app.app_context():
    init_db()


@app.context_processor
def inject_cart_count():
    cart = session.get("cart", {})
    count = sum(cart.values()) if cart else 0
    return {"cart_count": count}


@app.route("/")
def home():
    search = request.args.get("q", "")
    if search:
        foods = query_db(
            "SELECT * FROM foods WHERE name LIKE ? OR description LIKE ? LIMIT 8",
            (f"%{search}%", f"%{search}%"),
        )
    else:
        foods = query_db("SELECT * FROM foods LIMIT 8")
    return render_template("home.html", foods=foods, search=search)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")

        if not name or not email or not password:
            flash("All fields are required.", "danger")
            return redirect(url_for("register"))

        existing = query_db("SELECT * FROM users WHERE email = ?", (email,), one=True)
        if existing:
            flash("Email already registered. Please log in.", "warning")
            return redirect(url_for("login"))

        hashed = generate_password_hash(password)
        db = get_db()
        db.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)", (name, email, hashed))
        db.commit()
        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = query_db("SELECT * FROM users WHERE email = ?", (email,), one=True)
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["user_email"] = user["email"]
            flash(f"Welcome, {user['name']}!", "success")
            return redirect(url_for("home"))

        flash("Invalid email or password.", "danger")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session_keys = ["user_id", "user_name", "user_email", "cart"]
    for key in session_keys:
        session.pop(key, None)
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


@app.route("/menu")
def menu():
    category = request.args.get("category")
    search = request.args.get("q", "")
    query = "SELECT * FROM foods"
    args = []
    filters = []
    if category:
        filters.append("category = ?")
        args.append(category)
    if search:
        filters.append("(name LIKE ? OR description LIKE ?)")
        args.extend([f"%{search}%", f"%{search}%"])
    if filters:
        query += " WHERE " + " AND ".join(filters)
    query += " ORDER BY id DESC"
    foods = query_db(query, tuple(args))
    return render_template("menu.html", foods=foods, category=category, search=search)


@app.route("/add_to_cart/<int:food_id>")
def add_to_cart(food_id):
    cart = session.get("cart", {})
    cart[str(food_id)] = cart.get(str(food_id), 0) + 1
    session["cart"] = cart
    session.modified = True
    flash("Food item added to cart.", "success")
    return redirect(request.referrer or url_for("menu"))


@app.route("/remove_from_cart/<int:food_id>")
def remove_from_cart(food_id):
    cart = session.get("cart", {})
    cart.pop(str(food_id), None)
    session["cart"] = cart
    session.modified = True
    flash("Item removed from cart.", "info")
    return redirect(url_for("cart"))


@app.route("/cart", methods=["GET", "POST"])
def cart():
    cart = session.get("cart", {})
    if request.method == "POST":
        for food_id, qty in request.form.items():
            if not food_id.startswith("qty_"):
                continue
            item_id = food_id.split("qty_")[-1]
            try:
                quantity = int(qty)
            except ValueError:
                quantity = 1
            if quantity < 1:
                cart.pop(item_id, None)
            else:
                cart[item_id] = quantity
        session["cart"] = cart
        session.modified = True
        flash("Cart updated successfully.", "success")
        return redirect(url_for("cart"))

    items = []
    total = 0.0
    if cart:
        food_ids = tuple(int(fid) for fid in cart.keys())
        placeholder = ",".join("?" for _ in food_ids)
        foods = query_db(f"SELECT * FROM foods WHERE id IN ({placeholder})", food_ids)
        for food in foods:
            qty = cart.get(str(food["id"]), 0)
            subtotal = food["price"] * qty
            total += subtotal
            items.append({"food": food, "qty": qty, "subtotal": subtotal})
    return render_template("cart.html", items=items, total=total)


@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    cart = session.get("cart", {})
    if not cart:
        flash("Your cart is empty. Add items before checkout.", "warning")
        return redirect(url_for("menu"))

    items = []
    total = 0.0
    food_ids = tuple(int(fid) for fid in cart.keys())
    placeholder = ",".join("?" for _ in food_ids)
    foods = query_db(f"SELECT * FROM foods WHERE id IN ({placeholder})", food_ids)
    for food in foods:
        qty = cart.get(str(food["id"]), 0)
        subtotal = food["price"] * qty
        total += subtotal
        items.append({"food": food, "qty": qty, "subtotal": subtotal})

    discount_amount, discount_percentage = calculate_discount(total)
    final_total = total - discount_amount
    
    # Generate QR code for UPI payment
    qr_code = generate_upi_qr(final_total)
    
    # Calculate estimated delivery time
    estimated_delivery = calculate_estimated_delivery()

    if request.method == "POST":
        address = request.form.get("address")
        phone = request.form.get("phone")
        payment = request.form.get("payment")

        if not address or not phone or not payment:
            flash("All fields are required.", "danger")
            return redirect(url_for("checkout"))

        estimated_delivery = calculate_estimated_delivery()

        db = get_db()
        cursor = db.execute(
            '''
            INSERT INTO orders (user_id, total, original_total, discount, discount_percentage, address, phone, payment, status, estimated_delivery_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (session["user_id"], final_total, total, discount_amount, discount_percentage, address, phone, payment, "Preparing", estimated_delivery.strftime("%Y-%m-%d %H:%M:%S"))
        )
        order_id = cursor.lastrowid

        for item in items:
            db.execute(
                "INSERT INTO order_items (order_id, food_id, qty) VALUES (?, ?, ?)",
                (order_id, item["food"]["id"], item["qty"])
            )
        db.commit()

        session.pop("cart", None)
        flash("Order placed successfully!", "success")
        return redirect(url_for("order_success", order_id=order_id))

    return render_template("checkout.html", items=items, total=total, discount_amount=discount_amount, discount_percentage=discount_percentage, final_total=final_total, qr_code=qr_code, estimated_delivery=estimated_delivery)


def generate_upi_qr(amount, upi_id="9392831334@paytm", payee_name="FoodFlux"):
    """Generate QR code for UPI payment"""
    if not qrcode:
        return None
    try:
        upi_string = f"upi://pay?pa={upi_id}&pn={payee_name}&am={amount}&tn=Food%20Delivery"
        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(upi_string)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img_io = BytesIO()
        img.save(img_io, 'PNG')
        img_io.seek(0)
        qr_code_base64 = base64.b64encode(img_io.getvalue()).decode()
        return qr_code_base64
    except Exception as e:
        print(f"QR Code generation error: {e}")
        return None


@app.route("/order_success/<int:order_id>")
@login_required
def order_success(order_id):
    order = query_db("SELECT * FROM orders WHERE id = ? AND user_id = ?", (order_id, session["user_id"]), one=True)
    if not order:
        flash("Order not found.", "danger")
        return redirect(url_for("home"))

    return render_template("order_success.html", order=order)


@app.route("/track_order/<int:order_id>")
@login_required
def track_order(order_id):
    order = query_db("SELECT * FROM orders WHERE id = ? AND user_id = ?", (order_id, session["user_id"]), one=True)
    if not order:
        flash("Order not found.", "danger")
        return redirect(url_for("home"))

    order_items = query_db(
        '''
        SELECT oi.qty, f.name, f.category, f.price
        FROM order_items oi
        JOIN foods f ON oi.food_id = f.id
        WHERE oi.order_id = ?
        ''',
        (order_id,)
    )

    return render_template("track_order.html", order=order, order_items=order_items)


@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            flash("Admin login successful.", "success")
            return redirect(url_for("admin_dashboard"))

        flash("Invalid admin credentials.", "danger")
        return redirect(url_for("admin_login"))

    return render_template("admin_login.html")


@app.route("/admin_logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    flash("Admin logged out.", "info")
    return redirect(url_for("admin_login"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    orders = query_db("SELECT * FROM orders ORDER BY created_at DESC")
    return render_template("admin_dashboard.html", orders=orders)


@app.route("/admin/orders")
@admin_required
def admin_orders():
    orders = query_db("SELECT * FROM orders ORDER BY created_at DESC")
    return render_template("admin_orders.html", orders=orders)


@app.route("/admin/foods", methods=["GET", "POST"])
@admin_required
def admin_foods():
    if request.method == "POST":
        name = request.form.get("name")
        category = request.form.get("category")
        price = request.form.get("price")
        image = request.form.get("image")
        description = request.form.get("description")

        if not name or not category or not price or not image or not description:
            flash("All fields are required.", "danger")
            return redirect(url_for("admin_foods"))

        try:
            price = float(price)
        except ValueError:
            flash("Invalid price.", "danger")
            return redirect(url_for("admin_foods"))

        db = get_db()
        db.execute(
            "INSERT INTO foods (name, category, price, image, description) VALUES (?, ?, ?, ?, ?)",
            (name, category, price, image, description)
        )
        db.commit()
        flash("Food item added successfully.", "success")
        return redirect(url_for("admin_foods"))

    foods = query_db("SELECT * FROM foods ORDER BY id DESC")
    return render_template("admin_food_form.html", foods=foods)


@app.route("/admin/order/status/<int:order_id>/<status>")
@admin_required
def update_order_status(order_id, status):
    valid_statuses = ["Preparing", "Ready", "Out for Delivery", "Delivered"]
    if status not in valid_statuses:
        flash("Invalid status.", "danger")
        return redirect(url_for("admin_orders"))
    db = get_db()
    db.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    db.commit()
    flash(f"Order status updated to {status}.", "success")
    return redirect(url_for("admin_orders"))


@app.route("/api/order/check/<int:order_id>")
def check_order_status(order_id):
    order = query_db("SELECT * FROM orders WHERE id = ?", (order_id,), one=True)
    if order:
        return jsonify({"status": order["status"], "id": order["id"]})
    return jsonify({"status": "not_found", "id": order_id}), 404


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
