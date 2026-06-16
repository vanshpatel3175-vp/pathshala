import sqlite3
conn = sqlite3.connect('db.sqlite3')
cursor = conn.cursor()
tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'dashboard_%'").fetchall()
for (table,) in tables:
    new_name = table.replace('dashboard_', 'super_admin_')
    cursor.execute(f"ALTER TABLE {table} RENAME TO {new_name}")
conn.commit()
conn.close()
