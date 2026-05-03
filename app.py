import os
import re
import shutil
import sqlite3
import base64
import mimetypes
import json
import threading
from io import BytesIO
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session, g, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
try:
    import qrcode
except ImportError:
    qrcode = None

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, rely on system environment variables

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey_for_demo_only")
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = int(os.environ.get("STATIC_CACHE_SECONDS", "86400"))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if os.environ.get("DATABASE_PATH"):
    DATABASE_PATH = os.environ.get("DATABASE_PATH")
elif os.environ.get("RENDER"):
    render_disk_path = os.environ.get("RENDER_DISK_MOUNT_PATH")
    if render_disk_path:
        DATABASE_PATH = os.path.join(render_disk_path, "database.db")
    else:
        DATABASE_PATH = os.path.join("/tmp", "database.db")
else:
    DATABASE_PATH = os.path.join(BASE_DIR, "database.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "images")

DB_INIT_LOCK = threading.Lock()
DB_INIT_DONE = False
CACHE_LOCK = threading.Lock()
APP_CACHE = {}
CACHE_TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", "15"))

# Admin authentication via environment variables - NEVER hardcode credentials
ADMIN_MOBILE = os.environ.get("ADMIN_MOBILE")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
DEFAULT_ADMIN_MOBILE = os.environ.get("DEFAULT_ADMIN_MOBILE", "9000000000")
DEFAULT_ADMIN_PASSWORD = os.environ.get("DEFAULT_ADMIN_PASSWORD", "admin@123")

# Validation: ensure both are provided in production
if not ADMIN_MOBILE or not ADMIN_PASSWORD:
    import warnings
    warnings.warn(
        "⚠️ SECURITY WARNING: ADMIN_MOBILE and ADMIN_PASSWORD environment variables are not set. "
        "A development admin account may be created automatically if no admin exists. "
        "Set these variables before deploying to production.",
        RuntimeWarning
    )

MANAGER_MOBILE = os.environ.get("MANAGER_MOBILE", "9000000001")

MANAGER_EMAIL = os.environ.get("MANAGER_EMAIL", "manager@foodflux.local")
MANAGER_PASSWORD = os.environ.get("MANAGER_PASSWORD") or (ADMIN_PASSWORD if ADMIN_PASSWORD else "manager@123")

DELIVERY_STAFF = [
    ("Rahul Sharma", "rahul@ckfood.com", "delivery123", "9000000002"),
    ("Amit Verma", "amit@ckfood.com", "delivery123", "9000000003"),
    ("Suresh Kumar", "suresh@ckfood.com", "delivery123", "9000000004"),
    ("Vikram Singh", "vikram@ckfood.com", "delivery123", "9000000005"),
    ("Imran Khan", "imran@ckfood.com", "delivery123", "9000000006"),
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

MANAGER_WORKFLOW = {
    "Order Placed": ["Order Accepted", "Rejected"],
    "Order Accepted": ["Preparing Food", "Cancelled"],
    "Preparing Food": ["Ready for Pickup", "Cancelled"],
    "Ready for Pickup": [],
    "Rider Assigned": [],
    "Picked Up": [],
    "On the Way": [],
    "Near Customer": [],
    "Delivered": [],
    "Rejected": [],
    "Cancelled": [],
}

DELIVERY_ACTION_WORKFLOW = {
    "Ready for Pickup": ["Accept", "Reject"],
    "Rider Assigned": ["Picked Up"],
    "Picked Up": ["On the Way"],
    "On the Way": ["Near Customer"],
    "Near Customer": ["Delivered"],
}

TRACKER_STEPS = [
    "Order Placed",
    "Order Accepted",
    "Preparing Food",
    "Ready for Pickup",
    "Picked Up",
    "On the Way",
    "Near Customer",
    "Delivered",
]


def status_step_index(status):
    if status in TRACKER_STEPS:
        return TRACKER_STEPS.index(status)
    if status == "Rider Assigned":
        return TRACKER_STEPS.index("Ready for Pickup")
    return -1


def manager_allowed_actions(status):
    return MANAGER_WORKFLOW.get(status, [])


def delivery_allowed_actions(status):
    return DELIVERY_ACTION_WORKFLOW.get(status, [])


def customer_details_visible_for_delivery(status):
    return status in {"Ready for Pickup", "Rider Assigned", "Picked Up", "On the Way", "Near Customer", "Delivered"}


def safe_next_url(next_url, fallback_endpoint):
    if next_url and next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    return url_for(fallback_endpoint)


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db_dir = os.path.dirname(DATABASE_PATH)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
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
            mobile_number TEXT,
            mobile_verified INTEGER NOT NULL DEFAULT 0,
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
            mobile_number TEXT,
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
    db.execute(
        '''
        CREATE TABLE IF NOT EXISTS service_ratings(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            order_id INTEGER NOT NULL,
            target_type TEXT NOT NULL,
            target_name TEXT,
            rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
            review TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, order_id, target_type),
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(order_id) REFERENCES orders(id)
        )
        '''
    )
    db.execute(
        '''
        CREATE TABLE IF NOT EXISTS rider_locations(
            order_id INTEGER PRIMARY KEY,
            lat REAL NOT NULL,
            lng REAL NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(order_id) REFERENCES orders(id)
        )
        '''
    )
    db.execute(
        '''
        CREATE TABLE IF NOT EXISTS notifications(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'info',
            is_read INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
    )
    db.execute(
        '''
        CREATE TABLE IF NOT EXISTS order_timeline(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            actor_type TEXT NOT NULL DEFAULT 'system',
            actor_name TEXT,
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(order_id) REFERENCES orders(id)
        )
        '''
    )
    ensure_users_schema(db)
    ensure_staff_schema(db)
    ensure_foods_schema(db)
    ensure_orders_schema(db)
    ensure_performance_indexes(db)
    db.commit()
    normalize_db_image_paths(db)
    seed_foods(db)
    seed_staff_users(db)
    fix_food_images(db)
    ensure_image_aliases()


def ensure_users_schema(db):
    user_columns = {col["name"] for col in db.execute("PRAGMA table_info(users)").fetchall()}
    if not user_columns:
        return
    if "mobile_number" not in user_columns:
        db.execute("ALTER TABLE users ADD COLUMN mobile_number TEXT")
    if "mobile_verified" not in user_columns:
        db.execute("ALTER TABLE users ADD COLUMN mobile_verified INTEGER NOT NULL DEFAULT 0")


def ensure_staff_schema(db):
    staff_columns = {col["name"] for col in db.execute("PRAGMA table_info(staff_users)").fetchall()}
    if not staff_columns:
        return
    if "role" not in staff_columns:
        db.execute("ALTER TABLE staff_users ADD COLUMN role TEXT NOT NULL DEFAULT 'manager'")
    if "is_active" not in staff_columns:
        db.execute("ALTER TABLE staff_users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
    if "mobile_number" not in staff_columns:
        db.execute("ALTER TABLE staff_users ADD COLUMN mobile_number TEXT")
    if "mobile_verified" not in staff_columns:
        db.execute("ALTER TABLE staff_users ADD COLUMN mobile_verified INTEGER NOT NULL DEFAULT 0")


def ensure_foods_schema(db):
    food_columns = {col["name"] for col in db.execute("PRAGMA table_info(foods)").fetchall()}
    if not food_columns:
        return
    if "stock_qty" not in food_columns:
        db.execute("ALTER TABLE foods ADD COLUMN stock_qty INTEGER NOT NULL DEFAULT 25")
    if "is_available" not in food_columns:
        db.execute("ALTER TABLE foods ADD COLUMN is_available INTEGER NOT NULL DEFAULT 1")
    if "is_deleted" not in food_columns:
        db.execute("ALTER TABLE foods ADD COLUMN is_deleted INTEGER NOT NULL DEFAULT 0")


def ensure_performance_indexes(db):
    index_statements = [
        "CREATE INDEX IF NOT EXISTS idx_users_lower_email ON users(LOWER(email))",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_mobile_unique ON users(mobile_number) WHERE mobile_number IS NOT NULL",
        "CREATE INDEX IF NOT EXISTS idx_staff_users_lower_email_role_active ON staff_users(LOWER(email), role, is_active)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_staff_users_mobile_unique ON staff_users(mobile_number) WHERE mobile_number IS NOT NULL",
        "CREATE INDEX IF NOT EXISTS idx_orders_user_created_at ON orders(user_id, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)",
        "CREATE INDEX IF NOT EXISTS idx_orders_delivery_status ON orders(delivery_person, status)",
        "CREATE INDEX IF NOT EXISTS idx_orders_auto_delivered_at ON orders(auto_delivered_at)",
        "CREATE INDEX IF NOT EXISTS idx_foods_visible ON foods(is_deleted, is_available, stock_qty)",
        "CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id)",
        "CREATE INDEX IF NOT EXISTS idx_order_items_food_id ON order_items(food_id)",
        "CREATE INDEX IF NOT EXISTS idx_ratings_user_order ON ratings(user_id, order_id)",
        "CREATE INDEX IF NOT EXISTS idx_service_ratings_user_order_target ON service_ratings(user_id, order_id, target_type)",
        "CREATE INDEX IF NOT EXISTS idx_rider_locations_updated_at ON rider_locations(updated_at)",
        "CREATE INDEX IF NOT EXISTS idx_notifications_target_read_created ON notifications(target_type, target_id, is_read, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_order_timeline_order_created ON order_timeline(order_id, created_at DESC)",
    ]
    for statement in index_statements:
        db.execute(statement)


def seed_staff_users(db):
    existing_staff_rows = db.execute("SELECT email, mobile_number, role FROM staff_users").fetchall()
    existing_mobiles = {normalize_mobile(row["mobile_number"]) for row in existing_staff_rows if row["mobile_number"]}
    existing_mobiles.discard(None)
    existing_admin = any(row["role"] == "admin" for row in existing_staff_rows)

    if ADMIN_MOBILE and ADMIN_PASSWORD:
        admin_password_hash = generate_password_hash(ADMIN_PASSWORD)
        admin_mobile = normalize_mobile(ADMIN_MOBILE) or ADMIN_MOBILE
        if existing_admin:
            db.execute("UPDATE staff_users SET mobile_number = ?, password = ? WHERE role = 'admin'", (admin_mobile, admin_password_hash))
        else:
            admin_email = f"staff_{admin_mobile}@foodflux.local"
            db.execute(
                "INSERT INTO staff_users (name, email, mobile_number, mobile_verified, password, role) VALUES (?, ?, ?, 1, ?, ?)",
                ("FoodFlux Admin", admin_email, admin_mobile, admin_password_hash, "admin"),
            )
            existing_mobiles.add(admin_mobile)
    else:
        if not existing_admin:
            admin_password_hash = generate_password_hash(DEFAULT_ADMIN_PASSWORD)
            admin_mobile = normalize_mobile(DEFAULT_ADMIN_MOBILE) or DEFAULT_ADMIN_MOBILE
            import warnings
            warnings.warn(
                "⚠️ No ADMIN_MOBILE/ADMIN_PASSWORD provided. Creating a development admin account using default credentials. "
                "Do not use this in production.",
                RuntimeWarning,
            )
            admin_email = f"staff_{admin_mobile}@foodflux.local"
            db.execute(
                "INSERT INTO staff_users (name, email, mobile_number, mobile_verified, password, role) VALUES (?, ?, ?, 1, ?, ?)",
                ("FoodFlux Admin", admin_email, admin_mobile, admin_password_hash, "admin"),
            )
            existing_mobiles.add(admin_mobile)
    
    # Create manager account
    if MANAGER_PASSWORD:
        manager_password_hash = generate_password_hash(MANAGER_PASSWORD)
        manager_mobile = normalize_mobile(MANAGER_MOBILE) or MANAGER_MOBILE
        
        existing_staff_rows = db.execute("SELECT email, mobile_number FROM staff_users").fetchall()
        existing_emails = {row["email"].lower() for row in existing_staff_rows}
        existing_mobiles = {normalize_mobile(row["mobile_number"]) for row in existing_staff_rows if row["mobile_number"]}
        existing_mobiles.discard(None)

        if MANAGER_EMAIL.lower() not in existing_emails:
            db.execute(
                "INSERT INTO staff_users (name, email, mobile_number, mobile_verified, password, role) VALUES (?, ?, ?, 1, ?, ?)",
                ("Hotel Manager", MANAGER_EMAIL, manager_mobile, manager_password_hash, "manager"),
            )
            existing_emails.add(MANAGER_EMAIL.lower())
            existing_mobiles.add(manager_mobile)
        elif manager_mobile not in existing_mobiles:
            db.execute(
                "UPDATE staff_users SET mobile_number = ?, mobile_verified = 1 WHERE LOWER(email) = ? AND (mobile_number IS NULL OR TRIM(mobile_number) = '')",
                (manager_mobile, MANAGER_EMAIL.lower()),
            )
            existing_mobiles.add(manager_mobile)

    for name, email, password, mobile_number in DELIVERY_STAFF:
        if email.lower() not in existing_emails:
            db.execute(
                "INSERT INTO staff_users (name, email, mobile_number, mobile_verified, password, role) VALUES (?, ?, ?, 1, ?, ?)",
                (name, email, mobile_number, generate_password_hash(password), "delivery_partner"),
            )
            existing_emails.add(email.lower())
            existing_mobiles.add(mobile_number)
        elif mobile_number not in existing_mobiles:
            db.execute(
                "UPDATE staff_users SET mobile_number = ?, mobile_verified = 1 WHERE LOWER(email) = ? AND (mobile_number IS NULL OR TRIM(mobile_number) = '')",
                (mobile_number, email.lower()),
            )
            existing_mobiles.add(mobile_number)


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


def status_to_live_event(status):
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


def build_live_token(parts):
    return json.dumps(parts, sort_keys=True, separators=(",", ":"))


def emit_order_event(order_id, event_name=None, extra_payload=None):
    payload = get_order_payload(order_id)
    if not payload:
        return

    payload["event"] = event_name or status_to_live_event(payload["status"])
    if extra_payload:
        payload.update(extra_payload)

    # Polling clients will read fresh payloads from the /api/live endpoints.
    invalidate_cache("live:")


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
        log_order_timeline(due_order["id"], "Delivered", "system", "Auto Delivery", "Auto-marked as delivered by ETA")
        create_order_notifications(due_order["id"], "Delivered")
        emit_order_event(due_order["id"], "delivered")


def cache_get(cache_key):
    with CACHE_LOCK:
        cached = APP_CACHE.get(cache_key)
        if not cached:
            return None
        expires_at, value = cached
        if datetime.now() > expires_at:
            APP_CACHE.pop(cache_key, None)
            return None
        return value


def cache_set(cache_key, value, ttl_seconds=CACHE_TTL_SECONDS):
    with CACHE_LOCK:
        APP_CACHE[cache_key] = (datetime.now() + timedelta(seconds=ttl_seconds), value)


def invalidate_cache(prefix=None):
    with CACHE_LOCK:
        if not prefix:
            APP_CACHE.clear()
            return
        keys = [key for key in APP_CACHE.keys() if str(key).startswith(prefix)]
        for key in keys:
            APP_CACHE.pop(key, None)


def create_notification(target_type, target_id, title, message, category="info"):
    db = get_db()
    db.execute(
        '''
        INSERT INTO notifications (target_type, target_id, title, message, category, is_read)
        VALUES (?, ?, ?, ?, ?, 0)
        ''',
        (target_type, str(target_id), title, message, category),
    )
    db.commit()


def create_order_notifications(order_id, status):
    payload = get_order_payload(order_id)
    if not payload:
        return

    create_notification(
        "customer",
        payload["user_id"],
        f"Order #{order_id} {status}",
        f"Your order is now '{status}'.",
        "order",
    )
    create_notification("manager", "global", f"Order #{order_id} {status}", "Order status changed.", "order")
    if payload.get("delivery_person"):
        create_notification(
            "delivery_partner",
            payload["delivery_person"],
            f"Order #{order_id} {status}",
            "Delivery workflow updated.",
            "order",
        )


def log_order_timeline(order_id, status, actor_type="system", actor_name=None, note=None):
    db = get_db()
    db.execute(
        '''
        INSERT INTO order_timeline (order_id, status, actor_type, actor_name, note)
        VALUES (?, ?, ?, ?, ?)
        ''',
        (order_id, status, actor_type, actor_name, note),
    )
    db.commit()


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
    existing_food_rows = db.execute("SELECT name FROM foods").fetchall()
    existing_names = {row["name"] for row in existing_food_rows}

    for food in FOOD_CATALOG:
        if food[0] not in existing_names:
            db.execute("INSERT INTO foods (name, category, price, image, description) VALUES (?, ?, ?, ?, ?)", food)
    db.commit()


def fix_food_images(db):
    for name, _, _, image, _ in FOOD_CATALOG:
        db.execute("UPDATE foods SET image = ? WHERE name = ? AND image != ?", (image, name, image))
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


def user_required(func):
    return role_required("customer")(func)


def login_required(func):
    return user_required(func)


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
    return role_required("admin")(func)


def manager_required(func):
    return role_required("manager")(func)


def staff_order_required(func):
    return role_required("admin", "manager")(func)


def delivery_required(func):
    return role_required("delivery_partner")(func)


def customer_required(func):
    return user_required(func)


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


def normalize_mobile(mobile_number):
    digits = re.sub(r"\D", "", mobile_number or "")
    if len(digits) == 10:
        return digits
    if len(digits) == 12 and digits.startswith("91"):
        return digits[-10:]
    return None


def lookup_staff_by_email_or_mobile(identifier, role):
    if not staff_role_is_valid(role):
        return None
    identifier = (identifier or "").strip()
    if not identifier:
        return None
    mobile = normalize_mobile(identifier)
    if mobile:
        return query_db(
            "SELECT id, name, email, role, password, mobile_number FROM staff_users WHERE mobile_number = ? AND role = ? AND is_active = 1",
            (mobile, role),
            one=True,
        )
    return query_db(
        "SELECT id, name, email, role, password, mobile_number FROM staff_users WHERE LOWER(email) = ? AND role = ? AND is_active = 1",
        (identifier.lower(), role),
        one=True,
    )


def generate_mobile_shadow_email(mobile_number):
    base_email = f"mobile_{mobile_number}@foodflux.local"
    existing = query_db("SELECT id FROM users WHERE LOWER(email) = ?", (base_email.lower(),), one=True)
    if not existing:
        return base_email
    return f"mobile_{mobile_number}_{int(datetime.now().timestamp())}@foodflux.local"


def staff_role_is_valid(role):
    return role in {"admin", "manager", "delivery_partner"}


def set_staff_session(staff):
    session["staff_id"] = staff["id"]
    session["staff_name"] = staff["name"]
    session["staff_email"] = staff["email"]
    session["staff_role"] = staff["role"]
    session["account_role"] = staff["role"]


def login_staff_by_mobile(mobile_number, password, role):
    if not staff_role_is_valid(role):
        return None, (jsonify({"ok": False, "error": "Select a valid staff role."}), 400)

    staff = query_db(
        "SELECT id, name, email, role, password, mobile_number, mobile_verified FROM staff_users WHERE mobile_number = ? AND role = ? AND is_active = 1",
        (mobile_number, role),
        one=True,
    )
    if not staff:
        return None, (jsonify({"ok": False, "error": "Staff mobile number is not registered."}), 404)
    if not check_password_hash(staff["password"], password):
        return None, (jsonify({"ok": False, "error": "Invalid mobile number or password."}), 401)
    return staff, None


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


def ensure_db_ready():
    global DB_INIT_DONE
    if DB_INIT_DONE:
        return
    with DB_INIT_LOCK:
        if DB_INIT_DONE:
            return
        init_db()
        DB_INIT_DONE = True


@app.before_request
def bootstrap_database_if_needed():
    if request.endpoint in ("health", "healthz", "static"):
        return
    ensure_db_ready()


@app.context_processor
def inject_cart_count():
    cart = session.get("cart", {})
    count = sum(cart.values()) if cart else 0
    unread_count = get_unread_notification_count()
    return {"cart_count": count, "unread_notification_count": unread_count}


def get_unread_notification_count():
    role = session.get("account_role")
    if role == "customer" and session.get("user_id"):
        row = query_db(
            "SELECT COUNT(*) AS c FROM notifications WHERE target_type = 'customer' AND target_id = ? AND is_read = 0",
            (str(session.get("user_id")),),
            one=True,
        )
        return row["c"] if row else 0
    if role in ("admin", "manager"):
        row = query_db(
            "SELECT COUNT(*) AS c FROM notifications WHERE target_type = 'manager' AND target_id = 'global' AND is_read = 0",
            one=True,
        )
        return row["c"] if row else 0
    if role == "delivery_partner" and session.get("staff_name"):
        row = query_db(
            "SELECT COUNT(*) AS c FROM notifications WHERE target_type = 'delivery_partner' AND target_id = ? AND is_read = 0",
            (session.get("staff_name"),),
            one=True,
        )
        return row["c"] if row else 0
    return 0


@app.route("/")
def home():
    search = request.args.get("q", "")
    cache_key = f"home:{search.strip().lower()}"
    cached = cache_get(cache_key)
    if cached is not None:
        return render_template("home.html", foods=cached, search=search)
    if search:
        foods = query_db(
            '''
            SELECT
                f.*,
                COALESCE(AVG(r.rating), 0) AS avg_rating,
                COUNT(r.id) AS rating_count
            FROM foods f
            LEFT JOIN ratings r ON r.food_id = f.id
            WHERE (f.name LIKE ? OR f.description LIKE ?)
              AND COALESCE(f.is_deleted, 0) = 0
              AND COALESCE(f.is_available, 1) = 1
              AND COALESCE(f.stock_qty, 0) > 0
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
                        WHERE COALESCE(f.is_deleted, 0) = 0
                            AND COALESCE(f.is_available, 1) = 1
                            AND COALESCE(f.stock_qty, 0) > 0
            GROUP BY f.id
            ORDER BY f.id DESC
            LIMIT 8
            '''
        )
        cache_set(cache_key, foods)
    return render_template("home.html", foods=foods, search=search)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password")

        if not name or not email or not password:
            flash("All fields are required.", "danger")
            return redirect(url_for("register"))

        existing = query_db("SELECT id FROM users WHERE LOWER(email) = ?", (email,), one=True)
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


@app.route("/api/auth/mobile/login", methods=["POST"])
def mobile_login():
    payload = request.get_json(silent=True) or request.form
    mobile_number = normalize_mobile(payload.get("mobile_number"))
    password = (payload.get("password") or "").strip()
    next_url = payload.get("next")

    if not mobile_number or not password:
        return jsonify({"ok": False, "error": "Mobile number and password are required."}), 400

    user = query_db(
        "SELECT id, name, email, mobile_number, password FROM users WHERE mobile_number = ?",
        (mobile_number,),
        one=True,
    )
    if not user or not check_password_hash(user["password"], password):
        return jsonify({"ok": False, "error": "Invalid mobile number or password."}), 401

    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    session["user_email"] = user["email"]
    session["account_role"] = "customer"
    return jsonify({"ok": True, "message": "Login successful.", "redirect": safe_next_url(next_url, "user_dashboard")})


@app.route("/api/auth/staff/mobile/login", methods=["POST"])
def staff_mobile_login():
    payload = request.get_json(silent=True) or request.form
    mobile_number = normalize_mobile(payload.get("mobile_number"))
    password = (payload.get("password") or "").strip()
    role = (payload.get("role") or "").strip().lower()

    if not mobile_number or not password:
        return jsonify({"ok": False, "error": "Mobile number and password are required."}), 400

    staff, error_response = login_staff_by_mobile(mobile_number, password, role)
    if error_response:
        return error_response

    set_staff_session(staff)
    return jsonify({
        "ok": True,
        "message": "Login successful.",
        "redirect": url_for("admin_dashboard") if staff["role"] == "admin" else (url_for("manager_dashboard") if staff["role"] == "manager" else url_for("delivery_dashboard")),
    })


@app.route("/api/admin/staff/onboard", methods=["POST"])
@admin_required
def admin_onboard_staff():
    payload = request.get_json(silent=True) or request.form
    name = (payload.get("name") or payload.get("full_name") or "").strip()
    mobile_number = normalize_mobile(payload.get("mobile_number"))
    password = (payload.get("password") or "").strip()
    role = (payload.get("role") or "").strip().lower()

    if not staff_role_is_valid(role):
        return jsonify({"ok": False, "error": "Select a valid staff role."}), 400
    if not name or len(name) < 2:
        return jsonify({"ok": False, "error": "Staff name is required."}), 400
    if not mobile_number:
        return jsonify({"ok": False, "error": "Valid mobile number is required."}), 400
    if len(password) < 6:
        return jsonify({"ok": False, "error": "Password must be at least 6 characters."}), 400

    existing_staff = query_db("SELECT id FROM staff_users WHERE mobile_number = ?", (mobile_number,), one=True)
    existing_customer = query_db("SELECT id FROM users WHERE mobile_number = ?", (mobile_number,), one=True)
    if existing_staff or existing_customer:
        return jsonify({"ok": False, "error": "Mobile number is already in use."}), 409

    db = get_db()
    db.execute(
        "INSERT INTO staff_users (name, email, mobile_number, mobile_verified, password, role, is_active) VALUES (?, ?, ?, 1, ?, ?, 1)",
        (
            name,
            f"staff_{mobile_number}@foodflux.local",
            mobile_number,
            generate_password_hash(password),
            role,
        ),
    )
    db.commit()
    return jsonify({"ok": True, "message": "Staff account created successfully."})


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("account_role") in ("customer", "user") and session.get("user_id"):
        return redirect(url_for("user_dashboard"))
    if session.get("account_role") == "manager" and session.get("staff_id"):
        return redirect(url_for("manager_dashboard"))
    if session.get("account_role") == "admin" and session.get("staff_id"):
        return redirect(url_for("admin_dashboard"))
    if session.get("account_role") == "delivery_partner" and session.get("staff_id"):
        return redirect(url_for("delivery_dashboard"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        next_url = request.form.get("next") or request.args.get("next")

        if not email or not password:
            flash("Email and password are required.", "danger")
            return redirect(url_for("login"))

        user = query_db("SELECT id, name, email, password FROM users WHERE LOWER(email) = ?", (email,), one=True)
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["user_email"] = user["email"]
            session["account_role"] = "customer"
            flash(f"Welcome, {user['name']}!", "success")
            return redirect(safe_next_url(next_url, "user_dashboard"))

        flash("Invalid email or password.", "danger")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if session.get("account_role") == "admin" and session.get("staff_id"):
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        mobile_number = normalize_mobile(request.form.get("mobile_number") or "")
        password = request.form.get("password") or ""

        if not mobile_number or not password:
            flash("Mobile number and password are required.", "danger")
            return redirect(url_for("admin_login"))

        # Authenticate admin using mobile number + password
        staff = query_db(
            "SELECT id, name, email, role, password, mobile_number FROM staff_users WHERE mobile_number = ? AND role = 'admin' AND is_active = 1",
            (mobile_number,),
            one=True,
        )
        if staff and check_password_hash(staff["password"], password):
            session["staff_id"] = staff["id"]
            session["staff_name"] = staff["name"]
            session["staff_email"] = staff["email"]
            session["staff_mobile"] = staff["mobile_number"]
            session["staff_role"] = staff["role"]
            session["account_role"] = "admin"
            flash(f"Welcome, {staff['name']}!", "success")
            return redirect(url_for("admin_dashboard"))

        flash("Invalid admin credentials.", "danger")
        return redirect(url_for("admin_login"))

    admin_notice = None
    if not ADMIN_MOBILE or not ADMIN_PASSWORD:
        admin_notice = "No admin credentials are configured. For local development, use mobile 9000000000 and password admin@123."
    return render_template("admin_login.html", admin_notice=admin_notice)


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
    realtime_token = build_live_token(
        {
            "summary": {
                "total": order_summary["total_orders"] or 0,
                "active": order_summary["active_orders"] or 0,
                "delivered": order_summary["delivered_orders"] or 0,
            },
            "orders": [
                {
                    "id": row["id"],
                    "status": row["status"],
                    "delivery_person": row["delivery_person"] or "",
                }
                for row in recent_orders
            ],
        }
    )
    return render_template(
        "customer_dashboard.html",
        recent_orders=recent_orders,
        order_summary=order_summary,
        realtime_token=realtime_token,
    )


@app.route("/user/dashboard")
@user_required
def user_dashboard():
    return customer_dashboard()


@app.route("/user")
def user_home_redirect():
    return redirect(url_for("user_dashboard"))


@app.route("/logout")
def logout():
    session_keys = [
        "user_id",
        "user_name",
        "user_email",
        "cart",
        "account_role",
        "staff_id",
        "staff_name",
        "staff_email",
        "staff_role",
    ]
    for key in session_keys:
        session.pop(key, None)
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


@app.route("/manager/login", methods=["GET", "POST"])
def manager_login():
    if session.get("account_role") == "manager" and session.get("staff_id"):
        return redirect(url_for("manager_dashboard"))

    if request.method == "POST":
        identifier = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""

        if not identifier or not password:
            flash("Email or mobile plus password are required.", "danger")
            return redirect(url_for("manager_login"))

        staff = lookup_staff_by_email_or_mobile(identifier, "manager")
        if staff and check_password_hash(staff["password"], password):
            set_staff_session(staff)
            flash(f"Welcome, {staff['name']}!", "success")
            return redirect(url_for("manager_dashboard"))

        flash("Invalid manager credentials.", "danger")
        return redirect(url_for("manager_login"))

    return render_template("manager_login.html", manager_hint=f"{MANAGER_EMAIL} / {MANAGER_MOBILE}")


@app.route("/manager")
def manager_route():
    return redirect(url_for("manager_login"))


@app.route("/delivery/login", methods=["GET", "POST"])
def delivery_login():
    if session.get("account_role") == "delivery_partner" and session.get("staff_id"):
        return redirect(url_for("delivery_dashboard"))

    if request.method == "POST":
        identifier = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""

        if not identifier or not password:
            flash("Email or mobile plus password are required.", "danger")
            return redirect(url_for("delivery_login"))

        staff = lookup_staff_by_email_or_mobile(identifier, "delivery_partner")
        if staff and check_password_hash(staff["password"], password):
            set_staff_session(staff)
            flash(f"Welcome, {staff['name']}!", "success")
            return redirect(url_for("delivery_dashboard"))

        flash("Invalid delivery partner credentials.", "danger")
        return redirect(url_for("delivery_login"))

    return render_template("delivery_login.html", delivery_hint="Your registered email or mobile number")


@app.route("/menu")
def menu():
    category = request.args.get("category")
    search = request.args.get("q", "")
    cache_key = f"menu:{(category or '').strip().lower()}:{search.strip().lower()}"
    cached = cache_get(cache_key)
    if cached is not None:
        return render_template("menu.html", foods=cached, category=category, search=search)
    query = """
    SELECT
        f.*,
        COALESCE(AVG(r.rating), 0) AS avg_rating,
        COUNT(r.id) AS rating_count
    FROM foods f
    LEFT JOIN ratings r ON r.food_id = f.id
    """
    args = []
    filters = ["COALESCE(f.is_deleted, 0) = 0", "COALESCE(f.is_available, 1) = 1", "COALESCE(f.stock_qty, 0) > 0"]
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
    cache_set(cache_key, foods)
    return render_template("menu.html", foods=foods, category=category, search=search)


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"}), 200


@app.route("/health")
def health():
    return "OK", 200


@app.route("/add_to_cart/<int:food_id>")
def add_to_cart(food_id):
    cart = session.get("cart", {})
    cart[str(food_id)] = cart.get(str(food_id), 0) + 1
    session["cart"] = cart
    session.modified = True
    if wants_json_response():
        return jsonify({"ok": True, "message": "Food item added to cart.", **get_cart_state_payload()})
    flash("Food item added to cart.", "success")
    return redirect(request.referrer or url_for("menu"))


@app.route("/remove_from_cart/<int:food_id>")
def remove_from_cart(food_id):
    cart = session.get("cart", {})
    cart.pop(str(food_id), None)
    session["cart"] = cart
    session.modified = True
    if wants_json_response():
        return jsonify({"ok": True, "message": "Item removed from cart.", **get_cart_state_payload()})
    flash("Item removed from cart.", "info")
    return redirect(url_for("cart"))


@app.route("/api/cart/state")
def cart_state():
    return jsonify({"ok": True, **get_cart_state_payload()})


@app.route("/api/cart/update", methods=["POST"])
def update_cart_item_api():
    payload = request.get_json(silent=True) or request.form
    food_id = str(payload.get("food_id") or "").strip()
    try:
        quantity = int(payload.get("quantity"))
    except (TypeError, ValueError):
        quantity = 1

    if not food_id.isdigit():
        return jsonify({"ok": False, "error": "Invalid food item."}), 400

    cart = session.get("cart", {})
    if quantity < 1:
        cart.pop(food_id, None)
    else:
        cart[food_id] = min(quantity, 99)
    session["cart"] = cart
    session.modified = True
    return jsonify({"ok": True, **get_cart_state_payload()})


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

    items, total = get_cart_items_from_session()
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
        available_qty = int(food["stock_qty"] if "stock_qty" in food.keys() and food["stock_qty"] is not None else 25)
        is_available = int(food["is_available"] if "is_available" in food.keys() and food["is_available"] is not None else 1)
        is_deleted = int(food["is_deleted"] if "is_deleted" in food.keys() and food["is_deleted"] is not None else 0)
        if is_deleted or not is_available or available_qty < qty:
            flash(f"'{food['name']}' is out of stock or unavailable. Please update your cart.", "warning")
            return redirect(url_for("cart"))
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
            db.execute(
                "UPDATE foods SET stock_qty = CASE WHEN stock_qty - ? < 0 THEN 0 ELSE stock_qty - ? END WHERE id = ?",
                (item["qty"], item["qty"], item["food"]["id"]),
            )
            db.execute(
                "UPDATE foods SET is_available = 0 WHERE id = ? AND stock_qty <= 0",
                (item["food"]["id"],),
            )
        db.commit()

        log_order_timeline(order_id, "Order Placed", "customer", session.get("user_name"), "Order created from checkout")
        create_order_notifications(order_id, "Order Placed")
        emit_order_event(order_id, "order_created")
        if assigned_delivery_person and assigned_delivery_person != "Not Assigned":
            emit_order_event(order_id, "rider_assigned")
        invalidate_cache("home:")
        invalidate_cache("menu:")

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


def get_cart_items_from_session():
    cart = session.get("cart", {})
    items = []
    total = 0.0

    if not cart:
        return items, total

    food_ids = tuple(int(fid) for fid in cart.keys())
    placeholder = ",".join("?" for _ in food_ids)
    foods = query_db(f"SELECT * FROM foods WHERE id IN ({placeholder})", food_ids)
    for food in foods:
        qty = int(cart.get(str(food["id"]), 0))
        if qty < 1:
            continue
        subtotal = float(food["price"] or 0) * qty
        total += subtotal
        items.append({"food": food, "qty": qty, "subtotal": subtotal})

    return items, total


def get_cart_state_payload():
    items, total = get_cart_items_from_session()
    return {
        "count": sum(item["qty"] for item in items),
        "total": round(total, 2),
        "items": [
            {
                "food_id": item["food"]["id"],
                "name": item["food"]["name"],
                "price": float(item["food"]["price"] or 0),
                "qty": item["qty"],
                "subtotal": round(item["subtotal"], 2),
                "image": item["food"]["image"],
            }
            for item in items
        ],
    }


def wants_json_response():
    return request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.accept_mimetypes.best == "application/json"


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
    service_ratings = query_db(
        '''
        SELECT target_type, target_name, rating, review
        FROM service_ratings
        WHERE user_id = ? AND order_id = ?
        ''',
        (session["user_id"], order_id),
    )
    service_rating_map = {row["target_type"]: row for row in service_ratings}
    timeline_entries = query_db(
        '''
        SELECT status, actor_type, actor_name, note, created_at
        FROM order_timeline
        WHERE order_id = ?
        ORDER BY created_at ASC
        ''',
        (order_id,),
    )

    return render_template(
        "track_order.html",
        order=order,
        order_items=order_items,
        service_rating_map=service_rating_map,
        timeline_entries=timeline_entries,
    )


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


@app.route("/rate_service/<int:order_id>", methods=["POST"])
@login_required
def rate_service(order_id):
    order = query_db(
        "SELECT id, status, delivery_person FROM orders WHERE id = ? AND user_id = ?",
        (order_id, session["user_id"]),
        one=True,
    )
    if not order or order["status"] != "Delivered":
        flash("You can rate service only after delivery is completed.", "warning")
        return redirect(url_for("track_order", order_id=order_id))

    restaurant_rating_raw = request.form.get("restaurant_rating")
    delivery_rating_raw = request.form.get("delivery_rating")
    restaurant_review = (request.form.get("restaurant_review") or "").strip()
    delivery_review = (request.form.get("delivery_review") or "").strip()

    try:
        restaurant_rating = int(restaurant_rating_raw)
        delivery_rating = int(delivery_rating_raw)
    except (TypeError, ValueError):
        flash("Please select valid ratings between 1 and 5.", "danger")
        return redirect(url_for("track_order", order_id=order_id))

    if restaurant_rating not in (1, 2, 3, 4, 5) or delivery_rating not in (1, 2, 3, 4, 5):
        flash("Ratings must be between 1 and 5.", "danger")
        return redirect(url_for("track_order", order_id=order_id))

    db = get_db()
    db.execute(
        '''
        INSERT INTO service_ratings (user_id, order_id, target_type, target_name, rating, review, updated_at)
        VALUES (?, ?, 'restaurant', 'FoodFlux Restaurant', ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id, order_id, target_type)
        DO UPDATE SET
            rating = excluded.rating,
            review = excluded.review,
            updated_at = CURRENT_TIMESTAMP
        ''',
        (session["user_id"], order_id, restaurant_rating, restaurant_review),
    )
    db.execute(
        '''
        INSERT INTO service_ratings (user_id, order_id, target_type, target_name, rating, review, updated_at)
        VALUES (?, ?, 'delivery_partner', ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id, order_id, target_type)
        DO UPDATE SET
            target_name = excluded.target_name,
            rating = excluded.rating,
            review = excluded.review,
            updated_at = CURRENT_TIMESTAMP
        ''',
        (
            session["user_id"],
            order_id,
            order["delivery_person"] or "Delivery Partner",
            delivery_rating,
            delivery_review,
        ),
    )
    db.commit()
    flash("Thanks! Service ratings saved.", "success")
    return redirect(url_for("track_order", order_id=order_id))


@app.route("/admin_logout")
def admin_logout():
    return redirect(url_for("logout"))


@app.route("/admin/users")
@admin_required
def admin_users():
    customers = query_db(
        "SELECT id, name, email, mobile_number, mobile_verified FROM users ORDER BY id DESC"
    )
    staff_members = query_db(
        "SELECT id, name, email, mobile_number, mobile_verified, role, is_active, created_at FROM staff_users ORDER BY id DESC"
    )
    return render_template("admin_users.html", customers=customers, staff_members=staff_members)


@app.route("/admin/users/staff/<int:staff_id>/toggle", methods=["POST"])
@admin_required
def toggle_staff_status(staff_id):
    db = get_db()
    row = db.execute("SELECT id, is_active, name FROM staff_users WHERE id = ?", (staff_id,)).fetchone()
    if not row:
        flash("Staff account not found.", "warning")
        return redirect(url_for("admin_users"))
    next_state = 0 if int(row["is_active"] or 0) == 1 else 1
    db.execute("UPDATE staff_users SET is_active = ? WHERE id = ?", (next_state, staff_id))
    db.commit()
    flash(f"Staff account '{row['name']}' {'activated' if next_state == 1 else 'deactivated'}.", "success")
    return redirect(url_for("admin_users"))


@app.route("/notifications")
def notifications_center():
    role = session.get("account_role")
    if role == "customer" and session.get("user_id"):
        notifications = query_db(
            "SELECT * FROM notifications WHERE target_type = 'customer' AND target_id = ? ORDER BY created_at DESC LIMIT 100",
            (str(session.get("user_id")),),
        )
    elif role in ("admin", "manager"):
        notifications = query_db(
            "SELECT * FROM notifications WHERE target_type = 'manager' AND target_id = 'global' ORDER BY created_at DESC LIMIT 100"
        )
    elif role == "delivery_partner" and session.get("staff_name"):
        notifications = query_db(
            "SELECT * FROM notifications WHERE target_type = 'delivery_partner' AND target_id = ? ORDER BY created_at DESC LIMIT 100",
            (session.get("staff_name"),),
        )
    else:
        flash("Please login to view notifications.", "warning")
        return redirect(url_for("login"))

    return render_template("notifications.html", notifications=notifications)


@app.route("/api/notifications")
def notifications_api():
    role = session.get("account_role")
    if role == "customer" and session.get("user_id"):
        notifications = query_db(
            "SELECT * FROM notifications WHERE target_type = 'customer' AND target_id = ? ORDER BY created_at DESC LIMIT 50",
            (str(session.get("user_id")),),
        )
    elif role in ("admin", "manager"):
        notifications = query_db(
            "SELECT * FROM notifications WHERE target_type = 'manager' AND target_id = 'global' ORDER BY created_at DESC LIMIT 50"
        )
    elif role == "delivery_partner" and session.get("staff_name"):
        notifications = query_db(
            "SELECT * FROM notifications WHERE target_type = 'delivery_partner' AND target_id = ? ORDER BY created_at DESC LIMIT 50",
            (session.get("staff_name"),),
        )
    else:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401

    return jsonify(
        {
            "ok": True,
            "items": [
                {
                    "id": row["id"],
                    "title": row["title"],
                    "message": row["message"],
                    "category": row["category"],
                    "is_read": row["is_read"],
                    "created_at": row["created_at"],
                }
                for row in notifications
            ],
        }
    )


@app.route("/api/notifications/mark-read", methods=["POST"])
def notifications_mark_read_api():
    role = session.get("account_role")
    db = get_db()
    if role == "customer" and session.get("user_id"):
        db.execute(
            "UPDATE notifications SET is_read = 1 WHERE target_type = 'customer' AND target_id = ?",
            (str(session.get("user_id")),),
        )
    elif role in ("admin", "manager"):
        db.execute("UPDATE notifications SET is_read = 1 WHERE target_type = 'manager' AND target_id = 'global'")
    elif role == "delivery_partner" and session.get("staff_name"):
        db.execute(
            "UPDATE notifications SET is_read = 1 WHERE target_type = 'delivery_partner' AND target_id = ?",
            (session.get("staff_name"),),
        )
    else:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401
    db.commit()
    return jsonify({"ok": True})


@app.route("/admin")
@app.route("/admin/dashboard")
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
    realtime_token = build_live_token(
        {
            "stats": {
                "total": order_stats["total_orders"] or 0,
                "active": order_stats["active_orders"] or 0,
                "delivered": order_stats["delivered_orders"] or 0,
            },
            "panel": [
                {
                    "delivery_person": row["delivery_person"],
                    "latest_status": row["latest_status"],
                    "active_orders": row["active_orders"] or 0,
                    "delivered_orders": row["delivered_orders"] or 0,
                    "assigned_orders": row["assigned_orders"] or 0,
                }
                for row in delivery_panel
            ],
        }
    )
    return render_template(
        "admin_dashboard.html",
        foods=foods,
        order_stats=order_stats,
        delivery_panel=delivery_panel,
        realtime_token=realtime_token,
    )


@app.route("/manager/dashboard")
@manager_required
def manager_dashboard():
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
    realtime_token = build_live_token(
        {
            "stats": {
                "total": order_stats["total_orders"] or 0,
                "active": order_stats["active_orders"] or 0,
                "delivered": order_stats["delivered_orders"] or 0,
            },
            "panel": [
                {
                    "delivery_person": row["delivery_person"],
                    "latest_status": row["latest_status"],
                    "active_orders": row["active_orders"] or 0,
                    "delivered_orders": row["delivered_orders"] or 0,
                    "assigned_orders": row["assigned_orders"] or 0,
                }
                for row in delivery_panel
            ],
        }
    )
    return render_template(
        "manager_dashboard.html",
        foods=foods,
        order_stats=order_stats,
        delivery_panel=delivery_panel,
        realtime_token=realtime_token,
    )


@app.route("/admin/orders")
@app.route("/manager/orders")
@staff_order_required
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
    realtime_token = build_live_token(
        [
            {
                "id": row["id"],
                "status": row["status"],
                "delivery_person": row["delivery_person"] or "",
            }
            for row in orders
        ]
    )
    return render_template("admin_orders.html", orders=orders, realtime_token=realtime_token)


@app.route("/admin/foods", methods=["GET", "POST"])
@app.route("/manager/foods", methods=["GET", "POST"])
@admin_required
def admin_foods():
    if request.method == "POST":
        name = request.form.get("name")
        category = request.form.get("category")
        price = request.form.get("price")
        stock_qty_raw = request.form.get("stock_qty", "25")
        is_available = 1 if request.form.get("is_available") == "on" else 0
        image_file = request.files.get("image_file")
        description = request.form.get("description")

        if not name or not category or not price or not description:
            flash("All fields are required.", "danger")
            return redirect(url_for("admin_foods"))

        try:
            price = float(price)
            stock_qty = max(0, int(stock_qty_raw))
        except ValueError:
            flash("Invalid price or stock quantity.", "danger")
            return redirect(url_for("admin_foods"))

        image, upload_error = save_uploaded_food_image(image_file)
        if upload_error:
            flash(upload_error, "danger")
            return redirect(url_for("admin_foods"))

        db = get_db()
        db.execute(
            "INSERT INTO foods (name, category, price, image, description, stock_qty, is_available, is_deleted) VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
            (name, category, price, image, description, stock_qty, is_available)
        )
        db.commit()
        invalidate_cache("home:")
        invalidate_cache("menu:")
        flash("Food item added successfully.", "success")
        return redirect(url_for("admin_foods"))

    foods = query_db("SELECT * FROM foods ORDER BY is_deleted ASC, id DESC")
    return render_template("admin_food_form.html", foods=foods)


@app.route("/admin/foods/edit/<int:food_id>", methods=["POST"])
@app.route("/manager/foods/edit/<int:food_id>", methods=["POST"])
@admin_required
def edit_food(food_id):
    name = request.form.get("name")
    category = request.form.get("category")
    price = request.form.get("price")
    stock_qty_raw = request.form.get("stock_qty", "0")
    is_available = 1 if request.form.get("is_available") == "on" else 0
    description = request.form.get("description")
    image_file = request.files.get("image_file")

    if not name or not category or not price or not description:
        flash("All fields except image are required for update.", "danger")
        return redirect(url_for("admin_foods"))

    try:
        price = float(price)
        stock_qty = max(0, int(stock_qty_raw))
    except ValueError:
        flash("Invalid price or stock quantity.", "danger")
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
        "UPDATE foods SET name = ?, category = ?, price = ?, image = ?, description = ?, stock_qty = ?, is_available = ?, is_deleted = 0 WHERE id = ?",
        (name, category, price, updated_image, description, stock_qty, is_available, food_id),
    )
    db.commit()
    invalidate_cache("home:")
    invalidate_cache("menu:")
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
        db.execute("UPDATE foods SET is_deleted = 1, is_available = 0 WHERE id = ?", (food_id,))
        db.commit()
        invalidate_cache("home:")
        invalidate_cache("menu:")
        flash("Item has active order history, so it was archived (soft delete).", "warning")
        return redirect(url_for("admin_dashboard"))

    db.execute("DELETE FROM ratings WHERE food_id = ?", (food_id,))
    db.execute("DELETE FROM foods WHERE id = ?", (food_id,))
    db.commit()
    invalidate_cache("home:")
    invalidate_cache("menu:")

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
@staff_order_required
def update_order_status(order_id, status):
    db = get_db()
    order = db.execute("SELECT id, status FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order:
        flash("Order not found.", "warning")
        return redirect(url_for("admin_orders"))

    allowed_actions = manager_allowed_actions(order["status"])
    if status not in allowed_actions:
        flash(f"Invalid transition from '{order['status']}' to '{status}'.", "danger")
        return redirect(url_for("admin_orders"))

    db.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    db.commit()
    log_order_timeline(order_id, status, "manager", session.get("staff_name"), "Updated by manager")
    create_order_notifications(order_id, status)
    emit_order_event(order_id, status_to_live_event(status))
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
            u.email AS customer_email,
            CASE
                WHEN o.status IN ('Ready for Pickup', 'Rider Assigned', 'Picked Up', 'On the Way', 'Near Customer', 'Delivered')
                    THEN o.address
                ELSE 'Available after restaurant marks order Ready'
            END AS visible_address,
            CASE
                WHEN o.status IN ('Ready for Pickup', 'Rider Assigned', 'Picked Up', 'On the Way', 'Near Customer', 'Delivered')
                    THEN o.phone
                ELSE 'Hidden until order is Ready'
            END AS visible_phone
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
    realtime_token = build_live_token(
        {
            "stats": {
                "total": delivery_stats["total_assigned"] or 0,
                "accepted": delivery_stats["accepted_orders"] or 0,
                "active": delivery_stats["active_orders"] or 0,
                "delivered": delivery_stats["delivered_orders"] or 0,
            },
            "orders": [
                {
                    "id": row["id"],
                    "status": row["status"],
                    "delivery_accepted": row["delivery_accepted"] or 0,
                    "allowed_actions": delivery_allowed_actions(row["status"]),
                }
                for row in assigned_orders
            ],
        }
    )
    return render_template(
        "delivery_dashboard.html",
        assigned_orders=assigned_orders,
        delivery_stats=delivery_stats,
        realtime_token=realtime_token,
    )


@app.route("/delivery/order/status/<int:order_id>/<status>")
@delivery_required
def delivery_update_order_status(order_id, status):
    valid_statuses = ["Accept", "Reject", "Picked Up", "On the Way", "Near Customer", "Delivered"]
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

    allowed = delivery_allowed_actions(order["status"])
    if status not in allowed:
        flash(f"Invalid transition from '{order['status']}' using '{status}'.", "danger")
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
        event_name = status_to_live_event(status)

    db.commit()
    timeline_status = "Rider Assigned" if status == "Accept" else ("Ready for Pickup" if status == "Reject" else status)
    log_order_timeline(order_id, timeline_status, "delivery_partner", session.get("staff_name"), f"Delivery action: {status}")
    create_order_notifications(order_id, timeline_status)
    emit_order_event(order_id, event_name)
    flash(f"Delivery status updated to {status}.", "success")
    return redirect(url_for("delivery_dashboard"))


@app.route("/api/rider/location", methods=["POST"])
@delivery_required
def save_rider_location():
    try:
        payload = request.get_json(silent=True) or {}
        order_id = int(payload.get("order_id"))
        lat = float(payload.get("lat"))
        lng = float(payload.get("lng"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Invalid location payload."}), 400

    order = query_db(
        "SELECT id FROM orders WHERE id = ? AND delivery_person = ?",
        (order_id, session.get("staff_name")),
        one=True,
    )
    if not order:
        return jsonify({"ok": False, "error": "Order not assigned."}), 403

    db = get_db()
    db.execute(
        '''
        INSERT INTO rider_locations (order_id, lat, lng, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(order_id)
        DO UPDATE SET
            lat = excluded.lat,
            lng = excluded.lng,
            updated_at = CURRENT_TIMESTAMP
        ''',
        (order_id, lat, lng),
    )
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/live/customer/dashboard")
@customer_required
def live_customer_dashboard():
    cache_key = f"live:customer:{session.get('user_id')}"
    cached = cache_get(cache_key)
    if cached is not None:
        return jsonify({"token": cached})
    update_due_delivery_statuses()
    recent_orders = query_db(
        '''
        SELECT id, status, delivery_person, total, created_at
        FROM orders
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 6
        ''',
        (session["user_id"],),
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
    token = build_live_token(
        {
            "summary": {
                "total": order_summary["total_orders"] or 0,
                "active": order_summary["active_orders"] or 0,
                "delivered": order_summary["delivered_orders"] or 0,
            },
            "orders": [
                {
                    "id": row["id"],
                    "status": row["status"],
                    "delivery_person": row["delivery_person"] or "",
                    "total": float(row["total"] or 0),
                    "created_at": row["created_at"],
                }
                for row in recent_orders
            ],
        }
    )
    cache_set(cache_key, token, ttl_seconds=5)
    return jsonify(
        {
            "token": token,
            "kind": "customer_dashboard",
            "summary": {
                "total": order_summary["total_orders"] or 0,
                "active": order_summary["active_orders"] or 0,
                "delivered": order_summary["delivered_orders"] or 0,
            },
            "orders": [
                {
                    "id": row["id"],
                    "status": row["status"],
                    "delivery_person": row["delivery_person"] or "",
                    "total": float(row["total"] or 0),
                    "created_at": row["created_at"],
                }
                for row in recent_orders
            ],
        }
    )


@app.route("/api/live/user/dashboard")
@user_required
def live_user_dashboard():
    return live_customer_dashboard()


@app.route("/api/live/manager/dashboard")
@admin_required
def live_manager_dashboard():
    cache_key = "live:manager:dashboard"
    cached = cache_get(cache_key)
    if cached is not None:
        return jsonify({"token": cached})
    update_due_delivery_statuses()
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
    token = build_live_token(
        {
            "stats": {
                "total": order_stats["total_orders"] or 0,
                "active": order_stats["active_orders"] or 0,
                "delivered": order_stats["delivered_orders"] or 0,
            },
            "panel": [
                {
                    "delivery_person": row["delivery_person"],
                    "latest_status": row["latest_status"],
                    "active_orders": row["active_orders"] or 0,
                    "delivered_orders": row["delivered_orders"] or 0,
                    "assigned_orders": row["assigned_orders"] or 0,
                }
                for row in delivery_panel
            ],
        }
    )
    cache_set(cache_key, token, ttl_seconds=5)
    return jsonify(
        {
            "token": token,
            "kind": "manager_dashboard",
            "stats": {
                "total": order_stats["total_orders"] or 0,
                "active": order_stats["active_orders"] or 0,
                "delivered": order_stats["delivered_orders"] or 0,
            },
            "panel": [
                {
                    "delivery_person": row["delivery_person"],
                    "latest_status": row["latest_status"],
                    "active_orders": row["active_orders"] or 0,
                    "delivered_orders": row["delivered_orders"] or 0,
                    "assigned_orders": row["assigned_orders"] or 0,
                }
                for row in delivery_panel
            ],
        }
    )


@app.route("/api/live/manager/orders")
@admin_required
def live_manager_orders():
    cache_key = "live:manager:orders"
    cached = cache_get(cache_key)
    if cached is not None:
        return jsonify({"token": cached})
    update_due_delivery_statuses()
    orders = query_db(
        '''
        SELECT
            o.id,
            o.status,
            o.delivery_person,
            o.total,
            o.payment,
            o.address,
            o.phone,
            COALESCE(NULLIF(o.customer_name, ''), u.name, 'Guest') AS customer_name,
            u.email AS customer_email
        FROM orders o
        LEFT JOIN users u ON u.id = o.user_id
        WHERE o.status NOT IN ('Delivered', 'Cancelled', 'Rejected')
        ORDER BY created_at DESC
        '''
    )
    token = build_live_token(
        [
            {
                "id": row["id"],
                "status": row["status"],
                "delivery_person": row["delivery_person"] or "",
                "allowed_actions": manager_allowed_actions(row["status"]),
            }
            for row in orders
        ]
    )
    cache_set(cache_key, token, ttl_seconds=5)
    return jsonify(
        {
            "token": token,
            "kind": "manager_orders",
            "orders": [
                {
                    "id": row["id"],
                    "status": row["status"],
                    "delivery_person": row["delivery_person"] or "",
                    "total": float(row["total"] or 0),
                    "payment": row["payment"],
                    "address": row["address"],
                    "phone": row["phone"],
                    "customer_name": row["customer_name"],
                    "customer_email": row["customer_email"] or "",
                    "allowed_actions": manager_allowed_actions(row["status"]),
                }
                for row in orders
            ],
        }
    )


@app.route("/api/live/delivery/dashboard")
@delivery_required
def live_delivery_dashboard():
    cache_key = f"live:delivery:{session.get('staff_name')}"
    cached = cache_get(cache_key)
    if cached is not None:
        return jsonify({"token": cached})
    update_due_delivery_statuses()
    assigned_orders = query_db(
        '''
        SELECT
            o.id,
            o.status,
            o.delivery_accepted,
            o.address,
            o.phone,
            u.name AS customer_name,
            u.email AS customer_email
        FROM orders o
        LEFT JOIN users u ON u.id = o.user_id
        WHERE o.delivery_person = ?
        ORDER BY created_at DESC
        ''',
        (session.get("staff_name"),),
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
    token = build_live_token(
        {
            "stats": {
                "total": delivery_stats["total_assigned"] or 0,
                "accepted": delivery_stats["accepted_orders"] or 0,
                "active": delivery_stats["active_orders"] or 0,
                "delivered": delivery_stats["delivered_orders"] or 0,
            },
            "orders": [
                {
                    "id": row["id"],
                    "status": row["status"],
                    "delivery_accepted": row["delivery_accepted"] or 0,
                    "allowed_actions": delivery_allowed_actions(row["status"]),
                }
                for row in assigned_orders
            ],
        }
    )
    cache_set(cache_key, token, ttl_seconds=5)
    orders_payload = [
        {
            "id": row["id"],
            "status": row["status"],
            "delivery_accepted": row["delivery_accepted"] or 0,
            "customer_name": row["customer_name"] or "Customer",
            "customer_email": row["customer_email"] or "",
            "address": row["address"] if customer_details_visible_for_delivery(row["status"]) else "Available after restaurant marks order Ready",
            "phone": row["phone"] if customer_details_visible_for_delivery(row["status"]) else "Hidden until order is Ready",
            "allowed_actions": delivery_allowed_actions(row["status"]),
        }
        for row in assigned_orders
    ]
    return jsonify(
        {
            "token": token,
            "kind": "delivery_dashboard",
            "stats": {
                "total": delivery_stats["total_assigned"] or 0,
                "accepted": delivery_stats["accepted_orders"] or 0,
                "active": delivery_stats["active_orders"] or 0,
                "delivered": delivery_stats["delivered_orders"] or 0,
            },
            "orders": orders_payload,
        }
    )


@app.route("/api/live/order/<int:order_id>")
@login_required
def live_order(order_id):
    cache_key = f"live:order:{session.get('user_id')}:{order_id}"
    cached = cache_get(cache_key)
    if cached is not None:
        return jsonify(cached)
    update_due_delivery_statuses()
    order = query_db(
        '''
        SELECT id, status, delivery_person, phone, address, estimated_delivery_time, auto_delivered_at
        FROM orders
        WHERE id = ? AND user_id = ?
        ''',
        (order_id, session["user_id"]),
        one=True,
    )
    if not order:
        return jsonify({"error": "Order not found"}), 404

    rider_location = query_db(
        "SELECT lat, lng, updated_at FROM rider_locations WHERE order_id = ?",
        (order_id,),
        one=True,
    )
    payload = {
        "id": order["id"],
        "status": order["status"],
        "delivery_person": order["delivery_person"],
        "phone": order["phone"],
        "address": order["address"],
        "estimated_delivery_time": order["estimated_delivery_time"],
        "auto_delivered_at": order["auto_delivered_at"],
        "rider_location": {
            "lat": rider_location["lat"],
            "lng": rider_location["lng"],
            "updated_at": rider_location["updated_at"],
        }
        if rider_location
        else None,
    }
    cache_set(cache_key, payload, ttl_seconds=4)
    return jsonify(payload)


@app.route("/api/order/check/<int:order_id>")
def check_order_status(order_id):
    update_due_delivery_statuses()
    order = query_db("SELECT * FROM orders WHERE id = ?", (order_id,), one=True)
    if order:
        return jsonify(
            {
                "status": order["status"],
                "id": order["id"],
                "delivery_person": order["delivery_person"],
                "estimated_delivery_time": order["estimated_delivery_time"],
            }
        )
    return jsonify({"status": "not_found", "id": order_id}), 404


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
