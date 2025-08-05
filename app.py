from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_mysqldb import MySQL
import yaml

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a real secret key

# --- Database Configuration ---
# You should ideally store these in a separate, secure config file.
app.config['MYSQL_HOST'] = 'mysql6013.site4now.net'
app.config['MYSQL_USER'] = 'abc901_courtiq'
app.config['MYSQL_PASSWORD'] = 'omarreda123'
app.config['MYSQL_DB'] = 'db_abc901_courtiq'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor' # Returns results as dictionaries

mysql = MySQL(app)

# --- Database Schema Assumption ---
# For this application to work, you need to create tables in your MySQL database.
# Here is the example SQL to create them:
#
# CREATE TABLE users (
#     id INT AUTO_INCREMENT PRIMARY KEY,
#     username VARCHAR(255) NOT NULL UNIQUE,
#     password VARCHAR(255) NOT NULL, -- In a real app, this should be a hashed password
#     role VARCHAR(50) NOT NULL
# );
#
# CREATE TABLE teams (
#     id INT AUTO_INCREMENT PRIMARY KEY,
#     name VARCHAR(255) NOT NULL UNIQUE
# );
#
# CREATE TABLE players (
#     id INT AUTO_INCREMENT PRIMARY KEY,
#     name VARCHAR(255) NOT NULL,
#     position VARCHAR(100),
#     ppg DECIMAL(4,1),
#     rpg DECIMAL(4,1),
#     apg DECIMAL(4,1),
#     team_id INT,
#     FOREIGN KEY (team_id) REFERENCES teams(id)
# );
#
# -- To insert the initial users:
# INSERT INTO users (username, password, role) VALUES ('admin', 'adminpassword', 'admin');
# INSERT INTO users (username, password, role) VALUES ('coach', 'coachpassword', 'coach');

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handles the login process by checking credentials against the database.
    """
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s", [username])
        user = cur.fetchone()
        cur.close()

        # IMPORTANT: Passwords should be hashed. Here we do a plain text comparison for simplicity.
        if user and user['password'] == password:
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error="Invalid credentials")
            
    return render_template('login.html')

@app.route('/')
def home():
    """
    Redirects to the login page if not logged in,
    otherwise shows the dashboard.
    """
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    """
    Displays the main dashboard. Fetches players and teams data.
    Requires the user to be logged in.
    """
    if 'username' in session:
        cur = mysql.connection.cursor()
        
        # Fetch players
        cur.execute("SELECT * FROM players")
        players = cur.fetchall()

        # Fetch teams for the admin form
        cur.execute("SELECT * FROM teams")
        teams = cur.fetchall()

        cur.close()
        
        return render_template('dashboard.html', username=session['username'], role=session['role'], players=players, teams=teams)
    return redirect(url_for('login'))

@app.route('/add_team', methods=['POST'])
def add_team():
    """
    Admin function to add a new team to the database.
    """
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
    """
    Admin function to add a new player to the database.
    """
    if 'role' in session and session['role'] == 'admin':
        player_name = request.form['player_name']
        team_id = request.form['team_id']
        # You can add more fields here like position, etc.
        if player_name and team_id:
            cur = mysql.connection.cursor()
            cur.execute("INSERT INTO players (name, team_id) VALUES (%s, %s)", (player_name, team_id))
            mysql.connection.commit()
            cur.close()
    return redirect(url_for('dashboard'))


@app.route('/logout')
def logout():
    """
    Logs the user out by clearing the session.
    """
    session.pop('username', None)
    session.pop('role', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
