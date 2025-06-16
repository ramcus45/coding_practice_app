from functools import wraps
from flask import Flask, make_response, render_template, request, jsonify, redirect, url_for, session
import openai
from datetime import datetime, timezone
import dotenv
import os
from utils import hash_password
import subprocess
from flask import flash
import requests
from models import db, User, CodeSubmission, CompletedTask



# Load environment variables
dotenv.load_dotenv()
api_key = os.getenv("chat_gpt_api_key")


app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

# Configure SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = (
    f"mysql+pymysql://{os.environ['DB_USER']}:{os.environ['DB_PASSWORD']}"
    f"@{os.environ['DB_HOST']}:{os.environ['DB_PORT']}/{os.environ['DB_NAME']}"
)


app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Create the database tables if they don't exist
with app.app_context():
    db.create_all()

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
        except Exception as e:
            db.session.rollback()
            flash("Username already exists! Try another.", "danger")
            return render_template('register.html')
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
            flash("Invalid username or password!", "danger")
            return render_template('login.html')
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
            passed = str(output) == str(expected_output).strip("'")

            results.append({
                "input": str(input_val).strip("'"),
                "expected": str(expected_output).strip("'"),
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

def get_openrouter_hint(prompt, model):
    headers = {
        "Authorization": f"Bearer {os.getenv('openrouter_api_key')}",
        "HTTP-Referer": "http://localhost:5000",  # or your domain
        "X-Title": "AI Code Practice"
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 100,
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload
        )
        data = response.json()
        return data['choices'][0]['message']['content']
    except Exception as e:
        print("OpenRouter hint error:", e)
        return "[Error] Couldn't fetch hint from OpenRouter."




@app.route('/get_hint', methods=['POST'])
@login_required
@nocache
def get_hint():
    user_code = request.form['user_code']
    task_key = request.form['selectedTask']
    provider = request.form.get("provider", "openai")
    model = request.form.get("model", "gpt-4")

    task_info = PREDEFINED_TASKS.get(task_key)
    task_description = task_info["description"] if task_info else "Unknown task"

    prompt = (
        f"You're an expert python teacher and you assigned your student with: {task_description}\n"
        f"Review the following code:\n{user_code}\n"
        f"Provide a short hint (max 200 characters) to help them complete the task."
    )

    if provider in {"deepseek", "llama"}:
        return jsonify({"hint": get_openrouter_hint(prompt, model+":free")})

    elif provider == "openai":
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50
        )
        hint = response.choices[0].message.content if response.choices else "No hint generated."
        return jsonify({"hint": hint})

    else:
        return jsonify({"hint": "Unsupported provider."})


@app.route('/submit_code', methods=['POST'])
@login_required
@nocache
def submit_code():
    provider = request.form['provider']
    model = request.form['model']
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
        used_ai=used_ai,
        provider = provider,
        model_used = model
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

@app.route('/check_username', methods=['POST'])
def check_username():
    username = request.form.get('username')
    exists = User.query.filter_by(username=username).first() is not None
    return jsonify({'taken': exists})



if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)


