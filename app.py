from flask import Flask, render_template, request, redirect, url_for, session, g, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import pymysql.cursors
import logging
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_very_secret_key_change_this'
logging.basicConfig(level=logging.INFO)

# --- Database Configuration ---
DB_HOST = 'mysql6013.site4now.net'
DB_USER = 'abc901_newcour'
DB_PASSWORD = 'omarreda123'
DB_NAME = 'db_abc901_newcour'

def get_db():
    if 'db' not in g:
        g.db = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME, cursorclass=pymysql.cursors.DictCursor, connect_timeout=10)
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# --- Main Routes ---
@app.route('/')
def home(): return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username, password = request.form['username'], request.form['password']
        db = get_db()
        with db.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE username = %s", [username])
            user = cursor.fetchone()
        if user and check_password_hash(user['password'], password):
            session['user_id'], session['username'], session['role'] = user['id'], user['username'], user['role']
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
    if 'user_id' not in session: return redirect(url_for('login'))
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("SELECT p.*, t.name as team_name, (p.total_points / IF(p.games_played=0, 1, p.games_played)) as ppg, (p.total_rebounds / IF(p.games_played=0, 1, p.games_played)) as rpg, (p.total_assists / IF(p.games_played=0, 1, p.games_played)) as apg FROM players p LEFT JOIN teams t ON p.team_id = t.id ORDER BY p.name")
        players = cursor.fetchall()
        cursor.execute("SELECT * FROM teams ORDER BY name")
        teams = cursor.fetchall()
        cursor.execute("SELECT id, username FROM users WHERE role = 'coach' ORDER BY username")
        coaches = cursor.fetchall()
        cursor.execute("SELECT id, team_name, created_at FROM reports WHERE user_id = %s ORDER BY created_at DESC", [session['user_id']])
        reports = cursor.fetchall()
    return render_template('dashboard.html', **locals())

@app.route('/scouting_panel')
def scouting_panel():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('scouting_panel.html')

@app.route('/coach_board')
def coach_board():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('coach_board.html')

@app.route('/training_planner')
def training_planner():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('training_planner.html')

@app.route('/report/<int:report_id>')
def view_report(report_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    db = get_db()
    with db.cursor() as cursor:
        if session['role'] == 'admin':
            cursor.execute("SELECT * FROM reports WHERE id = %s", [report_id])
        else:
            cursor.execute("SELECT * FROM reports WHERE id = %s AND user_id = %s", (report_id, session['user_id']))
        report = cursor.fetchone()
    if not report: return "Report not found", 404
    report_data = json.loads(report['report_data'])
    return render_template('report.html', report=report, report_data=report_data)

# --- API Routes ---
@app.route('/api/players')
def api_players():
    if 'user_id' not in session: return jsonify({"error": "Not authorized"}), 401
    db = get_db()
    with db.cursor() as cursor:
        if session['role'] == 'admin':
            cursor.execute("SELECT p.id, p.name, p.number, t.name as team_name FROM players p LEFT JOIN teams t ON p.team_id = t.id ORDER BY p.name")
        else:
            cursor.execute("SELECT DISTINCT p.id, p.name, p.number, t.name as team_name FROM players p LEFT JOIN teams t ON p.team_id = t.id WHERE p.team_id IN (SELECT team_id FROM coaches_teams WHERE coach_id = %s) OR p.id IN (SELECT player_id FROM coaches_players WHERE coach_id = %s) ORDER BY p.name", (session['user_id'], session['user_id']))
        players = cursor.fetchall()
    return jsonify(players)

@app.route('/api/training_sessions', methods=['GET', 'POST'])
def handle_training_sessions():
    if 'user_id' not in session: return jsonify({"error": "Not authorized"}), 401
    db = get_db()
    coach_id = session['user_id']
    
    if request.method == 'GET':
        start_date, end_date = request.args.get('start'), request.args.get('end')
        with db.cursor() as cursor:
            cursor.execute("SELECT id, title, session_type, session_date, start_time, end_time, notes FROM training_sessions WHERE coach_id = %s AND session_date BETWEEN %s AND %s", (coach_id, start_date, end_date))
            sessions = cursor.fetchall()
            for s in sessions:
                s['session_date'], s['start_time'], s['end_time'] = s['session_date'].isoformat(), str(s['start_time']), str(s['end_time'])
        return jsonify(sessions)

    if request.method == 'POST':
        data = request.get_json()
        with db.cursor() as cursor:
            cursor.execute("INSERT INTO training_sessions (coach_id, title, session_type, session_date, start_time, end_time, notes) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                           (coach_id, data['title'], data['session_type'], data['session_date'], data['start_time'], data['end_time'], data.get('notes', '')))
            session_id = cursor.lastrowid
        db.commit()
        return jsonify({"success": True, "id": session_id})

@app.route('/api/training_session/<int:session_id>', methods=['DELETE'])
def delete_training_session(session_id):
    if 'user_id' not in session: return jsonify({"error": "Not authorized"}), 401
    db = get_db()
    with db.cursor() as cursor:
        # Ensure a coach can only delete their own sessions
        deleted_rows = cursor.execute("DELETE FROM training_sessions WHERE id = %s AND coach_id = %s", (session_id, session['user_id']))
    db.commit()
    if deleted_rows > 0:
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "error": "Session not found or permission denied"}), 404

@app.route('/api/session_attendance/<int:session_id>', methods=['GET', 'POST'])
def handle_attendance(session_id):
    if 'user_id' not in session: return jsonify({"error": "Not authorized"}), 401
    db = get_db()
    if request.method == 'GET':
        with db.cursor() as cursor:
            cursor.execute("SELECT player_id FROM session_attendance WHERE session_id = %s AND is_present = 1", [session_id])
        return jsonify([row['player_id'] for row in cursor.fetchall()])
    
    if request.method == 'POST':
        present_ids = request.get_json().get('present_player_ids', [])
        with db.cursor() as cursor:
            cursor.execute("SELECT DISTINCT p.id FROM players p WHERE p.team_id IN (SELECT team_id FROM coaches_teams WHERE coach_id = %s) OR p.id IN (SELECT player_id FROM coaches_players WHERE coach_id = %s)", (session['user_id'], session['user_id']))
            all_player_ids = [row['id'] for row in cursor.fetchall()]
            for player_id in all_player_ids:
                is_present = 1 if player_id in present_ids else 0
                cursor.execute("INSERT INTO session_attendance (session_id, player_id, is_present) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE is_present = %s", (session_id, player_id, is_present, is_present))
        db.commit()
        return jsonify({"success": True})

# --- Other Routes (Unchanged) ---
@app.route('/api/save_report', methods=['POST'])
def save_report():
    if 'user_id' not in session: return jsonify({"error": "Not authorized"}), 401
    data = request.get_json()
    report_data_json = json.dumps(data.get('players', []))
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("INSERT INTO reports (user_id, team_name, opponent_score, report_data) VALUES (%s, %s, %s, %s)", (session['user_id'], data.get('teamName'), data.get('opponentScore'), report_data_json))
        report_id = cursor.lastrowid
        for player_report in data.get('players', []):
            cursor.execute("UPDATE players SET games_played = games_played + 1, total_minutes = total_minutes + %s, total_points = total_points + %s, total_rebounds = total_rebounds + %s, total_assists = total_assists + %s, total_steals = total_steals + %s, total_blocks = total_blocks + %s, total_turnovers = total_turnovers + %s WHERE id = %s", (player_report.get('minutes', 0), player_report.get('points', 0), player_report.get('rebounds', 0), player_report.get('assists', 0), player_report.get('steals', 0), player_report.get('blocks', 0), player_report.get('turnovers', 0), player_report.get('id')))
    db.commit()
    return jsonify({"success": True, "reportId": report_id})

@app.route('/add_coach', methods=['POST'])
def add_coach():
    if session.get('role') != 'admin': return redirect(url_for('dashboard'))
    username, password = request.form.get('coach_username'), request.form.get('coach_password')
    if not username or not password: return redirect(url_for('dashboard'))
    hashed_password = generate_password_hash(password)
    db = get_db()
    with db.cursor() as cursor:
        try:
            cursor.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, 'coach')", (username, hashed_password))
            db.commit()
        except pymysql.err.IntegrityError: pass
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
    player_name, team_id, player_number, position = request.form.get('player_name'), request.form.get('team_id'), request.form.get('player_number'), request.form.get('position', 'N/A')
    if player_name and team_id:
        db = get_db()
        with db.cursor() as cursor:
            cursor.execute("INSERT INTO players (name, number, position, team_id) VALUES (%s, %s, %s, %s)", (player_name, player_number, position, team_id))
        db.commit()
    return redirect(url_for('dashboard'))

@app.route('/assign_resources', methods=['POST'])
def assign_resources():
    if session.get('role') != 'admin': return redirect(url_for('dashboard'))
    coach_id, assigned_teams, assigned_players = request.form.get('coach_id'), request.form.getlist('assigned_teams'), request.form.getlist('assigned_players')
    if not coach_id: return redirect(url_for('dashboard'))
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("DELETE FROM coaches_teams WHERE coach_id = %s", [coach_id])
        cursor.execute("DELETE FROM coaches_players WHERE coach_id = %s", [coach_id])
        if assigned_teams:
            cursor.executemany("INSERT INTO coaches_teams (coach_id, team_id) VALUES (%s, %s)", [(coach_id, team_id) for team_id in assigned_teams])
        if assigned_players:
            cursor.executemany("INSERT INTO coaches_players (coach_id, player_id) VALUES (%s, %s)", [(coach_id, player_id) for player_id in assigned_players])
    db.commit()
    return redirect(url_for('dashboard'))

@app.route('/create_user_dev', methods=['GET'])
def create_user_dev():
    username, password, role = request.args.get('user'), request.args.get('pass'), request.args.get('role')
    if not (username and password and role): return "Please provide user, pass, and role query parameters."
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
