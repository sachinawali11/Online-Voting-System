import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash
from functools import wraps

app = Flask(__name__)
app.secret_key = 'super_secret_online_voting_key_2026'
DB_NAME = 'database.db'

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # User authentication table with approval status
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            has_voted INTEGER DEFAULT 0,
            is_approved INTEGER DEFAULT 1
        )
    ''')
    
    # Candidates table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            position TEXT NOT NULL,
            votes INTEGER DEFAULT 0
        )
    ''')
    
    # Default Admin account creation
    cursor.execute('SELECT * FROM users WHERE username = "Sachin11"')
    if not cursor.fetchone():
        cursor.execute('INSERT INTO users (username, password, role, is_approved) VALUES (?, ?, ?, 1)',
                       ('Sachin11', 'Sachin11@123', 'admin'))
        
    # Default 10 Voter accounts creation
    cursor.execute('SELECT * FROM users WHERE role = "voter"')
    if not cursor.fetchall():
        for i in range(1, 11):
            username = f'voter{i}'
            password = f'Voter{i}@123'
            cursor.execute('INSERT INTO users (username, password, role, is_approved) VALUES (?, ?, "voter", 1)',
                           (username, password))
        
    # Default Candidates creation
    cursor.execute('SELECT * FROM candidates')
    if not cursor.fetchall():
        cursor.execute('INSERT INTO candidates (name, position) VALUES (?, ?)', ('Alice Johnson', 'Candidate 1'))
        cursor.execute('INSERT INTO candidates (name, position) VALUES (?, ?)', ('Bob Smith', 'Candidate 2'))

    conn.commit()
    conn.close()

init_db()

# Security Access Decorators
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in first.", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'admin':
            flash("Admin access required.", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- ROUTING ---

@app.route('/')
def home():
    if 'user_id' in session:
        if session['role'] == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('voter_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            if user['role'] == 'voter' and not user['is_approved']:
                flash("Your registration is pending admin approval.", "error")
                return redirect(url_for('login'))
                
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('voter_dashboard'))
        else:
            flash("Invalid Username or Password", "error")
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if username and password:
            try:
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute('INSERT INTO users (username, password, role, is_approved) VALUES (?, ?, "voter", 0)',
                               (username, password))
                conn.commit()
                conn.close()
                flash("Registration submitted! Please wait for admin approval before logging in.", "success")
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                flash("Username or Voter ID already exists. Choose a different one.", "error")
        else:
            flash("Please fill in all fields.", "error")
            
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Successfully logged out.", "success")
    return redirect(url_for('login'))

# --- VOTER ROUTES ---

@app.route('/voter')
@login_required
def voter_dashboard():
    if session['role'] != 'voter':
        return redirect(url_for('admin_dashboard'))
        
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    cursor.execute('SELECT * FROM candidates')
    candidates = cursor.fetchall()
    conn.close()
    
    return render_template('voter.html', user=user, candidates=candidates)

@app.route('/vote', methods=['POST'])
@login_required
def cast_vote():
    if session['role'] != 'voter':
        return redirect(url_for('admin_dashboard'))
        
    candidate_id = request.form.get('candidate_id')
    user_id = session['user_id']
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT has_voted FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    
    if user['has_voted']:
        flash("You have already cast your vote!", "error")
    elif candidate_id:
        cursor.execute('UPDATE candidates SET votes = votes + 1 WHERE id = ?', (candidate_id,))
        cursor.execute('UPDATE users SET has_voted = 1 WHERE id = ?', (user_id,))
        conn.commit()
        flash("Your vote has been securely recorded!", "success")
    else:
        flash("Please select a candidate.", "error")
        
    conn.close()
    return redirect(url_for('voter_dashboard'))

# --- ADMIN ROUTES ---

@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM candidates')
    candidates = cursor.fetchall()
    
    cursor.execute('SELECT * FROM users WHERE role = "voter" AND is_approved = 1')
    approved_voters = cursor.fetchall()

    cursor.execute('SELECT * FROM users WHERE role = "voter" AND is_approved = 0')
    pending_voters = cursor.fetchall()
    
    cursor.execute('SELECT COUNT(*) as total FROM users WHERE role = "voter" AND is_approved = 1')
    total_voters = cursor.fetchone()['total']
    
    cursor.execute('SELECT COUNT(*) as voted FROM users WHERE role = "voter" AND is_approved = 1 AND has_voted = 1')
    voted_count = cursor.fetchone()['voted']
    
    conn.close()
    return render_template('admin.html', candidates=candidates, approved_voters=approved_voters, pending_voters=pending_voters, total_voters=total_voters, voted_count=voted_count)

@app.route('/admin/approve_voter/<int:id>')
@login_required
@admin_required
def approve_voter(id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET is_approved = 1 WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash("Voter registration approved.", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reject_voter/<int:id>')
@login_required
@admin_required
def reject_voter(id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM users WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash("Voter registration request rejected.", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/add_candidate', methods=['POST'])
@login_required
@admin_required
def add_candidate():
    name = request.form.get('name', '').strip()
    position = request.form.get('position', '').strip()
    
    if name and position:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO candidates (name, position) VALUES (?, ?)', (name, position))
        conn.commit()
        conn.close()
        flash(f"Candidate '{name}' added.", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_candidate/<int:id>')
@login_required
@admin_required
def delete_candidate(id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM candidates WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash("Candidate removed.", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/add_voter', methods=['POST'])
@login_required
@admin_required
def add_voter():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    
    if username and password:
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('INSERT INTO users (username, password, role, is_approved) VALUES (?, ?, "voter", 1)', (username, password))
            conn.commit()
            conn.close()
            flash(f"Voter '{username}' registered and approved.", "success")
        except sqlite3.IntegrityError:
            flash("Voter ID already exists.", "error")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reset_election')
@login_required
@admin_required
def reset_election():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE candidates SET votes = 0')
    cursor.execute('UPDATE users SET has_voted = 0 WHERE role = "voter"')
    conn.commit()
    conn.close()
    flash("All election votes have been reset.", "success")
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
