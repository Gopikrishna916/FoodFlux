import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()
cursor.execute('SELECT name FROM sqlite_master WHERE type="table"')
tables = [row[0] for row in cursor.fetchall()]
print('Tables:', tables)

# Check orders table schema
cursor.execute('PRAGMA table_info(orders)')
columns = cursor.fetchall()
print('Orders table columns:')
for col in columns:
    print(f"  {col[1]}: {col[2]}")

conn.close()