from flask import Flask, render_template, request, redirect, url_for, session, g, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import pymysql.cursors
import logging

app = Flask(__name__)
app.secret_key = 'your_very_secret_key_change_this' # Replace with a real secret key

# Setup basic logging
logging.basicConfig(level=logging.INFO)

# --- Database Configuration ---
DB_HOST = 'mysql6013.site4now.net'
DB_USER = 'abc901_newcour'
DB_PASSWORD = 'omarreda123'
DB_NAME = 'db_abc901_newcour'

def get_db():
    if 'db' not in g:
        try:
            g.db = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME, cursorclass=pymysql.cursors.DictCursor, connect_timeout=10)
        except pymysql.MySQLError as e:
            logging.error(f"DATABASE CONNECTION ERROR: {e}")
            raise e
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# --- Routes ---

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        with db.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE username = %s", [username])
            user = cursor.fetchone()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error="Invalid username or password")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("SELECT p.*, t.name as team_name FROM players p LEFT JOIN teams t ON p.team_id = t.id ORDER BY p.name")
        players = cursor.fetchall()
        cursor.execute("SELECT * FROM teams ORDER BY name")
        teams = cursor.fetchall()
        # Fetch coaches for the admin panel assignment forms
        cursor.execute("SELECT id, username FROM users WHERE role = 'coach' ORDER BY username")
        coaches = cursor.fetchall()
    return render_template('dashboard.html', username=session['username'], role=session['role'], players=players, teams=teams, coaches=coaches)

@app.route('/scouting_panel')
def scouting_panel():
    """Renders the dynamic scouting panel page."""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('scouting_panel.html')

# --- API Routes ---

@app.route('/api/players')
def api_players():
    """
    API endpoint to get players.
    - Admins get all players.
    - Coaches get only players assigned to them (via teams or directly).
    """
    if 'user_id' not in session:
        return jsonify({"error": "Not authorized"}), 401
    
    db = get_db()
    with db.cursor() as cursor:
        if session['role'] == 'admin':
            sql = "SELECT p.id, p.name, p.number, t.name as team_name FROM players p LEFT JOIN teams t ON p.team_id = t.id ORDER BY p.name"
            cursor.execute(sql)
        else: # It's a coach
            coach_id = session['user_id']
            sql = """
                SELECT DISTINCT p.id, p.name, p.number, t.name as team_name
                FROM players p
                JOIN teams t ON p.team_id = t.id
                WHERE p.team_id IN (SELECT team_id FROM coaches_teams WHERE coach_id = %s)
                OR p.id IN (SELECT player_id FROM coaches_players WHERE coach_id = %s)
                ORDER BY p.name
            """
            cursor.execute(sql, (coach_id, coach_id))
        
        players = cursor.fetchall()
    return jsonify(players)

# --- Admin Routes ---

@app.route('/add_coach', methods=['POST'])
def add_coach():
    if session.get('role') != 'admin': return redirect(url_for('dashboard'))
    
    username = request.form.get('coach_username')
    password = request.form.get('coach_password')

    if not username or not password:
        return redirect(url_for('dashboard'))

    hashed_password = generate_password_hash(password)
    db = get_db()
    with db.cursor() as cursor:
        try:
            cursor.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, 'coach')", (username, hashed_password))
            db.commit()
        except pymysql.err.IntegrityError:
            pass
    return redirect(url_for('dashboard'))


@app.route('/add_team', methods=['POST'])
def add_team():
    if session.get('role') != 'admin': return redirect(url_for('dashboard'))
    team_name = request.form['team_name']
    if team_name:
        db = get_db()
        with db.cursor() as cursor:
            cursor.execute("INSERT INTO teams (name) VALUES (%s)", [team_name])
        db.commit()
    return redirect(url_for('dashboard'))

@app.route('/add_player', methods=['POST'])
def add_player():
    if session.get('role') != 'admin': return redirect(url_for('dashboard'))
    player_name = request.form.get('player_name')
    team_id = request.form.get('team_id')
    player_number = request.form.get('player_number')
    position = request.form.get('position', 'N/A')
    if player_name and team_id:
        db = get_db()
        with db.cursor() as cursor:
            cursor.execute("INSERT INTO players (name, number, position, team_id) VALUES (%s, %s, %s, %s)", (player_name, player_number, position, team_id))
        db.commit()
    return redirect(url_for('dashboard'))

@app.route('/assign_resources', methods=['POST'])
def assign_resources():
    if session.get('role') != 'admin': return redirect(url_for('dashboard'))
    
    coach_id = request.form.get('coach_id')
    assigned_teams = request.form.getlist('assigned_teams')
    assigned_players = request.form.getlist('assigned_players')

    if not coach_id:
        return redirect(url_for('dashboard'))

    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("DELETE FROM coaches_teams WHERE coach_id = %s", [coach_id])
        cursor.execute("DELETE FROM coaches_players WHERE coach_id = %s", [coach_id])

        if assigned_teams:
            team_data = [(coach_id, team_id) for team_id in assigned_teams]
            cursor.executemany("INSERT INTO coaches_teams (coach_id, team_id) VALUES (%s, %s)", team_data)
        
        if assigned_players:
            player_data = [(coach_id, player_id) for player_id in assigned_players]
            cursor.executemany("INSERT INTO coaches_players (coach_id, player_id) VALUES (%s, %s)", player_data)
    
    db.commit()
    return redirect(url_for('dashboard'))

# --- Temporary User Creation Route ---
# This route is for development only.
@app.route('/create_user_dev', methods=['GET'])
def create_user_dev():
    username = request.args.get('user')
    password = request.args.get('pass')
    role = request.args.get('role')
    if not (username and password and role):
        return "Please provide user, pass, and role query parameters."

    hashed_password = generate_password_hash(password)
    db = get_db()
    try:
        with db.cursor() as cursor:
            cursor.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, %s)", (username, hashed_password, role))
        db.commit()
        return f"User '{username}' created successfully."
    except pymysql.err.IntegrityError:
        return f"Error: User '{username}' already exists."
    except Exception as e:
        return f"Error creating user: {e}"

if __name__ == '__main__':
    app.run(debug=True)
