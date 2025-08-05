from flask import Flask, render_template, request, redirect, url_for, session, g
from werkzeug.security import generate_password_hash, check_password_hash
import pymysql.cursors

app = Flask(__name__)
app.secret_key = 'your_very_secret_key_change_this' # Replace with a real secret key

# --- Database Configuration ---
# Using PyMySQL directly for better compatibility with Vercel
DB_HOST = 'mysql6013.site4now.net'
DB_USER = 'abc901_newcour'
DB_PASSWORD = 'omarreda123'
DB_NAME = 'db_abc901_newcour'

def get_db():
    """
    Opens a new database connection if there is none yet for the
    current application context.
    """
    if 'db' not in g:
        g.db = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=10
        )
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    """
    Closes the database again at the end of the request.
    """
    db = g.pop('db', None)
    if db is not None:
        db.close()

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
        db = get_db()
        with db.cursor() as cursor:
            cursor.execute("SELECT p.*, t.name as team_name FROM players p LEFT JOIN teams t ON p.team_id = t.id")
            players = cursor.fetchall()
            cursor.execute("SELECT * FROM teams")
            teams = cursor.fetchall()
        return render_template('dashboard.html', username=session['username'], role=session['role'], players=players, teams=teams)
    return redirect(url_for('login'))

@app.route('/add_team', methods=['POST'])
def add_team():
    if 'role' in session and session['role'] == 'admin':
        team_name = request.form['team_name']
        if team_name:
            db = get_db()
            with db.cursor() as cursor:
                cursor.execute("INSERT INTO teams (name) VALUES (%s)", [team_name])
            db.commit()
    return redirect(url_for('dashboard'))

@app.route('/add_player', methods=['POST'])
def add_player():
    if 'role' in session and session['role'] == 'admin':
        player_name = request.form.get('player_name')
        team_id = request.form.get('team_id')
        position = request.form.get('position', 'N/A')
        if player_name and team_id:
            db = get_db()
            with db.cursor() as cursor:
                cursor.execute("INSERT INTO players (name, team_id, position) VALUES (%s, %s, %s)", (player_name, team_id, position))
            db.commit()
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
    db = get_db()
    try:
        with db.cursor() as cursor:
            cursor.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, %s)", (username, hashed_password, role))
        db.commit()
        return f"User {username} created successfully."
    except Exception as e:
        return f"Error creating user: {e}"

if __name__ == '__main__':
    app.run(debug=True)
