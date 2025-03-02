from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import openai
import mysql.connector
import datetime
import dotenv
import os
import hashlib

# Load environment variables
dotenv.load_dotenv()
api_key = os.getenv("chat_gpt_api_key")
host = os.getenv("host")
port = os.getenv("port")
user = os.getenv("user")
password = os.getenv("password")
database = os.getenv("database")

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "your_secret_key")

# Configure MySQL connection
conn = mysql.connector.connect(
    host=host,
    port=port,
    user=user,
    password=password,
    database=database
)
cursor = conn.cursor()
client = openai.OpenAI(api_key=api_key)  # Create OpenAI client

# Create tables if not exist
cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(255) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL
    )
""")
conn.commit()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS code_submissions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT,
        task TEXT,
        user_code TEXT,
        hint TEXT,
        completion_status TEXT,
        timestamp DATETIME,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
""")
conn.commit()

# Hash password using SHA-3
def hash_password(password):
    return hashlib.sha3_256(password.encode()).hexdigest()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        password_hash = hash_password(password)
        try:
            cursor.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s)", (username, password_hash))
            conn.commit()
            return redirect(url_for('login'))
        except mysql.connector.IntegrityError:
            return "Username already exists! Try another."
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        password_hash = hash_password(password)
        cursor.execute("SELECT * FROM users WHERE username = %s AND password_hash = %s", (username, password_hash))
        user = cursor.fetchone()
        if user:
            session['user_id'] = user[0]
            session['username'] = user[1]
            return redirect(url_for('dashboard'))
        else:
            return "Invalid username or password!"
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('app.html', username=session['username'])

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/get_response', methods=['POST'])
def get_response():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_input = request.form['user_input']
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": user_input}]
    )
    return jsonify({"response": response.choices[0].message.content})

@app.route('/generate_task', methods=['GET'])
def generate_task():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    prompt = "Generate a simple programming exercise in Python."
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    task = response.choices[0].message.content if response.choices else "No task generated."
    return jsonify({"task": task})

@app.route('/get_hint', methods=['POST'])
def get_hint():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_code = request.form['user_code']
    prompt = f"Review the following code and provide hints for improvement:\n{user_code}"
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    hint = response.choices[0].message.content if response.choices else "No hint generated."
    return jsonify({"hint": hint})


@app.route('/submit_code', methods=['POST'])
def submit_code():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    task = request.form['task']
    user_code = request.form['user_code']
    hint = request.form['hint']
    timestamp = datetime.datetime.now()
    completion_status = "Pending"
    cursor.execute(
        "INSERT INTO code_submissions (user_id, task, user_code, hint, completion_status, timestamp) VALUES (%s, %s, %s, %s, %s, %s)",
        (session['user_id'], task, user_code, hint, completion_status, timestamp)
    )
    conn.commit()
    return jsonify({"message": "Code submitted successfully!"})

if __name__ == '__main__':
    app.run(debug=True)