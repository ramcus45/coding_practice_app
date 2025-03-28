from functools import wraps
from flask import Flask, make_response, render_template, request, jsonify, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
import openai
from datetime import datetime, timezone
import dotenv
import os
import hashlib
import subprocess
from flask import flash
from sqlalchemy.orm import joinedload



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

# Configure SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"
print("DB URI:", app.config['SQLALCHEMY_DATABASE_URI'])
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
# Configure MySQL connection

client = openai.OpenAI(api_key=api_key)  # Create OpenAI client

# Predefined Python Tasks
PREDEFINED_TASKS = {
    "task1": {
        "description": "Write a function to calculate the factorial of a number.",
        "test_cases": [
            {"input": "5", "expected_output": "120"},
            {"input": "0", "expected_output": "1"}
        ]
    },
    "task2": {
        "description": "Write a function to check if a string is a palindrome.",
        "test_cases": [
            {"input": "'racecar'", "expected_output": "True"},
            {"input": "'hello'", "expected_output": "False"}
        ]
    },
    "task3": {
        "description": "Implement a function to find the nth Fibonacci number.",
        "test_cases": [
            {"input": "6", "expected_output": "8"},
            {"input": "10", "expected_output": "55"}
        ]
    },
    "task4": {
        "description": "Create a function that reverses the words in a sentence.",
        "test_cases": [
            {"input": "'hello world'", "expected_output": "'world hello'"},
            {"input": "'Python is fun'", "expected_output": "'fun is Python'"}
        ]
    }
}


# Models
class User(db.Model):
    __tablename__ = 'users'  # <-- match your existing table name here
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

class CodeSubmission(db.Model):
    __tablename__ = 'code_submissions'  # <-- match your existing table name here
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    task = db.Column(db.Text)
    user_code = db.Column(db.Text)
    hint = db.Column(db.Text)
    used_ai = db.Column(db.Boolean, default=True)  # ✅ NEW FIELD
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)  # Fixed here
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    duration_seconds = db.Column(db.Integer)


class CompletedTask(db.Model):
    __tablename__ = 'completed_tasks'  # <-- match your existing table name here
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    task_key = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)  # Fixed here
    __table_args__ = (db.UniqueConstraint('user_id', 'task_key', name='_user_task_uc'),)




def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('login'))
        return view_func(*args, **kwargs)
    return wrapper


def nocache(view):
    @wraps(view)
    def no_cache(*args, **kwargs):
        response = make_response(view(*args, **kwargs))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
        return response
    return no_cache



# Hash password using SHA-3
def hash_password(password):
    return hashlib.sha3_256(password.encode()).hexdigest()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
@nocache
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        password_hash = hash_password(password)
        try:
            user = User(username=username, password_hash=password_hash)
            db.session.add(user)
            db.session.commit()
            return redirect(url_for('login'))
        except:
            db.session.rollback()
            return "Username already exists! Try another."
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
@nocache
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        password_hash = hash_password(password)
        user = User.query.filter_by(username=username, password_hash=password_hash).first()
        if user:
            session['user_id'] = user.id
            session['username'] = user.username
            return redirect(url_for('dashboard'))
        else:
            return "Invalid username or password!"
    return render_template('login.html')

@app.route('/dashboard')
@nocache
@login_required
def dashboard():
    completed = CompletedTask.query.filter_by(user_id=session['user_id']).all()
    submissions = CodeSubmission.query.filter_by(user_id=session['user_id']).all()
    completed_keys = {t.task_key for t in completed}
    completed_by_ai_mode = {
    (sub.task, str(sub.used_ai).lower()) for sub in submissions
    }
    return render_template('app.html', username=session['username'], tasks=PREDEFINED_TASKS,completed_keys=completed_keys,completed_by_ai_mode=completed_by_ai_mode)



@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/select_task', methods=['POST'])
@login_required
@nocache
def select_task():
    selected_task_key = request.form['task_key']
    session['start_time'] = datetime.now(timezone.utc).isoformat()  # Store in UTC
    task = PREDEFINED_TASKS.get(selected_task_key, "Invalid task selected.")
    return jsonify({"task": task})

@app.route('/execute_code', methods=['POST'])
@login_required
@nocache
def execute_code():
    user_code = request.form['user_code']
    task_key = request.form['task_key']

    task = PREDEFINED_TASKS.get(task_key)
    if not task:
        return jsonify({"error": "Invalid task key."})

    test_cases = task.get("test_cases", [])
    results = []

    for case in test_cases:
        try:
            input_val = case["input"]
            expected_output = case["expected_output"]

            # Assume function is named solution()
            wrapped_code = f"{user_code}\nprint(solution({input_val}))"
            result = subprocess.run(["py", "-c", wrapped_code], capture_output=True, text=True, timeout=5)
            output = result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
            passed = output == expected_output

            results.append({
                "input": input_val,
                "expected": expected_output,
                "actual": output,
                "passed": passed
            })

        except Exception as e:
            results.append({
                "input": case.get("input"),
                "expected": case.get("expected_output"),
                "actual": str(e),
                "passed": False
            })

    all_passed = all(r["passed"] for r in results)

    if all_passed:
        exists = CompletedTask.query.filter_by(user_id=session['user_id'], task_key=task_key).first()
        if not exists:
            completed = CompletedTask(user_id=session['user_id'], task_key=task_key, timestamp=datetime.utcnow())
            db.session.add(completed)
            db.session.commit()

    return jsonify({"results": results, "all_tests_passed": all_passed})



@app.route('/run_code', methods=['POST'])
@login_required
@nocache
def run_code():
    user_code = request.form['user_code']

    try:
        result = subprocess.run(["py", "-c", user_code], capture_output=True, text=True, timeout=5)
        output = result.stdout if result.returncode == 0 else result.stderr
    except Exception as e:
        output = str(e)

    return jsonify({"output": output})



@app.route('/get_hint', methods=['POST'])
@login_required
@nocache
def get_hint():
    user_code = request.form['user_code']
    task_key = request.form['selectedTask']
    task_info = PREDEFINED_TASKS.get(task_key)
    task_description = task_info["description"] if task_info else "Unknown task"
    prompt = (f"You're an expert python teacher and you assigned your student with: {task_description}"+
    f"Review the following code:\n{user_code} and provide a short hint 200 character max to help them complete the task.")
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=50
    )
    hint = response.choices[0].message.content if response.choices else "No hint generated."
    return jsonify({"hint": hint})

@app.route('/submit_code', methods=['POST'])
@login_required
@nocache
def submit_code():
    task = request.form['task']
    user_code = request.form['user_code']
    hint = request.form['hint']
    timestamp = datetime.now(timezone.utc).replace(tzinfo=None)  # Store as naive UTC
    start_time = session.get('start_time')
    end_time = datetime.now(timezone.utc).replace(tzinfo=None)  # Store as naive UTC
    used_ai = request.form.get("used_ai", "true") == "true"

    if start_time:
        # Convert start_time from ISO format to naive UTC datetime
        start_dt = datetime.fromisoformat(start_time).replace(tzinfo=None)
        duration_seconds = int((end_time - start_dt).total_seconds())
    else:
        start_dt = None
        duration_seconds = None

    submission = CodeSubmission(
        user_id=session['user_id'],
        task=task,
        user_code=user_code,
        hint=hint,
        timestamp=timestamp,
        start_time=start_dt,
        end_time=end_time,
        duration_seconds=duration_seconds,
        used_ai=used_ai
    )
    db.session.add(submission)
    db.session.commit()
    return jsonify({"message": "Code submitted successfully!"})

@app.route('/history')
@login_required
@nocache
def submission_history():
    submissions = CodeSubmission.query.filter_by(user_id=session['user_id']).order_by(CodeSubmission.timestamp.desc()).all()
    return render_template('history.html', submissions=submissions)


if __name__ == '__main__':
    app.run(debug=True)
