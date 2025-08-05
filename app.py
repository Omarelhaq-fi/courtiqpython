from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
import pymysql

app = Flask(__name__)
app.secret_key = 'your_very_secret_key_change_this' # Replace with a real secret key

# --- Database Configuration ---
# Using PyMySQL for better compatibility with Vercel
app.config['MYSQL_HOST'] = 'mysql6013.site4now.net'
app.config['MYSQL_USER'] = 'abc901_newcour'
app.config['MYSQL_PASSWORD'] = 'omarreda123'
app.config['MYSQL_DB'] = 'db_abc901_newcour'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor' 
# Use PyMySQL as the driver
app.config['MYSQL_CUSTOM_OPTIONS'] = {'ssl': {'ca': None}} # Adjust SSL settings if needed by host

mysql = MySQL(app)

# --- Database Schema Assumption ---
# You need to run the updated SQL setup script in your database.
# The `password` column should be longer to store hashes, e.g., VARCHAR(255).

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handles the login process by checking credentials against the database.
    Now uses hashed password checking.
    """
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s", [username])
        user = cur.fetchone()
        cur.close()

        if user and check_password_hash(user['password'], password):
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error="Invalid username or password")
            
    return render_template('login.html')

@app.route('/')
def home():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'username' in session:
        cur = mysql.connection.cursor()
        cur.execute("SELECT p.*, t.name as team_name FROM players p LEFT JOIN teams t ON p.team_id = t.id")
        players = cur.fetchall()
        cur.execute("SELECT * FROM teams")
        teams = cur.fetchall()
        cur.close()
        return render_template('dashboard.html', username=session['username'], role=session['role'], players=players, teams=teams)
    return redirect(url_for('login'))

@app.route('/add_team', methods=['POST'])
def add_team():
    if 'role' in session and session['role'] == 'admin':
        team_name = request.form['team_name']
        if team_name:
            cur = mysql.connection.cursor()
            cur.execute("INSERT INTO teams (name) VALUES (%s)", [team_name])
            mysql.connection.commit()
            cur.close()
    return redirect(url_for('dashboard'))

@app.route('/add_player', methods=['POST'])
def add_player():
    if 'role' in session and session['role'] == 'admin':
        player_name = request.form.get('player_name')
        team_id = request.form.get('team_id')
        position = request.form.get('position', 'N/A')
        if player_name and team_id:
            cur = mysql.connection.cursor()
            cur.execute("INSERT INTO players (name, team_id, position) VALUES (%s, %s, %s)", (player_name, team_id, position))
            mysql.connection.commit()
            cur.close()
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('role', None)
    return redirect(url_for('login'))

# You might want an admin route to add users with hashed passwords
@app.route('/create_user_dev', methods=['GET'])
def create_user_dev():
    # This is a temporary route for development to easily create users.
    # You should remove this in production.
    username = request.args.get('user')
    password = request.args.get('pass')
    role = request.args.get('role')
    if not (username and password and role):
        return "Please provide user, pass, and role query parameters."

    hashed_password = generate_password_hash(password)
    cur = mysql.connection.cursor()
    try:
        cur.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, %s)", (username, hashed_password, role))
        mysql.connection.commit()
        return f"User {username} created successfully."
    except Exception as e:
        return f"Error creating user: {e}"
    finally:
        cur.close()

if __name__ == '__main__':
    app.run(debug=True)
