import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# Check food items
cursor.execute('SELECT name, category, description FROM foods')
foods = cursor.fetchall()
print('Food items in database:')
for food in foods:
    print(f'  {food[0]} ({food[1]}): {food[2]}')

print()
print('Testing search for "pizza":')
cursor.execute('SELECT name FROM foods WHERE name LIKE ? OR description LIKE ?', ('%pizza%', '%pizza%'))
results = cursor.fetchall()
print('Results:', [r[0] for r in results])

print()
print('Testing search for "chicken":')
cursor.execute('SELECT name FROM foods WHERE name LIKE ? OR description LIKE ?', ('%chicken%', '%chicken%'))
results = cursor.fetchall()
print('Results:', [r[0] for r in results])

print()
print('Testing search for "fresh":')
cursor.execute('SELECT name FROM foods WHERE name LIKE ? OR description LIKE ?', ('%fresh%', '%fresh%'))
results = cursor.fetchall()
print('Results:', [r[0] for r in results])

conn.close()