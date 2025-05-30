import sqlite3

# Connect to your SQLite database file
conn = sqlite3.connect('database/4s.db')
cursor = conn.cursor()

# Insert a test user for Sales Executive
cursor.execute('''
INSERT INTO users (full_name, username, password, email, role, phone, address, department, dob, gender)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
''', (
    'Test Sales User',         # full_name
    'sales1',                  # username (must be unique)
    'admin123',                # password
    'sales@example.com',       # email
    'Sales',                   # role
    '9876543210',              # phone
    'Test Address',            # address
    'Sales',                   # department
    '1995-05-05',              # dob
    'Male'                     # gender
))


conn.commit()
conn.close()

print("✅ Test Sales user inserted into the database.")
