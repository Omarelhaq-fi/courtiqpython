from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a real secret key

# Hardcoded users for demonstration
# In a real application, you would query a database
USERS = {
    "admin": "adminpassword",
    "coach": "coachpassword"
}

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handles the login process.
    - GET: Displays the login form.
    - POST: Authenticates the user.
    """
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Check if the user exists and the password is correct
        if username in USERS and USERS[username] == password:
            session['username'] = username
            session['role'] = 'admin' if username == 'admin' else 'coach'
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
    Displays the main dashboard.
    Requires the user to be logged in.
    """
    if 'username' in session:
        return render_template('dashboard.html', username=session['username'], role=session['role'])
    return redirect(url_for('login'))

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
