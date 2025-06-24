import os
import sqlite3
import uuid
import json
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

# Use /tmp for writable directories on Render
UPLOAD_FOLDER = os.path.join('/tmp', 'uploads')
DB_PATH = os.path.join('/tmp', 'elist.db')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__, static_folder='.', static_url_path='')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
CORS(app)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Ensure DB exists on startup
def ensure_db():
    if not os.path.exists(DB_PATH):
        from database import init_db
        init_db(DB_PATH)
ensure_db()

@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.json
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')

    if not name or not email or not password:
        return jsonify({'status': 'error', 'message': 'All fields are required.'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO users (name, email, password) VALUES (?, ?, ?)', (name, email, password))
        conn.commit()
        return jsonify({'status': 'success'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'status': 'error', 'message': 'Email already exists.'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    if not email or not password:
        return jsonify({'status': 'error', 'message': 'Email and password required'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE email = ? AND password = ?', (email, password))
    user = cursor.fetchone()
    conn.close()
    if user:
        return jsonify({'status': 'success', 'user': {'name': user['name'], 'email': user['email']}})
    else:
        return jsonify({'status': 'error', 'message': 'Invalid credentials'}), 401

@app.route('/api/register-group', methods=['POST'])
def register_group():
    participants_json = request.form.get('participants')
    payment_screenshot = request.files.get('paymentScreenshot')

    if not participants_json or not payment_screenshot:
        return jsonify({'status': 'error', 'message': 'Missing participants or payment screenshot'}), 400

    try:
        participants = json.loads(participants_json)
    except Exception:
        return jsonify({'status': 'error', 'message': 'Invalid participants data'}), 400

    group_id = uuid.uuid4().hex
    screenshot_filename = f"{group_id}_{secure_filename(payment_screenshot.filename)}"
    screenshot_path = os.path.join(app.config['UPLOAD_FOLDER'], screenshot_filename)
    payment_screenshot.save(screenshot_path)

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        for participant in participants:
            cursor.execute('''
                INSERT INTO registrations
                (group_id, participant_type, first_name, last_name, email, phone, address, event, fee, screenshot_filename)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                group_id,
                participant.get('type'),
                participant.get('first_name'),
                participant.get('last_name'),
                participant.get('email'),
                participant.get('phone'),
                participant.get('address'),
                participant.get('event'),
                participant.get('fee'),
                screenshot_filename
            ))
        conn.commit()
        base_url = request.host_url.rstrip('/')
        screenshot_url = f"{base_url}/uploads/{screenshot_filename}"
        return jsonify({'status': 'success', 'group_id': group_id, 'screenshot_url': screenshot_url})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    if os.path.exists(filename):
        return send_from_directory('.', filename)
    else:
        return "File not found", 404
@app.route('/api/registrations', methods=['GET'])
def list_registrations():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM registrations')
    rows = cursor.fetchall()
    conn.close()
    registrations = [dict(row) for row in rows]
    return jsonify({'status': 'success', 'registrations': registrations})

if __name__ == '__main__':
    app.run(debug=True)