import os
import re
import shutil
import sqlite3
import base64
import mimetypes
from io import BytesIO
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session, g, jsonify
from flask_socketio import SocketIO, join_room
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
try:
    import qrcode
except ImportError:
    qrcode = None

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey_for_demo_only")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "database.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "images")

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@ckfood.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

MANAGER_EMAIL = os.environ.get("MANAGER_EMAIL", ADMIN_EMAIL)
MANAGER_PASSWORD = os.environ.get("MANAGER_PASSWORD", ADMIN_PASSWORD)

DELIVERY_STAFF = [
    ("Rahul Sharma", "rahul@ckfood.com", "delivery123"),
    ("Amit Verma", "amit@ckfood.com", "delivery123"),
    ("Suresh Kumar", "suresh@ckfood.com", "delivery123"),
    ("Vikram Singh", "vikram@ckfood.com", "delivery123"),
    ("Imran Khan", "imran@ckfood.com", "delivery123"),
]

DELIVERY_TEAM = [
    "Rahul Sharma",
    "Amit Verma",
    "Suresh Kumar",
    "Vikram Singh",
    "Imran Khan",
]

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
        CREATE TABLE IF NOT EXISTS staff_users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            customer_name TEXT NOT NULL DEFAULT '',
            total REAL NOT NULL,
            original_total REAL NOT NULL DEFAULT 0,
            discount REAL NOT NULL DEFAULT 0,
            discount_percentage REAL NOT NULL DEFAULT 0,
            address TEXT NOT NULL,
            phone TEXT NOT NULL,
            payment TEXT NOT NULL,
            payment_details TEXT,
            status TEXT NOT NULL,
            delivery_person TEXT,
            delivery_accepted INTEGER NOT NULL DEFAULT 0,
            estimated_delivery_time TEXT,
            auto_delivered_at TEXT,
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
    db.execute(
        '''
        CREATE TABLE IF NOT EXISTS ratings(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            food_id INTEGER NOT NULL,
            order_id INTEGER NOT NULL,
            rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
            review TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, food_id, order_id),
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(food_id) REFERENCES foods(id),
            FOREIGN KEY(order_id) REFERENCES orders(id)
        )
        '''
    )
    ensure_staff_schema(db)
    ensure_orders_schema(db)
    db.commit()
    normalize_db_image_paths(db)
    seed_foods(db)
    seed_staff_users(db)
    fix_food_images(db)
    ensure_image_aliases()


def ensure_staff_schema(db):
    staff_columns = {col["name"] for col in db.execute("PRAGMA table_info(staff_users)").fetchall()}
    if not staff_columns:
        return
    if "role" not in staff_columns:
        db.execute("ALTER TABLE staff_users ADD COLUMN role TEXT NOT NULL DEFAULT 'manager'")
    if "is_active" not in staff_columns:
        db.execute("ALTER TABLE staff_users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")


def seed_staff_users(db):
    manager_password_hash = generate_password_hash(MANAGER_PASSWORD)
    existing_manager = db.execute("SELECT id FROM staff_users WHERE email = ?", (MANAGER_EMAIL,)).fetchone()
    if not existing_manager:
        db.execute(
            "INSERT INTO staff_users (name, email, password, role) VALUES (?, ?, ?, ?)",
            ("Hotel Manager", MANAGER_EMAIL, manager_password_hash, "manager"),
        )

    for name, email, password in DELIVERY_STAFF:
        existing_partner = db.execute("SELECT id FROM staff_users WHERE email = ?", (email,)).fetchone()
        if not existing_partner:
            db.execute(
                "INSERT INTO staff_users (name, email, password, role) VALUES (?, ?, ?, ?)",
                (name, email, generate_password_hash(password), "delivery_partner"),
            )


def ensure_orders_schema(db):
    order_columns = {col["name"] for col in db.execute("PRAGMA table_info(orders)").fetchall()}

    if "customer_name" not in order_columns:
        db.execute("ALTER TABLE orders ADD COLUMN customer_name TEXT NOT NULL DEFAULT ''")
    if "delivery_person" not in order_columns:
        db.execute("ALTER TABLE orders ADD COLUMN delivery_person TEXT")
    if "payment_details" not in order_columns:
        db.execute("ALTER TABLE orders ADD COLUMN payment_details TEXT")
    if "delivery_accepted" not in order_columns:
        db.execute("ALTER TABLE orders ADD COLUMN delivery_accepted INTEGER NOT NULL DEFAULT 0")
    if "rider_accepted_at" not in order_columns:
        db.execute("ALTER TABLE orders ADD COLUMN rider_accepted_at TEXT")
    if "auto_delivered_at" not in order_columns:
        db.execute("ALTER TABLE orders ADD COLUMN auto_delivered_at TEXT")

    db.execute(
        '''
        UPDATE orders
        SET customer_name = (
            SELECT users.name FROM users WHERE users.id = orders.user_id
        )
        WHERE customer_name IS NULL OR TRIM(customer_name) = ''
        '''
    )
    db.execute(
        '''
        UPDATE orders
        SET delivery_accepted = 1
        WHERE delivery_person IS NOT NULL
          AND TRIM(delivery_person) != ''
        '''
    )


def allocate_delivery_person(order_id):
    if not DELIVERY_TEAM:
        return "Not Assigned"
    return DELIVERY_TEAM[(order_id - 1) % len(DELIVERY_TEAM)]


def allocate_next_delivery_person(current_name):
    if not DELIVERY_TEAM:
        return "Not Assigned"
    if current_name not in DELIVERY_TEAM:
        return DELIVERY_TEAM[0]
    current_index = DELIVERY_TEAM.index(current_name)
    return DELIVERY_TEAM[(current_index + 1) % len(DELIVERY_TEAM)]


def delivery_room_name(staff_name):
    safe_name = (staff_name or "").strip().lower().replace(" ", "_")
    return f"delivery_{safe_name}"


def get_order_payload(order_id):
    order = query_db(
        '''
        SELECT
            o.*,
            u.email AS customer_email
        FROM orders o
        LEFT JOIN users u ON u.id = o.user_id
        WHERE o.id = ?
        ''',
        (order_id,),
        one=True,
    )
    if not order:
        return None

    return {
        "id": order["id"],
        "user_id": order["user_id"],
        "customer_name": order["customer_name"],
        "customer_email": order["customer_email"],
        "total": float(order["total"] or 0),
        "payment": order["payment"],
        "status": order["status"],
        "delivery_person": order["delivery_person"],
        "address": order["address"],
        "phone": order["phone"],
        "created_at": order["created_at"],
        "estimated_delivery_time": order["estimated_delivery_time"],
    }


def status_to_socket_event(status):
    status_map = {
        "Order Placed": "order_created",
        "Order Accepted": "order_accepted",
        "Preparing Food": "preparing",
        "Ready for Pickup": "restaurant_ready",
        "Rider Assigned": "rider_accepted",
        "Picked Up": "picked_up",
        "On the Way": "on_the_way",
        "Delivered": "delivered",
        "Rejected": "cancelled",
        "Cancelled": "cancelled",
    }
    return status_map.get(status, "order_updated")


def emit_order_event(order_id, event_name=None, extra_payload=None):
    payload = get_order_payload(order_id)
    if not payload:
        return

    payload["event"] = event_name or status_to_socket_event(payload["status"])
    if extra_payload:
        payload.update(extra_payload)

    socketio.emit("order_event", payload, room="manager")
    socketio.emit("order_event", payload, room=f"customer_{payload['user_id']}")

    if payload.get("delivery_person"):
        socketio.emit("order_event", payload, room=delivery_room_name(payload["delivery_person"]))


def update_due_delivery_statuses():
    db = get_db()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    due_orders = db.execute(
        '''
        SELECT id
        FROM orders
                WHERE status NOT IN ('Delivered', 'Cancelled', 'Rejected')
          AND auto_delivered_at IS NOT NULL
          AND auto_delivered_at <= ?
        ''',
        (current_time,),
    ).fetchall()

    db.execute(
        '''
        UPDATE orders
        SET status = 'Delivered'
                WHERE status NOT IN ('Delivered', 'Cancelled', 'Rejected')
          AND auto_delivered_at IS NOT NULL
          AND auto_delivered_at <= ?
        ''',
        (current_time,),
    )
    db.commit()

    for due_order in due_orders:
        emit_order_event(due_order["id"], "delivered")


@socketio.on("connect")
def handle_socket_connect():
    role = session.get("account_role")
    join_room("global")

    if role == "manager":
        join_room("manager")
    elif role == "customer" and session.get("user_id"):
        join_room(f"customer_{session['user_id']}")
    elif role == "delivery_partner" and session.get("staff_name"):
        join_room(delivery_room_name(session["staff_name"]))


@socketio.on("rider_location_update")
def handle_rider_location_update(data):
    order_id = data.get("order_id")
    lat = data.get("lat")
    lng = data.get("lng")
    if not order_id or lat is None or lng is None:
        return

    order = query_db("SELECT id, user_id FROM orders WHERE id = ?", (order_id,), one=True)
    if not order:
        return

    location_payload = {
        "order_id": order["id"],
        "lat": lat,
        "lng": lng,
        "event": "rider_location",
    }
    socketio.emit("rider_location", location_payload, room="manager")
    socketio.emit("rider_location", location_payload, room=f"customer_{order['user_id']}")


@socketio.on("near_customer")
def handle_near_customer(data):
    order_id = data.get("order_id")
    if not order_id:
        return
    emit_order_event(order_id, "near_customer")


def normalize_db_image_paths(db):
    foods = db.execute("SELECT id, image FROM foods").fetchall()
    for food in foods:
        image = food["image"]
        if not image or image.startswith("http"):
            continue
        normalized = image.replace("\\", "/").strip()
        if not normalized.startswith("images/"):
            normalized = f"images/{normalized.split('/')[-1]}"
        normalized = normalized.lower()
        if normalized != image:
            db.execute("UPDATE foods SET image = ? WHERE id = ?", (normalized, food["id"]))
    db.commit()


def ensure_image_aliases():
    image_dir = os.path.join(BASE_DIR, "static", "images")
    alias_pairs = [
        ("margherita_pizza.png", "margherita_pizza.jpeg"),
        ("bbq_chicken_pizza.png", "bbq_chicken_pizza.jpeg"),
        ("caesar_salad.png", "caesar_salad.jpeg"),
        ("chocolate_cake.png", "chocolate_cake.jpeg"),
        ("spaghetti_bolognese.png", "spaghetti_bolognese.jpeg"),
        ("fish_curry.png", "fish_curry.jpeg"),
        ("vanilla_ice_cream.png", "vanilla_ice_cream.jpeg"),
    ]
    for source_name, alias_name in alias_pairs:
        source_path = os.path.join(image_dir, source_name)
        alias_path = os.path.join(image_dir, alias_name)
        if os.path.exists(source_path) and not os.path.exists(alias_path):
            shutil.copyfile(source_path, alias_path)


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


def is_allowed_image(filename):
    if not filename:
        return False
    mime_type, _ = mimetypes.guess_type(filename)
    return bool(mime_type and mime_type.startswith("image/"))


def save_uploaded_food_image(uploaded_file):
    if not uploaded_file or not uploaded_file.filename:
        return None, "Please upload an image file."

    mime_type = (uploaded_file.mimetype or "").lower()
    if not mime_type.startswith("image/") and not is_allowed_image(uploaded_file.filename):
        return None, "Invalid file type. Please upload an image file."

    os.makedirs(UPLOAD_DIR, exist_ok=True)

    original_name = secure_filename(uploaded_file.filename)
    name_part, extension = os.path.splitext(original_name)
    extension = extension.lower()
    if not extension and mime_type.startswith("image/"):
        guessed_extension = mimetypes.guess_extension(mime_type)
        extension = (guessed_extension or ".img").lower()
    if not name_part:
        name_part = "food_image"
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    safe_name = f"{name_part[:40]}_{timestamp}{extension}"
    save_path = os.path.join(UPLOAD_DIR, safe_name)
    uploaded_file.save(save_path)
    return f"images/{safe_name}", None


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def login_required(func):
    def wrapper(*args, **kwargs):
        if session.get("account_role") != "customer" or not session.get("user_id"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return func(*args, **kwargs)

    wrapper.__name__ = func.__name__
    return wrapper


def role_required(*allowed_roles):
    def decorator(func):
        def wrapper(*args, **kwargs):
            if session.get("account_role") not in allowed_roles:
                flash("Access required for this dashboard.", "warning")
                return redirect(url_for("home"))
            return func(*args, **kwargs)

        wrapper.__name__ = func.__name__
        return wrapper

    return decorator


def admin_required(func):
    return role_required("manager")(func)


def delivery_required(func):
    return role_required("delivery_partner")(func)


def customer_required(func):
    return role_required("customer")(func)


def calculate_discount(total):
    '''Calculate 20% discount for orders above 300'''
    discount_amount = 0.0
    discount_percentage = 0.0
    if total > 300:
        discount_percentage = 20
        discount_amount = total * (discount_percentage / 100)
    return discount_amount, discount_percentage


def calculate_estimated_delivery():
    '''Calculate estimated delivery time (30 minutes from now)'''
    current_time = datetime.now()
    delivery_time = current_time + timedelta(minutes=30)
    return delivery_time


def validate_payment_and_details(form, payment_method):
    """Validate payment inputs for each method and return sanitized summary."""
    method = (payment_method or "").strip()

    if method == "Cash on Delivery":
        cod_confirm = form.get("cod_confirm")
        if cod_confirm != "yes":
            return None, "Please confirm Cash on Delivery before placing order."
        return "Cash on Delivery confirmed", None

    if method == "UPI":
        upi_reference = (form.get("upi_transaction_id") or "").strip()
        if len(upi_reference) < 6:
            return None, "Please enter a valid UPI transaction/reference ID."
        return f"UPI reference: {upi_reference}", None

    if method == "Debit/Credit Card":
        card_number = re.sub(r"\s+", "", (form.get("card_number") or "").strip())
        card_holder = (form.get("card_holder") or "").strip()
        card_expiry = (form.get("card_expiry") or "").strip()
        card_cvv = (form.get("card_cvv") or "").strip()

        if not (card_number.isdigit() and 13 <= len(card_number) <= 19):
            return None, "Please enter a valid card number."
        if len(card_holder) < 2:
            return None, "Please enter the card holder name."
        if not re.match(r"^(0[1-9]|1[0-2])/[0-9]{2}$", card_expiry):
            return None, "Card expiry must be in MM/YY format."
        if not (card_cvv.isdigit() and len(card_cvv) in (3, 4)):
            return None, "Please enter a valid card CVV."

        return f"Card payment (ending {card_number[-4:]})", None

    if method == "Net Banking":
        bank_name = (form.get("bank_name") or "").strip()
        account_holder = (form.get("netbanking_account_holder") or "").strip()
        account_last4 = (form.get("netbanking_account_last4") or "").strip()

        if len(bank_name) < 2:
            return None, "Please select or enter your bank name."
        if len(account_holder) < 2:
            return None, "Please enter account holder name for net banking."
        if not (account_last4.isdigit() and len(account_last4) == 4):
            return None, "Please enter last 4 digits of the bank account."

        return f"Net banking: {bank_name} (A/C ending {account_last4})", None

    if method == "Wallet":
        wallet_provider = (form.get("wallet_provider") or "").strip()
        wallet_mobile = (form.get("wallet_mobile") or "").strip()

        if len(wallet_provider) < 2:
            return None, "Please select a wallet provider."
        if not re.match(r"^[0-9]{10}$", wallet_mobile):
            return None, "Wallet mobile number must be exactly 10 digits."

        return f"Wallet: {wallet_provider} ({wallet_mobile})", None

    return None, "Invalid payment method selected."


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
            '''
            SELECT
                f.*,
                COALESCE(AVG(r.rating), 0) AS avg_rating,
                COUNT(r.id) AS rating_count
            FROM foods f
            LEFT JOIN ratings r ON r.food_id = f.id
            WHERE f.name LIKE ? OR f.description LIKE ?
            GROUP BY f.id
            ORDER BY f.id DESC
            LIMIT 8
            ''',
            (f"%{search}%", f"%{search}%"),
        )
    else:
        foods = query_db(
            '''
            SELECT
                f.*,
                COALESCE(AVG(r.rating), 0) AS avg_rating,
                COUNT(r.id) AS rating_count
            FROM foods f
            LEFT JOIN ratings r ON r.food_id = f.id
            GROUP BY f.id
            ORDER BY f.id DESC
            LIMIT 8
            '''
        )
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
    if session.get("account_role") == "customer" and session.get("user_id"):
        return redirect(url_for("customer_dashboard"))
    if session.get("account_role") == "manager" and session.get("staff_id"):
        return redirect(url_for("admin_dashboard"))
    if session.get("account_role") == "delivery_partner" and session.get("staff_id"):
        return redirect(url_for("delivery_dashboard"))

    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = query_db("SELECT * FROM users WHERE email = ?", (email,), one=True)
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["user_email"] = user["email"]
            session["account_role"] = "customer"
            flash(f"Welcome, {user['name']}!", "success")
            return redirect(url_for("customer_dashboard"))

        flash("Invalid email or password.", "danger")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/customer/dashboard")
@login_required
def customer_dashboard():
    update_due_delivery_statuses()
    recent_orders = query_db(
        '''
        SELECT *
        FROM orders
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 6
        ''',
        (session["user_id"],)
    )
    order_summary = query_db(
        '''
        SELECT
            COUNT(*) AS total_orders,
            SUM(CASE WHEN status = 'Delivered' THEN 1 ELSE 0 END) AS delivered_orders,
            SUM(CASE WHEN status NOT IN ('Delivered', 'Cancelled', 'Rejected') THEN 1 ELSE 0 END) AS active_orders
        FROM orders
        WHERE user_id = ?
        ''',
        (session["user_id"],),
        one=True,
    )
    return render_template(
        "customer_dashboard.html",
        recent_orders=recent_orders,
        order_summary=order_summary,
    )


@app.route("/logout")
def logout():
    session_keys = ["user_id", "user_name", "user_email", "cart", "account_role", "staff_id", "staff_name", "staff_email", "staff_role"]
    for key in session_keys:
        session.pop(key, None)
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


@app.route("/manager/login", methods=["GET", "POST"])
def manager_login():
    if session.get("account_role") == "manager" and session.get("staff_id"):
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        staff = query_db("SELECT * FROM staff_users WHERE email = ? AND role = 'manager' AND is_active = 1", (email,), one=True)
        if staff and check_password_hash(staff["password"], password):
            session["staff_id"] = staff["id"]
            session["staff_name"] = staff["name"]
            session["staff_email"] = staff["email"]
            session["staff_role"] = staff["role"]
            session["account_role"] = "manager"
            flash(f"Welcome, {staff['name']}!", "success")
            return redirect(url_for("admin_dashboard"))

        flash("Invalid manager credentials.", "danger")
        return redirect(url_for("manager_login"))

    return render_template("manager_login.html")


@app.route("/manager")
def manager_route():
    return redirect(url_for("manager_login"))


@app.route("/delivery/login", methods=["GET", "POST"])
def delivery_login():
    if session.get("account_role") == "delivery_partner" and session.get("staff_id"):
        return redirect(url_for("delivery_dashboard"))

    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        staff = query_db("SELECT * FROM staff_users WHERE email = ? AND role = 'delivery_partner' AND is_active = 1", (email,), one=True)
        if staff and check_password_hash(staff["password"], password):
            session["staff_id"] = staff["id"]
            session["staff_name"] = staff["name"]
            session["staff_email"] = staff["email"]
            session["staff_role"] = staff["role"]
            session["account_role"] = "delivery_partner"
            flash(f"Welcome, {staff['name']}!", "success")
            return redirect(url_for("delivery_dashboard"))

        flash("Invalid delivery partner credentials.", "danger")
        return redirect(url_for("delivery_login"))

    return render_template("delivery_login.html")


@app.route("/menu")
def menu():
    category = request.args.get("category")
    search = request.args.get("q", "")
    query = """
    SELECT
        f.*,
        COALESCE(AVG(r.rating), 0) AS avg_rating,
        COUNT(r.id) AS rating_count
    FROM foods f
    LEFT JOIN ratings r ON r.food_id = f.id
    """
    args = []
    filters = []
    if category:
        filters.append("f.category = ?")
        args.append(category)
    if search:
        filters.append("(f.name LIKE ? OR f.description LIKE ?)")
        args.extend([f"%{search}%", f"%{search}%"])
    if filters:
        query += " WHERE " + " AND ".join(filters)
    query += " GROUP BY f.id ORDER BY f.id DESC"
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
    
    # Calculate estimated delivery time
    estimated_delivery = calculate_estimated_delivery()

    if request.method == "POST":
        customer_name = (request.form.get("customer_name") or "").strip()
        address = request.form.get("address")
        phone = request.form.get("phone")
        payment = request.form.get("payment")

        if not customer_name or not address or not phone or not payment:
            flash("All fields are required.", "danger")
            return redirect(url_for("checkout"))

        payment_details, payment_error = validate_payment_and_details(request.form, payment)
        if payment_error:
            flash(payment_error, "danger")
            return redirect(url_for("checkout"))

        db = get_db()
        cursor = db.execute(
            '''
            INSERT INTO orders (user_id, customer_name, total, original_total, discount, discount_percentage, address, phone, payment, payment_details, status, estimated_delivery_time, auto_delivered_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                session["user_id"],
                customer_name,
                final_total,
                total,
                discount_amount,
                discount_percentage,
                address,
                phone,
                payment,
                payment_details,
                "Order Placed",
                None,
                None,
            )
        )
        order_id = cursor.lastrowid
        assigned_delivery_person = allocate_delivery_person(order_id)
        db.execute(
            "UPDATE orders SET delivery_person = ?, delivery_accepted = 0 WHERE id = ?",
            (assigned_delivery_person, order_id),
        )

        for item in items:
            db.execute(
                "INSERT INTO order_items (order_id, food_id, qty) VALUES (?, ?, ?)",
                (order_id, item["food"]["id"], item["qty"])
            )
        db.commit()

        emit_order_event(order_id, "order_created")
        if assigned_delivery_person and assigned_delivery_person != "Not Assigned":
            emit_order_event(order_id, "rider_assigned")

        session.pop("cart", None)
        flash("Order placed successfully!", "success")
        return redirect(url_for("order_success", order_id=order_id))

    return render_template(
        "checkout.html",
        items=items,
        total=total,
        discount_amount=discount_amount,
        discount_percentage=discount_percentage,
        final_total=final_total,
        estimated_delivery=estimated_delivery,
        customer_name=session.get("user_name", ""),
    )


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
    update_due_delivery_statuses()
    order = query_db("SELECT * FROM orders WHERE id = ? AND user_id = ?", (order_id, session["user_id"]), one=True)
    if not order:
        flash("Order not found.", "danger")
        return redirect(url_for("home"))

    return render_template("order_success.html", order=order)


@app.route("/track_order/<int:order_id>")
@login_required
def track_order(order_id):
    update_due_delivery_statuses()
    order = query_db("SELECT * FROM orders WHERE id = ? AND user_id = ?", (order_id, session["user_id"]), one=True)
    if not order:
        flash("Order not found.", "danger")
        return redirect(url_for("home"))

    order_items = query_db(
        '''
        SELECT
            oi.food_id,
            oi.qty,
            f.name,
            f.category,
            f.price,
            r.rating AS user_rating,
            r.review AS user_review
        FROM order_items oi
        JOIN foods f ON oi.food_id = f.id
        LEFT JOIN ratings r ON r.order_id = oi.order_id AND r.food_id = oi.food_id AND r.user_id = ?
        WHERE oi.order_id = ?
        ''',
        (session["user_id"], order_id)
    )

    return render_template("track_order.html", order=order, order_items=order_items)


@app.route("/rate_item/<int:order_id>/<int:food_id>", methods=["POST"])
@login_required
def rate_item(order_id, food_id):
    rating_raw = request.form.get("rating")
    review = (request.form.get("review") or "").strip()

    try:
        rating = int(rating_raw)
    except (TypeError, ValueError):
        flash("Please select a valid rating from 1 to 5.", "danger")
        return redirect(url_for("track_order", order_id=order_id))

    if rating < 1 or rating > 5:
        flash("Rating must be between 1 and 5.", "danger")
        return redirect(url_for("track_order", order_id=order_id))

    eligible_item = query_db(
        '''
        SELECT oi.id
        FROM order_items oi
        JOIN orders o ON o.id = oi.order_id
        WHERE oi.order_id = ?
          AND oi.food_id = ?
          AND o.user_id = ?
          AND o.status = 'Delivered'
        ''',
        (order_id, food_id, session["user_id"]),
        one=True,
    )

    if not eligible_item:
        flash("You can rate only delivered items from your own orders.", "warning")
        return redirect(url_for("track_order", order_id=order_id))

    db = get_db()
    db.execute(
        '''
        INSERT INTO ratings (user_id, food_id, order_id, rating, review, updated_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id, food_id, order_id)
        DO UPDATE SET
            rating = excluded.rating,
            review = excluded.review,
            updated_at = CURRENT_TIMESTAMP
        ''',
        (session["user_id"], food_id, order_id, rating, review),
    )
    db.commit()

    flash("Thanks! Your rating has been saved.", "success")
    return redirect(url_for("track_order", order_id=order_id))


@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    return redirect(url_for("manager_login"))


@app.route("/admin_logout")
def admin_logout():
    return redirect(url_for("logout"))


@app.route("/admin")
@app.route("/manager/dashboard")
@admin_required
def admin_dashboard():
    update_due_delivery_statuses()
    foods = query_db("SELECT * FROM foods ORDER BY id DESC")
    order_stats = query_db(
        '''
        SELECT
            COUNT(*) AS total_orders,
            SUM(CASE WHEN status = 'Delivered' THEN 1 ELSE 0 END) AS delivered_orders,
            SUM(CASE WHEN status NOT IN ('Delivered', 'Cancelled', 'Rejected') THEN 1 ELSE 0 END) AS active_orders
        FROM orders
        ''',
        one=True,
    )
    delivery_panel = query_db(
        '''
        SELECT
            o.delivery_person,
            COUNT(*) AS assigned_orders,
            SUM(CASE WHEN o.status = 'Delivered' THEN 1 ELSE 0 END) AS delivered_orders,
            SUM(CASE WHEN o.status NOT IN ('Delivered', 'Cancelled', 'Rejected') THEN 1 ELSE 0 END) AS active_orders,
            COALESCE(
                (
                    SELECT o2.status
                    FROM orders o2
                    WHERE o2.delivery_person = o.delivery_person
                    ORDER BY o2.created_at DESC
                    LIMIT 1
                ),
                'Idle'
            ) AS latest_status
        FROM orders o
        WHERE o.delivery_person IS NOT NULL AND TRIM(o.delivery_person) != ''
        GROUP BY o.delivery_person
        ORDER BY active_orders DESC, assigned_orders DESC
        '''
    )
    return render_template(
        "manager_dashboard.html",
        foods=foods,
        order_stats=order_stats,
        delivery_panel=delivery_panel,
    )


@app.route("/admin/orders")
@app.route("/manager/orders")
@admin_required
def admin_orders():
    update_due_delivery_statuses()
    orders = query_db(
        '''
        SELECT
            o.*,
            COALESCE(NULLIF(o.customer_name, ''), u.name, 'Guest') AS customer_name,
            u.email AS customer_email,
            CASE
                WHEN o.status = 'Delivered' THEN 'Completed'
                WHEN o.status = 'On the Way' THEN 'On Route'
                WHEN o.status = 'Ready for Pickup' THEN 'Ready to Dispatch'
                WHEN o.status = 'Rider Assigned' THEN 'Rider Assigned'
                WHEN o.status = 'Order Accepted' THEN 'Accepted'
                ELSE 'Preparing'
            END AS delivery_boy_status
        FROM orders o
        LEFT JOIN users u ON u.id = o.user_id
        WHERE o.status NOT IN ('Delivered', 'Cancelled', 'Rejected')
        ORDER BY o.created_at DESC
        '''
    )
    return render_template("admin_orders.html", orders=orders)


@app.route("/admin/foods", methods=["GET", "POST"])
@app.route("/manager/foods", methods=["GET", "POST"])
@admin_required
def admin_foods():
    if request.method == "POST":
        name = request.form.get("name")
        category = request.form.get("category")
        price = request.form.get("price")
        image_file = request.files.get("image_file")
        description = request.form.get("description")

        if not name or not category or not price or not description:
            flash("All fields are required.", "danger")
            return redirect(url_for("admin_foods"))

        try:
            price = float(price)
        except ValueError:
            flash("Invalid price.", "danger")
            return redirect(url_for("admin_foods"))

        image, upload_error = save_uploaded_food_image(image_file)
        if upload_error:
            flash(upload_error, "danger")
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


@app.route("/admin/foods/edit/<int:food_id>", methods=["POST"])
@app.route("/manager/foods/edit/<int:food_id>", methods=["POST"])
@admin_required
def edit_food(food_id):
    name = request.form.get("name")
    category = request.form.get("category")
    price = request.form.get("price")
    description = request.form.get("description")
    image_file = request.files.get("image_file")

    if not name or not category or not price or not description:
        flash("All fields except image are required for update.", "danger")
        return redirect(url_for("admin_foods"))

    try:
        price = float(price)
    except ValueError:
        flash("Invalid price.", "danger")
        return redirect(url_for("admin_foods"))

    db = get_db()
    existing = db.execute("SELECT image FROM foods WHERE id = ?", (food_id,)).fetchone()
    if not existing:
        flash("Food item not found.", "warning")
        return redirect(url_for("admin_foods"))

    updated_image = existing["image"]
    if image_file and image_file.filename:
        saved_image, upload_error = save_uploaded_food_image(image_file)
        if upload_error:
            flash(upload_error, "danger")
            return redirect(url_for("admin_foods"))
        updated_image = saved_image

    db.execute(
        "UPDATE foods SET name = ?, category = ?, price = ?, image = ?, description = ? WHERE id = ?",
        (name, category, price, updated_image, description, food_id),
    )
    db.commit()
    flash("Food item updated successfully.", "success")
    return redirect(url_for("admin_foods"))


@app.route("/admin/foods/delete/<int:food_id>", methods=["POST"])
@app.route("/manager/foods/delete/<int:food_id>", methods=["POST"])
@admin_required
def delete_food(food_id):
    db = get_db()
    food = db.execute("SELECT id, image, name FROM foods WHERE id = ?", (food_id,)).fetchone()
    if not food:
        flash("Food item not found.", "warning")
        return redirect(url_for("admin_dashboard"))

    linked_items = db.execute("SELECT COUNT(*) AS count FROM order_items WHERE food_id = ?", (food_id,)).fetchone()
    if linked_items and linked_items["count"] > 0:
        flash("This item cannot be deleted because it exists in customer orders.", "warning")
        return redirect(url_for("admin_dashboard"))

    db.execute("DELETE FROM ratings WHERE food_id = ?", (food_id,))
    db.execute("DELETE FROM foods WHERE id = ?", (food_id,))
    db.commit()

    image_path = food["image"] or ""
    if image_path.startswith("images/"):
        still_used = db.execute("SELECT 1 FROM foods WHERE image = ? LIMIT 1", (image_path,)).fetchone()
        protected_images = {item[3] for item in FOOD_CATALOG}
        if not still_used and image_path not in protected_images:
            absolute_image_path = os.path.join(BASE_DIR, "static", image_path.replace("/", os.sep))
            if os.path.exists(absolute_image_path):
                os.remove(absolute_image_path)

    flash(f"'{food['name']}' deleted successfully.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/order/status/<int:order_id>/<status>")
@app.route("/manager/order/status/<int:order_id>/<status>")
@admin_required
def update_order_status(order_id, status):
    valid_statuses = ["Order Accepted", "Preparing Food", "Ready for Pickup", "Rejected", "Cancelled", "Delivered"]
    if status not in valid_statuses:
        flash("Invalid status.", "danger")
        return redirect(url_for("admin_orders"))
    db = get_db()
    db.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    db.commit()
    emit_order_event(order_id, status_to_socket_event(status))
    flash(f"Order status updated to {status}.", "success")
    return redirect(url_for("admin_orders"))


@app.route("/delivery/dashboard")
@delivery_required
def delivery_dashboard():
    update_due_delivery_statuses()
    assigned_orders = query_db(
        '''
        SELECT
            o.*,
            u.name AS customer_name,
            u.email AS customer_email
        FROM orders o
        LEFT JOIN users u ON u.id = o.user_id
        WHERE o.delivery_person = ?
        ORDER BY o.created_at DESC
        ''',
        (session.get("staff_name"),)
    )
    delivery_stats = query_db(
        '''
        SELECT
            COUNT(*) AS total_assigned,
            SUM(CASE WHEN delivery_accepted = 1 THEN 1 ELSE 0 END) AS accepted_orders,
            SUM(CASE WHEN status = 'Delivered' THEN 1 ELSE 0 END) AS delivered_orders,
            SUM(CASE WHEN status NOT IN ('Delivered', 'Cancelled', 'Rejected') THEN 1 ELSE 0 END) AS active_orders
        FROM orders
        WHERE delivery_person = ?
        ''',
        (session.get("staff_name"),),
        one=True,
    )
    return render_template(
        "delivery_dashboard.html",
        assigned_orders=assigned_orders,
        delivery_stats=delivery_stats,
    )


@app.route("/delivery/order/status/<int:order_id>/<status>")
@delivery_required
def delivery_update_order_status(order_id, status):
    valid_statuses = ["Accept", "Reject", "Picked Up", "On the Way", "Delivered"]
    if status not in valid_statuses:
        flash("Invalid delivery status.", "danger")
        return redirect(url_for("delivery_dashboard"))

    db = get_db()
    order = db.execute(
        "SELECT id, delivery_person, status FROM orders WHERE id = ? AND delivery_person = ?",
        (order_id, session.get("staff_name")),
    ).fetchone()
    if not order:
        flash("Order not assigned to you.", "warning")
        return redirect(url_for("delivery_dashboard"))

    event_name = None
    if status == "Accept":
        eta_time = datetime.now() + timedelta(minutes=30)
        db.execute(
            "UPDATE orders SET status = ?, delivery_accepted = 1, rider_accepted_at = CURRENT_TIMESTAMP, auto_delivered_at = ?, estimated_delivery_time = ? WHERE id = ?",
            (
                "Rider Assigned",
                eta_time.strftime("%Y-%m-%d %H:%M:%S"),
                eta_time.strftime("%Y-%m-%d %H:%M:%S"),
                order_id,
            ),
        )
        event_name = "rider_accepted"
    elif status == "Reject":
        next_rider = allocate_next_delivery_person(order["delivery_person"])
        db.execute(
            "UPDATE orders SET delivery_person = ?, delivery_accepted = 0, rider_accepted_at = NULL, status = ? WHERE id = ?",
            (next_rider, "Ready for Pickup", order_id),
        )
        event_name = "rider_assigned"
    else:
        db.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
        event_name = status_to_socket_event(status)

    db.commit()
    emit_order_event(order_id, event_name)
    flash(f"Delivery status updated to {status}.", "success")
    return redirect(url_for("delivery_dashboard"))


@app.route("/api/order/check/<int:order_id>")
def check_order_status(order_id):
    update_due_delivery_statuses()
    order = query_db("SELECT * FROM orders WHERE id = ?", (order_id,), one=True)
    if order:
        return jsonify({"status": order["status"], "id": order["id"]})
    return jsonify({"status": "not_found", "id": order_id}), 404


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=True)
