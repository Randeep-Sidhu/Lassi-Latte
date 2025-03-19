from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from flask_mysqldb import MySQL
from flask_bcrypt import Bcrypt
from flask_session import Session
from datetime import datetime

app = Flask(__name__)

# MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'NewPassword@123'  # Update with your MySQL password
app.config['MYSQL_DB'] = 'cafe_db'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

# Session Configuration
app.config['SECRET_KEY'] = 'your_secret_key_here'  # Replace with a strong secret
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True

# Initialize Extensions
mysql = MySQL(app)
bcrypt = Bcrypt(app)
Session(app)

# Create users table (already exists)
with app.app_context():
    cur = mysql.connection.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            first_name VARCHAR(50),
            last_name VARCHAR(50),
            email VARCHAR(100) UNIQUE,
            password_hash VARCHAR(255),
            is_admin BOOLEAN DEFAULT FALSE,
            created_at DATETIME
        )
    """)

    # Create orders table (already exists with your structure)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            item_name VARCHAR(100) NOT NULL,
            quantity INT NOT NULL,
            total_price DECIMAL(10, 2) NOT NULL,
            payment_method ENUM('in_person', 'cod') NOT NULL DEFAULT 'in_person',
            order_status ENUM('pending', 'completed', 'cancelled') NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Create contact_messages table (already exists, added for consistency)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS contact_messages (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(100) NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create feedback table (already exists, added for consistency)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INT AUTO_INCREMENT PRIMARY KEY,
            feedback TEXT NOT NULL,
            user_id INT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    """)
    mysql.connection.commit()
    cur.close()

# Routes
@app.route('/')
def home():
    first_name = session.get('first_name')
    last_name = session.get('last_name')
    return render_template('index.html', first_name=first_name, last_name=last_name)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/account')
def account():
    return render_template('account.html')

@app.route('/basket')
def basket():
    return render_template('basket.html')

@app.route('/careers')
def careers():
    return render_template('careers.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

# Debug Session Route
@app.route('/debug_session')
def debug_session():
    return jsonify({"session": dict(session)})

# User Registration
@app.route('/signup', methods=['POST'])
def signup():
    try:
        data = request.get_json()
        first_name = data.get('first_name')
        last_name = data.get('last_name')
        email = data.get('email')
        password = data.get('password')

        if not all([first_name, last_name, email, password]):
            return jsonify({"status": "error", "message": "All fields are required."})

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        existing_user = cur.fetchone()

        if existing_user:
            cur.close()
            return jsonify({"status": "error", "message": "Email already registered. Please log in."})

        first_name = first_name.capitalize()
        last_name = last_name.capitalize()

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        cur.execute("INSERT INTO users (first_name, last_name, email, password_hash, created_at) VALUES (%s, %s, %s, %s, %s)",
                    (first_name, last_name, email, hashed_password, datetime.now()))
        mysql.connection.commit()
        cur.close()

        return jsonify({"status": "success", "message": "Signup successful! Please log in.", "redirect": "/account"})

    except Exception as e:
        return jsonify({"status": "error", "message": f"Signup failed: {str(e)}"})

# User Login
@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            return jsonify({"status": "error", "message": "Email and password are required."})

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        cur.close()

        if user and bcrypt.check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['email'] = user['email']
            session['is_admin'] = user['is_admin']
            session['first_name'] = user['first_name'].capitalize()
            session['last_name'] = user['last_name'].capitalize()
            
            # Redirect all users to homepage after login
            redirect_url = '/'
            return jsonify({"status": "success", "message": "Login successful!", "redirect": redirect_url})
        else:
            return jsonify({"status": "error", "message": "Invalid email or password."})

    except Exception as e:
        return jsonify({"status": "error", "message": f"Login failed: {str(e)}"})

# User Logout
@app.route('/logout', methods=['GET'])
def logout():
    try:
        session.clear()
        return jsonify({"status": "success", "message": "Logged out successfully.", "redirect": "/"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Logout failed: {str(e)}"})

# Checkout Route
@app.route('/checkout', methods=['POST'])
def checkout():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Please log in to checkout'})
    
    data = request.get_json()
    user_id = data['user_id']
    basket = data['basket']
    total_price = data['total_price']
    payment_method = data['payment_method']

    if not basket:
        return jsonify({'status': 'error', 'message': 'Basket is empty'})

    try:
        grouped_items = {}
        for item in basket:
            name = item['name']
            price = float(item['price'])
            if name in grouped_items:
                grouped_items[name]['quantity'] += 1
                grouped_items[name]['total_price'] += price
            else:
                grouped_items[name] = {'quantity': 1, 'total_price': price}

        cur = mysql.connection.cursor()
        for item_name, details in grouped_items.items():
            cur.execute("""
                INSERT INTO orders (user_id, item_name, quantity, total_price, payment_method)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, item_name, details['quantity'], details['total_price'], payment_method))
        mysql.connection.commit()
        
        cur.execute("SELECT LAST_INSERT_ID() AS order_id")
        order_id = cur.fetchone()['order_id']
        cur.close()
        
        return jsonify({'status': 'success', 'message': 'Order placed successfully', 'order_id': order_id})
    except Exception as e:
        mysql.connection.rollback()
        return jsonify({'status': 'error', 'message': str(e)})

# Confirmation Route
@app.route('/confirmation')
def confirmation():
    order_id = request.args.get('order_id')
    if not order_id:
        return redirect(url_for('home'))

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT id, item_name, quantity, total_price, payment_method 
        FROM orders 
        WHERE id >= %s AND user_id = %s AND created_at = (SELECT created_at FROM orders WHERE id = %s)
    """, (order_id, session.get('user_id'), order_id))
    orders = cur.fetchall()
    cur.close()

    if not orders:
        return redirect(url_for('home'))

    items = [{'item_name': row['item_name'], 'quantity': row['quantity']} for row in orders]
    total_price = sum(row['total_price'] for row in orders)
    payment_method = "In-Person Payment at the Counter" if orders[0]['payment_method'] == 'in_person' else "Cash on Delivery (COD)"

    return render_template('confirmation.html', order_id=order_id, items=items, total_price=total_price, payment_method=payment_method)

# Admin Dashboard Route
@app.route('/admin')
def admin_dashboard():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('account'))

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT o.id, o.user_id, u.first_name, u.last_name, u.email, 
               o.item_name, o.quantity, o.total_price, o.payment_method, 
               o.order_status, o.created_at
        FROM orders o
        JOIN users u ON o.user_id = u.id
        ORDER BY o.created_at DESC
    """)
    orders = cur.fetchall()
    cur.close()

    return render_template('admin.html', orders=orders)

# Admin Update Order Status Route
@app.route('/admin/update_order_status/<int:order_id>', methods=['POST'])
def update_order_status(order_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({'status': 'error', 'message': 'Unauthorized'})

    data = request.get_json()
    new_status = data.get('status')

    if new_status not in ['pending', 'completed', 'cancelled']:
        return jsonify({'status': 'error', 'message': 'Invalid status'})

    try:
        cur = mysql.connection.cursor()
        cur.execute("UPDATE orders SET order_status = %s WHERE id = %s", (new_status, order_id))
        mysql.connection.commit()
        cur.close()
        return jsonify({'status': 'success', 'message': 'Order status updated'})
    except Exception as e:
        mysql.connection.rollback()
        return jsonify({'status': 'error', 'message': str(e)})

# Contact Us Form Submission Route
@app.route('/contact', methods=['POST'])
def contact_submit():
    try:
        data = request.get_json()
        name = data.get('name')
        email = data.get('email')
        message = data.get('message')

        if not all([name, email, message]):
            return jsonify({'success': False, 'message': 'All fields are required.'})

        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO contact_messages (name, email, message)
            VALUES (%s, %s, %s)
        """, (name, email, message))
        mysql.connection.commit()
        cur.close()

        return jsonify({'success': True, 'message': 'Message received successfully!'})
    except Exception as e:
        mysql.connection.rollback()
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

# Feedback Form Submission Route
@app.route('/feedback', methods=['POST'])
def feedback_submit():
    try:
        data = request.get_json()
        feedback = data.get('feedback')
        user_id = session.get('user_id')  # Optional: Link to logged-in user

        if not feedback:
            return jsonify({'success': False, 'message': 'Feedback is required.'})

        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO feedback (feedback, user_id)
            VALUES (%s, %s)
        """, (feedback, user_id))
        mysql.connection.commit()
        cur.close()

        return jsonify({'success': True, 'message': 'Feedback received successfully!'})
    except Exception as e:
        mysql.connection.rollback()
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

# Admin Contact Dashboard Route
@app.route('/admin/contact')
def admin_contact_dashboard():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('account'))

    cur = mysql.connection.cursor()
    # Fetch all contact messages
    cur.execute("""
        SELECT id, name, email, message, created_at
        FROM contact_messages
        ORDER BY created_at DESC
    """)
    contact_messages = cur.fetchall()

    # Fetch all feedback with optional user details
    cur.execute("""
        SELECT f.id, f.feedback, f.user_id, f.created_at, 
               u.first_name, u.last_name, u.email
        FROM feedback f
        LEFT JOIN users u ON f.user_id = u.id
        ORDER BY f.created_at DESC
    """)
    feedback = cur.fetchall()
    cur.close()

    return render_template('admin_contact.html', contact_messages=contact_messages, feedback=feedback)

# User Profile Route
@app.route('/account/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('account'))
    
    cur = mysql.connection.cursor()
    cur.execute("SELECT first_name, last_name, email FROM users WHERE id = %s", (session['user_id'],))
    user = cur.fetchone()
    cur.close()
    
    return render_template('profile.html', user=user)

# Update Profile Route
@app.route('/account/update_profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Please log in to update your profile'})

    data = request.get_json()
    first_name = data.get('first_name')
    last_name = data.get('last_name')
    old_password = data.get('old_password')
    new_password = data.get('new_password')

    if not first_name or not last_name:
        return jsonify({'status': 'error', 'message': 'First name and last name are required'})

    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT password_hash FROM users WHERE id = %s", (session['user_id'],))
        user = cur.fetchone()

        # If password change is requested, verify old password
        if old_password or new_password:
            if not old_password or not new_password:
                cur.close()
                return jsonify({'status': 'error', 'message': 'Both old and new passwords are required to change password'})
            if not bcrypt.check_password_hash(user['password_hash'], old_password):
                cur.close()
                return jsonify({'status': 'error', 'message': 'Incorrect old password'})

        # Update fields
        if old_password and new_password:
            hashed_password = bcrypt.generate_password_hash(new_password).decode('utf-8')
            cur.execute("""
                UPDATE users 
                SET first_name = %s, last_name = %s, password_hash = %s 
                WHERE id = %s
            """, (first_name.capitalize(), last_name.capitalize(), hashed_password, session['user_id']))
        else:
            cur.execute("""
                UPDATE users 
                SET first_name = %s, last_name = %s 
                WHERE id = %s
            """, (first_name.capitalize(), last_name.capitalize(), session['user_id']))

        mysql.connection.commit()
        cur.close()

        # Update session with new names
        session['first_name'] = first_name.capitalize()
        session['last_name'] = last_name.capitalize()

        return jsonify({'status': 'success', 'message': 'Profile updated successfully!'})
    except Exception as e:
        mysql.connection.rollback()
        return jsonify({'status': 'error', 'message': f'Error: {str(e)}'})

if __name__ == '__main__':
    app.run(debug=True)