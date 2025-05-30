# models.py
import os
import sqlite3

def init_db():
    print("🔧 Starting database initialization...")

    if not os.path.exists('database'):
        os.makedirs('database')
        print("📁 'database' folder created.")

    db_path = 'database/4s.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Drop old tables
    cursor.execute("DROP TABLE IF EXISTS requests")
    cursor.execute("DROP TABLE IF EXISTS warehouse_inventory")
    print("🗑️ Dropped old 'requests' and 'warehouse_inventory' tables.")

    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT CHECK(role IN ('admin', 'sales', 'warehouse', 'planner', 'support')) NOT NULL,
            email TEXT,
            phone TEXT,
            address TEXT,
            department TEXT,
            dob TEXT,
            gender TEXT
        )
    ''')
    print("✅ Users table ready.")

    # Create updated requests table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item TEXT,
            item_quantity INTEGER,
            comment TEXT,
            created_by TEXT NOT NULL,
            assigned_to TEXT DEFAULT 'warehouse',
            status TEXT CHECK(status IN ('Submitted', 'In Review', 'Fulfilled', 'Declined', 'Forwarded to Production')) DEFAULT 'Submitted',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            warehouse_comment TEXT,
            tracking_id TEXT,
            courier_name TEXT,
            delivery_date TEXT,
            shipment_status TEXT DEFAULT 'Pending',
            stock_available TEXT CHECK(stock_available IN ('Yes', 'No')) DEFAULT 'Yes'
        )
    ''')
    print("✅ Requests table created.")

    # Warehouse inventory table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS warehouse_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item TEXT NOT NULL,
            item_quantity INTEGER NOT NULL
        )
    ''')
    print("✅ Warehouse inventory table created.")

    # Production plans table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS production_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            schedule_date TEXT NOT NULL
        )
    ''')
    print("✅ Production plans table ready.")

    # Support tickets table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS support_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_description TEXT NOT NULL,
            status TEXT DEFAULT 'Open'
        )
    ''')
    print("✅ Support tickets table ready.")

    # Insert default users
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        default_users = [
            ('Admin User', 'admin', 'admin123', 'admin', 'admin@example.com', '9999999999', 'Admin Address', 'Admin Dept', '1990-01-01', 'Male'),
            ('John Doe', 'john', 'john123', 'sales', 'john@example.com', '8888888888', '123 Street', 'Sales', '1992-05-10', 'Male'),
            ('Rita Smith', 'rita', 'rita123', 'warehouse', 'rita@example.com', '7777777777', '456 Road', 'Warehouse', '1995-07-21', 'Female'),
            ('Paul Clark', 'paul', 'paul123', 'planner', 'paul@example.com', '6666666666', '789 Lane', 'Planning', '1991-03-15', 'Male'),
            ('Sara Lee', 'sara', 'sara123', 'support', 'sara@example.com', '5555555555', '101 Ave', 'Support', '1994-11-30', 'Female')
        ]
        cursor.executemany('''
            INSERT INTO users 
            (full_name, username, password, role, email, phone, address, department, dob, gender)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', default_users)
        conn.commit()
        print("✅ Default users inserted.")
    else:
        print("ℹ️ Users already exist. Skipping user insertion.")

    conn.close()
    print("✅ Database initialized and all tables created successfully.")

# Entry point
if __name__ == "__main__":
    init_db()
