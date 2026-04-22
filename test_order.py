import sqlite3
from datetime import datetime, timedelta

# Simulate the discount calculation
def calculate_discount(total):
    discount_amount = 0.0
    discount_percentage = 0.0
    if total > 300:
        discount_percentage = 20
        discount_amount = total * (discount_percentage / 100)
    return discount_amount, discount_percentage

def calculate_estimated_delivery():
    current_time = datetime.now()
    delivery_time = current_time + timedelta(minutes=35)
    return delivery_time

# Test discount scenarios
print("Testing discount scenarios:")
test_totals = [250, 300, 350, 400, 500]
for total in test_totals:
    discount_amount, discount_percentage = calculate_discount(total)
    final_total = total - discount_amount
    print(f"Total: ₹{total} → Discount: ₹{discount_amount} ({discount_percentage}%) → Final: ₹{final_total}")

print()
print("Testing delivery time:")
print(f"Estimated delivery: {calculate_estimated_delivery()}")

# Test database insertion simulation
print()
print("Testing order creation simulation:")
conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# Create a test user first
cursor.execute('INSERT OR IGNORE INTO users (name, email, password) VALUES (?, ?, ?)',
               ('Test User', 'test@example.com', 'hashedpass'))
user_id = cursor.lastrowid
if user_id == 0:
    cursor.execute('SELECT id FROM users WHERE email = ?', ('test@example.com',))
    user_id = cursor.fetchone()[0]

# Simulate order placement
total = 400  # Should get 20% discount
discount_amount, discount_percentage = calculate_discount(total)
final_total = total - discount_amount
estimated_delivery = calculate_estimated_delivery()

cursor.execute('''
    INSERT INTO orders (user_id, total, original_total, discount, discount_percentage, address, phone, payment, status, estimated_delivery_time)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
''', (user_id, final_total, total, discount_amount, discount_percentage,
      'Test Address', '1234567890', 'UPI', 'Preparing', estimated_delivery.strftime("%Y-%m-%d %H:%M:%S")))

order_id = cursor.lastrowid

# Add some order items
cursor.execute('SELECT id, price FROM foods LIMIT 2')
foods = cursor.fetchall()
for food in foods:
    cursor.execute('INSERT INTO order_items (order_id, food_id, qty) VALUES (?, ?, ?)',
                   (order_id, food[0], 2))

conn.commit()

# Verify the order
cursor.execute('SELECT * FROM orders WHERE id = ?', (order_id,))
order = cursor.fetchone()
print(f"Created order ID: {order[0]}")
print(f"Original total: ₹{order[3]}")
print(f"Discount: ₹{order[4]} ({order[5]}%)")
print(f"Final total: ₹{order[2]}")
print(f"Status: {order[9]}")
print(f"Estimated delivery: {order[10]}")

conn.close()