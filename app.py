from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
import sqlite3
import os
from datetime import datetime
import csv
from io import StringIO
from flask import make_response
import pandas as pd
from io import BytesIO
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_super_secret_key'
DB_PATH = 'database/4s.db'

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# ----------------------------------- Login ---------------------------------------------------


@app.route('/', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username'].strip().lower()
        password = request.form['password']
        role = request.form['role'].strip().lower()

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM users WHERE LOWER(username)=? AND password=? AND LOWER(role)=?
        ''', (username, password, role))
        user = cursor.fetchone()
        conn.close()

        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']  # ✅ for tracking in request creation
            session['role'] = user['role'].lower()
            return redirect(url_for(f"{session['role']}_dashboard"))
        else:
            error = 'Invalid credentials. Please try again.'
    return render_template('login.html', error=error)


# --------------------------------- Admin Dashboard -----------------------------------------------


@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    role_filter = request.args.get('role', '').strip().lower()
    dept_filter = request.args.get('department', '').strip().lower()

    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM users WHERE 1=1"
    params = []
    if role_filter:
        query += " AND LOWER(role) LIKE ?"
        params.append(f"%{role_filter}%")
    if dept_filter:
        query += " AND LOWER(department) LIKE ?"
        params.append(f"%{dept_filter}%")

    cursor.execute(query, params)
    users = cursor.fetchall()
    conn.close()

    return render_template('admin_dashboard.html', users=users)


#--------------------------------------admin add user------------------------------------------------


@app.route('/admin/add_user', methods=['GET', 'POST'])
def add_user():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        data = {field: request.form.get(field, '') for field in [
            'full_name', 'username', 'password', 'email', 'role',
            'phone', 'address', 'department', 'dob', 'gender'
        ]}
        data['role'] = data['role'].lower()

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (full_name, username, password, email, role, phone, address, department, dob, gender)
            VALUES (:full_name, :username, :password, :email, :role, :phone, :address, :department, :dob, :gender)
        ''', data)
        conn.commit()
        conn.close()
        return redirect(url_for('admin_dashboard'))

    return render_template('add_user.html')

#------------------------------admin edit user----------------------------------------------

@app.route('/admin/edit_user/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        fields = {
            'full_name': request.form['full_name'],
            'username': request.form['username'],
            'email': request.form['email'],
            'role': request.form['role'].lower(),
            'department': request.form.get('department', ''),
            'phone': request.form.get('phone', ''),
            'address': request.form.get('address', ''),
            'dob': request.form.get('dob', ''),
            'gender': request.form.get('gender', '')
        }
        password = request.form.get('password', '')

        if password:
            fields['password'] = password
            query = '''UPDATE users SET full_name=?, username=?, email=?, role=?, department=?,
                       phone=?, address=?, dob=?, gender=?, password=? WHERE id=?'''
            values = (*fields.values(), user_id)
        else:
            query = '''UPDATE users SET full_name=?, username=?, email=?, role=?, department=?,
                       phone=?, address=?, dob=?, gender=? WHERE id=?'''
            values = (*fields.values(), user_id)

        cursor.execute(query, values)
        conn.commit()
        conn.close()
        return redirect(url_for('admin_dashboard'))

    cursor.execute('SELECT * FROM users WHERE id=?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return render_template('edit_user.html', user=user) if user else ("User not found", 404)

#-----------------------------------admin delete user---------------------------------------------  


@app.route('/admin/delete/<int:user_id>')
def delete_user(user_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    conn = get_db_connection()
    conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))


# ------------------------------ Sales Executive Dashboard ------------------------------------

@app.route('/sales_dashboard')
def sales_dashboard():
    if session.get('role') != 'sales':
        return redirect(url_for('login'))

    username = session['username']
    conn = sqlite3.connect('database/4s.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM requests WHERE created_by = ?", (username,))
    rows = cursor.fetchall()
    requests = []
    for r in rows:
        created_at = r['created_at']
        if isinstance(created_at, str):
            try:
                created_at = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                created_at = None
        requests.append({**dict(r), 'created_at': created_at})

    cursor.execute("SELECT item, item_quantity FROM warehouse_inventory")
    inventory_rows = cursor.fetchall()
    inventory = [dict(row) for row in inventory_rows]

    # 🔥 Added: Fetch resolved complaints
    cursor.execute("SELECT * FROM complaints")
    resolved_rows = cursor.fetchall()
    resolved_complaints = [dict(row) for row in resolved_rows]
    print("Resolved Complaints:", resolved_complaints)  # Debug print

    conn.close()
    return render_template(
        'sales_dashboard.html',
        requests=requests,
        inventory=inventory,
        resolved_complaints=resolved_complaints  # ✅ Pass to template
    )



#---------------------------------------raise request-------------------------------------------------

from uuid import uuid4

import uuid

@app.route('/raise_request', methods=['GET', 'POST'])
def raise_request():
    if session.get('role') != 'sales':
        return redirect(url_for('login'))

    if request.method == 'POST':
        customer_name = request.form['customer_name']
        customer_id = str(uuid.uuid4())[:8]  # Short unique ID
        item = request.form['item']
        quantity = int(request.form['item_quantity'])
        request_type = request.form.get('request_type', 'New')  # ✅ New field
        created_by = session['username']
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO requests (customer_id, customer_name, item, item_quantity, status, created_by, created_at, request_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (customer_id, customer_name, item, quantity, 'Submitted', created_by, created_at, request_type))

        conn.commit()
        conn.close()

        flash('Request submitted successfully.', 'success')
        return redirect(url_for('sales_dashboard'))

    return render_template('raise_request.html')

#-------------------------------sales report -------------------------------------------------

@app.route('/download_report')
def download_report():
    if session.get('role') != 'sales':
        return redirect(url_for('login'))

    username = session['username']
    conn = sqlite3.connect('database/4s.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT id, customer_id, customer_name, item, item_quantity, status, shipment_status, created_at FROM requests WHERE created_by = ?", (username,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        flash("No requests found to export.", "warning")
        return redirect(url_for('sales_dashboard'))

    # Convert to DataFrame
    df = pd.DataFrame(rows, columns=[col[0] for col in cursor.description])

    # Excel export to in-memory buffer
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sales Requests')
    output.seek(0)

    return send_file(output,
                     download_name='sales_report.xlsx',
                     as_attachment=True,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


#--------------------------------------------------------------------------------------------


from flask import send_file, flash, redirect, url_for, session
import matplotlib.pyplot as plt
import pandas as pd
from io import BytesIO
import sqlite3

@app.route('/sales_report_chart')
def sales_report_chart():
    if session.get('role') != 'sales':
        return redirect(url_for('login'))

    username = session['username']

    conn = sqlite3.connect('database/4s.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Fetch request count per item for the current sales user
    cursor.execute('''
        SELECT item, COUNT(*) as request_count
        FROM requests
        WHERE created_by = ?
        GROUP BY item
    ''', (username,))
    rows = cursor.fetchall()
    conn.close()

    # Convert to DataFrame
    df = pd.DataFrame(rows, columns=['item', 'request_count'])

    if df.empty:
        flash("No request data found to generate chart.", "warning")
        return redirect(url_for('sales_dashboard'))


    plt.figure(figsize=(10, 6))
    df.set_index('item')['request_count'].sort_values().plot(kind='bar', color='skyblue')
    plt.title("Number of Requests per Item")
    plt.ylabel("Request Count")
    plt.xlabel("Item")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.grid(axis='y', linestyle='--', alpha=0.7)


    # Return chart image
    img = BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    plt.clf()
    return send_file(img, mimetype='image/png')

# -------------------------------------- Edit Requests ------------------------------------------------


@app.route('/edit_request/<int:request_id>', methods=['GET', 'POST'])
def edit_request(request_id):
    if session.get('role') != 'sales':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        customer_name = request.form['customer_name']
        request_type = request.form['request_type']
        item = request.form['item']
        item_quantity = request.form['item_quantity']

        cursor.execute('''
            UPDATE requests 
            SET customer_name=?, request_type=?, item=?, item_quantity=? 
            WHERE id=?
        ''', (customer_name, request_type, item, item_quantity, request_id))

        conn.commit()
        conn.close()
        flash('Request updated successfully!', 'success')
        return redirect(url_for('sales_dashboard'))

    cursor.execute('SELECT * FROM requests WHERE id=?', (request_id,))
    request_data = cursor.fetchone()
    conn.close()
    return render_template('edit_request.html', request=request_data)

#--------------------------------------- Delete Requests --------------------------------


@app.route('/delete_request/<int:request_id>')
def delete_request(request_id):
    if session.get('role') != 'sales':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM requests WHERE id=?', (request_id,))
    conn.commit()
    conn.close()
    flash('Request deleted successfully!', 'success')
    return redirect(url_for('sales_dashboard'))

# ------------------------------ Warehouse Officer Dashboard -----------------------------------------


from flask import Flask, render_template, request, redirect, session
from datetime import datetime, timedelta
import sqlite3

@app.route('/warehouse_dashboard', methods=['GET', 'POST'])
def warehouse_dashboard():
    if 'username' not in session or session['role'] != 'warehouse':
        return redirect('/login')

    conn = sqlite3.connect('database/4s.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    search_query = ""
    status_filter = ""

    if request.method == 'POST':
        search_query = request.form.get('search', '').strip()
        status_filter = request.form.get('status_filter', '').strip()

        query = '''
            SELECT * FROM requests
            WHERE assigned_to = 'warehouse'
        '''
        params = []

        if search_query:
            query += " AND item LIKE ?"
            params.append(f"%{search_query}%")
        if status_filter:
            query += " AND status = ?"
            params.append(status_filter)

        query += " ORDER BY created_at DESC"
        c.execute(query, params)
    else:
        c.execute('''
            SELECT * FROM requests
            WHERE assigned_to = 'warehouse'
            ORDER BY created_at DESC
        ''')

    requests_raw = c.fetchall()
    updated_requests = []

    for row in requests_raw:
        item = row['item']
        quantity_needed = row['item_quantity']

        c.execute("SELECT item_quantity FROM warehouse_inventory WHERE item = ?", (item,))
        inventory = c.fetchone()
        stock_status = inventory and inventory['item_quantity'] >= quantity_needed

        row_dict = dict(row)
        row_dict['stock_available'] = stock_status
        row_dict['customer_id'] = row['customer_id']
        row_dict['customer_name'] = row['customer_name']

        # SLA: parse created_at and compute SLA deadline
        created_at = datetime.strptime(row['created_at'], "%Y-%m-%d %H:%M:%S")
        row_dict['created_at_dt'] = created_at
        row_dict['sla_status'] = "Breached"

        now = datetime.now()
        if now <= created_at + timedelta(hours=2):
            row_dict['sla_status'] = "On Time"
        elif now <= created_at + timedelta(hours=2, minutes=30):
            row_dict['sla_status'] = "Warning"

        updated_requests.append(row_dict)

    c.execute('''
        SELECT COUNT(*) as count FROM requests 
        WHERE assigned_to = 'warehouse' AND status = 'Forwarded to Production'
    ''')
    forwarded_count = c.fetchone()['count']

    conn.close()
    return render_template(
        'warehouse_dashboard.html',
        username=session['username'],
        requests=updated_requests,
        search_query=search_query,
        status_filter=status_filter,
        forwarded_count=forwarded_count,
        forwarded_view=False,
        current_time=datetime.now()
    )

# ---------------------warehouse Update Request ----------------------------------------------


@app.route('/warehouse/update/<int:request_id>', methods=['GET', 'POST'])
def update_request_warehouse(request_id):
    if 'username' not in session or session['role'] != 'warehouse':
        return redirect('/login')

    conn = sqlite3.connect('database/4s.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    if request.method == 'POST':
        #comment = request.form['warehouse_comment']
        #courier = request.form.get('courier_name')
        delivery_date = request.form.get('delivery_date')
        now = datetime.now()

        # Get request item and quantity
        c.execute("SELECT item, item_quantity FROM requests WHERE id = ?", (request_id,))
        req = c.fetchone()
        if req:
            item = req['item']
            req_qty = req['item_quantity']
        else:
            flash("Request not found.", "danger")
            conn.close()
            return redirect(url_for('warehouse_dashboard'))

        # Get inventory quantity
        c.execute("SELECT item_quantity FROM warehouse_inventory WHERE item = ?", (item,))
        inv = c.fetchone()
        inv_qty = inv['item_quantity'] if inv else 0

        if inv_qty >= req_qty:
            # ✅ Stock is available — fulfill
            new_qty = inv_qty - req_qty
            c.execute("UPDATE warehouse_inventory SET item_quantity = ? WHERE item = ?", (new_qty, item))

            # 🔁 Auto-generate tracking ID
            generated_tracking_id = f"TRK{int(datetime.now().timestamp())}{request_id}"

            c.execute("""
                UPDATE requests SET
                    status = 'Fulfilled',
                    
                    tracking_id = ?,
                    delivery_date = ?,
                    shipment_status = 'Shipped',
                    updated_at = ?,
                    stock_available = 'Yes'
                WHERE id = ?
            """, ( generated_tracking_id, delivery_date, now, request_id))
            flash('Request Fulfilled automatically. Stock was available.', 'success')
        else:
            # ❌ Stock not available — forward
            c.execute("""
                UPDATE requests SET
                    status = 'Forwarded to Production',
                    
                    updated_at = ?,
                    stock_available = 'No',
                    assigned_to = 'planner',
                    was_forwarded = 1
                WHERE id = ?
            """, ( now, request_id))
            flash('Stock not available. Request forwarded to Production Planner.', 'warning')

        conn.commit()
        conn.close()
        return redirect(url_for('warehouse_dashboard'))

    # GET: Load request data
    c.execute("SELECT * FROM requests WHERE id = ?", (request_id,))
    request_data = c.fetchone()
    conn.close()
    return render_template('warehouse_update.html', request=request_data)

#--------------------------------warehouse delete request---------------------------------------------

@app.route('/warehouse/delete/<int:request_id>', methods=['POST'])
def delete_shipped_request(request_id):
    if 'username' not in session or session['role'] != 'warehouse':
        return redirect('/login')

    conn = sqlite3.connect('database/4s.db')
    c = conn.cursor()

    # Check if the request is shipped
    c.execute("SELECT shipment_status FROM requests WHERE id = ?", (request_id,))
    req = c.fetchone()

    if req and req[0] == 'Shipped':
        c.execute("DELETE FROM requests WHERE id = ?", (request_id,))
        conn.commit()
        flash("Shipped request deleted successfully.", "success")
    else:
        flash("Request is not shipped or doesn't exist.", "danger")

    conn.close()
    return redirect(url_for('warehouse_dashboard'))

# -------------------------- Warehouse Stock -------------------------------------------

@app.route('/warehouse_stock', methods=['GET', 'POST'])
def warehouse_stock():
    conn = sqlite3.connect('database/4s.db')
    cursor = conn.cursor()

    if request.method == 'POST':
        item = request.form['item']
        quantity_change = int(request.form['quantity'])

        # Check if item exists
        cursor.execute("SELECT item_quantity FROM warehouse_inventory WHERE item = ?", (item,))
        row = cursor.fetchone()

        if row:
            new_quantity = row[0] + quantity_change
            if new_quantity < 0:
                flash('Quantity cannot be negative.', 'danger')
            else:
                cursor.execute("UPDATE warehouse_inventory SET item_quantity = ? WHERE item = ?", (new_quantity, item))
                conn.commit()
                flash(f'Stock updated successfully. New quantity of "{item}": {new_quantity}', 'success')
        else:
            flash(f'Item "{item}" not found in inventory.', 'warning')

    cursor.execute("SELECT id, item, item_quantity FROM warehouse_inventory")
    stock_data = cursor.fetchall()
    conn.close()
    return render_template('warehouse_stock.html', stock=stock_data)

#---------------------------- Warehouse Forwarded Requests ---------------------------------------------

@app.route('/warehouse_forwarded')
def warehouse_forwarded():
    conn = sqlite3.connect('database/4s.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Fetch all requests that were ever forwarded to production
    c.execute("SELECT * FROM requests WHERE was_forwarded = 1")
    forwarded_requests = c.fetchall()

    updated_requests = []
    for row in forwarded_requests:
        row_dict = dict(row)

        # Safely set customer_id and customer_name if they exist in the row
        row_dict['customer_id'] = row['customer_id'] if 'customer_id' in row.keys() else 'N/A'
        row_dict['customer_name'] = row['customer_name'] if 'customer_name' in row.keys() else 'N/A'

        updated_requests.append(row_dict)

    conn.close()
    return render_template('warehouse_forwarded.html', requests=updated_requests)

#---------------------------- Delete Forwarded Requests ---------------------------------------------

@app.route('/warehouse_forwarded/delete/<int:request_id>', methods=['POST'])
def delete_forwarded_shipped_request(request_id):
    if 'username' not in session or session['role'] != 'warehouse':
        return redirect('/login')

    conn = sqlite3.connect('database/4s.db')
    c = conn.cursor()

    c.execute("SELECT status FROM requests WHERE id = ?", (request_id,))
    req = c.fetchone()

    if req and req[0] == 'Fulfilled':
        c.execute("DELETE FROM requests WHERE id = ?", (request_id,))
        conn.commit()
        flash("Shipped forwarded request deleted successfully.", "success")
    else:
        flash("Request is not shipped or doesn't exist.", "danger")

    conn.close()
    return redirect(url_for('warehouse_forwarded'))


#---------------------------------------warehouse report----------------------------------------------------

@app.route('/download_csv')
def download_csv():
    if 'username' not in session or session['role'] != 'warehouse':
        return redirect('/login')

    conn = sqlite3.connect('database/4s.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM requests WHERE assigned_to = 'warehouse'")
    rows = c.fetchall()
    conn.close()

    output = StringIO()
    writer = csv.writer(output)
    headers = rows[0].keys() if rows else []
    writer.writerow(headers)

    for row in rows:
        writer.writerow([row[h] for h in headers])

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=warehouse_requests.csv"
    response.headers["Content-type"] = "text/csv"
    return response


# ------------------------------- Production Planner Dashboard --------------------------------

@app.route('/planner/dashboard')
def planner_dashboard():
    #print("Session:", session)  # <-- Add this
    if 'username' not in session or session.get('role') != 'planner':
        return redirect(url_for('login'))

    conn = sqlite3.connect('database/4s.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM requests WHERE status != 'Fulfilled'")

    requests = cur.fetchall()

    updated_requests = []
    for row in requests:
        row_dict = dict(row)

        item_name = row_dict.get('item')
        item_quantity = row_dict.get('item_quantity')

        try:
            item_quantity = int(item_quantity)
        except (TypeError, ValueError):
            item_quantity = 0

        cur.execute("SELECT item_quantity FROM warehouse_inventory WHERE item = ?", (item_name,))
        inv = cur.fetchone()

        if inv is not None and inv['item_quantity'] is not None:
            try:
                current_qty = int(inv['item_quantity'])
            except (TypeError, ValueError):
                current_qty = 0
        else:
            current_qty = 0

        shortfall = max(item_quantity - current_qty, 0)
        inventory_status = (
            '✅' if current_qty >= item_quantity else
            '⚠️' if current_qty > 0 else
            '❌'
        )

        row_dict['available_inventory'] = f"{current_qty} {inventory_status}"
        row_dict['shortfall'] = shortfall if row_dict.get('status') == 'Forwarded to Production' else None

        row_dict['customer_id'] = row_dict.get('customer_id', 'N/A')
        row_dict['customer_name'] = row_dict.get('customer_name', 'N/A')
        row_dict['request_type'] = row_dict.get('request_type', 'New')


        updated_requests.append(row_dict)

    conn.close()
    return render_template('planner_request.html', requests=updated_requests)

#---------------------------------------planner report----------------------------------------------------

@app.route('/planner/report')
def report():
    if session.get('role') != 'planner':
        return redirect(url_for('login'))

    conn = sqlite3.connect('database/4s.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Use updated_at as fulfillment timestamp
    cursor.execute('''
        SELECT item, 
               AVG(julianday(updated_at) - julianday(created_at)) AS avg_turnaround
        FROM requests
        WHERE status = 'Fulfilled' AND updated_at IS NOT NULL
        GROUP BY item
    ''')
    rows = cursor.fetchall()
    conn.close()

    df = pd.DataFrame(rows, columns=['item', 'avg_turnaround'])

    if df.empty:
        flash("No Fulfilled request data found to generate chart.", "warning")
        return redirect(url_for('planner_dashboard'))

    # Generate chart
    plt.figure(figsize=(10, 6))
    df.set_index('item')['avg_turnaround'].sort_values().plot(kind='bar', color='mediumseagreen')
    plt.title("Average Fulfillment Turnaround Time by Item")
    plt.ylabel("Avg Turnaround (Days)")
    plt.xlabel("Item")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.grid(axis='y', linestyle='--', alpha=0.7)

    chart_path = os.path.join('static', 'avg_turnaround_chart.png')
    plt.savefig(chart_path)
    plt.clf()

    return render_template('planner_report.html')

#---------------------------------------planner update status---------------------------------------------

@app.route('/planner/request/<int:req_id>/update_status', methods=['POST']) 
def update_status(req_id):
    new_status = request.form.get('status')
    allowed = ['Submitted', 'In Review', 'Fulfilled', 'Declined', 'Forwarded to Production']
    if new_status not in allowed:
        return f"Invalid status {new_status}", 400

    with sqlite3.connect('database/4s.db') as conn:
        cur = conn.cursor()

        # 1) Fetch existing status, item & quantity
        cur.execute("SELECT status, item, item_quantity FROM requests WHERE id = ?", (req_id,))
        row = cur.fetchone()
        if not row:
            flash(f"❌ Request #{req_id} not found.", 'danger')
            return redirect(url_for('planner_dashboard'))

        old_status, item_name, qty = row

        # 2) Update main status & timestamp
        cur.execute("""
            UPDATE requests
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_status, req_id))

        # 3) Shipment status logic
        if new_status == 'Fulfilled':
            cur.execute("""
                UPDATE requests
                SET shipment_status = 'Shipped'
                WHERE id = ?
            """, (req_id,))

            # ✅ Only increment inventory if it was not already Fulfilled
            if old_status != 'Fulfilled':
                cur.execute("""
                    UPDATE warehouse_inventory
                    SET item_quantity = item_quantity + ?
                    WHERE item = ?
                """, (qty, item_name))

        else:
            cur.execute("""
                UPDATE requests
                SET shipment_status = 'Pending'
                WHERE id = ?
            """, (req_id,))

        # ✅ NEW: reduce inventory on "Forwarded to Production"
        if new_status == 'Forwarded to Production':
            cur.execute("SELECT item_quantity FROM warehouse_inventory WHERE item = ?", (item_name,))
            inventory_row = cur.fetchone()
            current_qty = inventory_row[0] if inventory_row else 0
            shortfall = qty - current_qty if qty > current_qty else 0

            if shortfall > 0 and current_qty > 0:
                # Deduct whatever is available (avoid negative inventory)
                cur.execute("""
                    UPDATE warehouse_inventory
                    SET item_quantity = item_quantity - ?
                    WHERE item = ?
                """, (min(qty, current_qty), item_name))

        conn.commit()

    flash(f"✅ Request #{req_id} updated to '{new_status}'", 'success')
    return redirect(url_for('planner_dashboard'))

# ---------------------------- Support Dashboard -------------------------------------------

# At the top of your file (global variable)
complaints = []  # This should be a list

from flask import Flask, render_template, request, redirect, url_for, session, flash, get_flashed_messages
from datetime import datetime
import sqlite3

@app.route('/raise_complaint', methods=['GET', 'POST'])
def raise_complaint():
    if session.get('role') != 'sales':
        return redirect(url_for('login'))

    conn = sqlite3.connect('database/4s.db')
    cursor = conn.cursor()

    if request.method == 'POST':
        cursor.execute('''
            INSERT INTO complaints (customer_id, subject, description, created_at, status)
            VALUES (?, ?, ?, ?, 'Open')
        ''', (
            request.form['customer_id'],
            request.form['subject'],
            request.form['description'],
            datetime.now()
        ))
        conn.commit()
        conn.close()
        flash("✅ Complaint submitted successfully!", "success")
        return redirect(url_for('raise_complaint'))

    # Get all customer_ids created by the logged-in user
    cursor.execute('''
        SELECT customer_id FROM requests
        WHERE created_by = ?
        ORDER BY created_at DESC
    ''', (session['username'],))
    rows = cursor.fetchall()
    customer_ids = [row[0] for row in rows]

    conn.close()
    return render_template('raise_complaint.html', customer_ids=customer_ids)


    # ✅ Get latest customer_id created by this user
    conn = sqlite3.connect('database/4s.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT customer_id FROM requests
        WHERE created_by = ?
        ORDER BY created_at DESC
        LIMIT 1
    ''', (session['username'],))
    row = cursor.fetchone()
    customer_id = row[0] if row else ''

    conn.close()

    return render_template('raise_complaint.html', customer_id=customer_id)




@app.route('/support_dashboard')
def support_dashboard():
    conn = sqlite3.connect('database/4s.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM complaints WHERE status = 'Open'")
    complaints = cursor.fetchall()
    conn.close()
    return render_template('support_dashboard.html', complaints=complaints)

@app.route('/respond/<int:complaint_id>', methods=['GET', 'POST'])
def respond_complaint(complaint_id):
    conn = sqlite3.connect('database/4s.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM complaints WHERE id = ?", (complaint_id,))
    complaint = cursor.fetchone()

    if not complaint:
        conn.close()
        return "Complaint not found", 404

    if request.method == 'POST':
        cursor.execute('''
            UPDATE complaints SET response = ?, resolved_at = ?, status = 'Resolved' WHERE id = ?
        ''', (request.form['response'], datetime.now(), complaint_id))
        conn.commit()
        conn.close()
        return redirect(url_for('support_dashboard'))

    conn.close()
    return render_template('respond_complaint.html', complaint=complaint)


@app.route('/resolved_dashboard')
def resolved_dashboard():
    return render_template('resolved_dashboard.html', complaints=resolved_complaints)

@app.route('/resolved_complaints')
def resolved_complaints():
    if session.get('role') != 'sales':
        return redirect(url_for('login'))

    conn = sqlite3.connect('database/4s.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM complaints")
    rows = cursor.fetchall()
    resolved_requests = [dict(r) for r in rows]

    conn.close()
    return render_template('resolved_complaints.html', resolved_requests=resolved_requests)


@app.route('/delete_complaint/<int:complaint_id>', methods=['POST'])
def delete_complaint(complaint_id):
    if session.get('role') != 'sales':
        return redirect(url_for('login'))

    conn = sqlite3.connect('database/4s.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM complaints WHERE id = ? AND status = 'Resolved'", (complaint_id,))
    conn.commit()
    conn.close()
    flash("🗑️ Complaint deleted successfully.", "success")
    return redirect(url_for('resolved_complaints'))


# -------------------- Logout --------------------

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# -------------------- Run --------------------
if __name__ == '__main__':
    if not os.path.exists(DB_PATH):
        print("❌ Database not found. Please run models.py to initialize it.")
    app.run(debug=True)
