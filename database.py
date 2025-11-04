import sqlite3
import json
import os
from datetime import datetime
from config import DATABASE_FILE, LIVES_FILE

class Logger:
    def __init__(self, max_messages=100):
        self.messages = []
        self.max_messages = max_messages

    def add(self, message):
        ts = datetime.now().strftime("%H:%M:%S")
        msg = f"[{ts}] {message}"
        self.messages.append(msg)
        if len(self.messages) > self.max_messages:
            self.messages.pop(0)
        print(msg)

    def get_recent(self, limit=20):
        return self.messages[-limit:]

class DatabaseManager:
    def __init__(self):
        self.db_file = DATABASE_FILE
        self.init_database()

    def get_connection(self):
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        return conn

    def init_database(self):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS login_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                attempt_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                success BOOLEAN DEFAULT 0
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_token TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()

    def user_exists(self, username):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
        result = cursor.fetchone()
        conn.close()
        return result is not None

    def create_user(self, username, password_hash, role='user'):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
                         (username, password_hash, role))
            conn.commit()
            conn.close()
            return True
        except:
            return False

    def get_user(self, username):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ? AND is_active = 1', (username,))
        user = cursor.fetchone()
        conn.close()
        return user

    def update_last_login(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()

    def record_login_attempt(self, username, success=False):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO login_attempts (username, success) VALUES (?, ?)',
                     (username, success))
        conn.commit()
        conn.close()

    def get_failed_login_attempts(self, username, minutes=15):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''SELECT COUNT(*) FROM login_attempts
            WHERE username = ? AND success = 0
            AND attempt_time > datetime('now', '-' || ? || ' minutes')''',
                     (username, minutes))
        result = cursor.fetchone()[0]
        conn.close()
        return result

    def create_session(self, user_id, session_token, expires_at):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO sessions (user_id, session_token, expires_at) VALUES (?, ?, ?)',
                     (user_id, session_token, expires_at))
        conn.commit()
        conn.close()

    def get_session(self, session_token):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''SELECT s.*, u.username, u.role FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.session_token = ? AND s.expires_at > CURRENT_TIMESTAMP''',
                     (session_token,))
        session = cursor.fetchone()
        conn.close()
        return session

    def invalidate_session(self, session_token):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM sessions WHERE session_token = ?', (session_token,))
        conn.commit()
        conn.close()

class LivesManager:
    def __init__(self):
        self.lives_file = LIVES_FILE
        self.lives_list = self.load_lives()

    def load_lives(self):
        if os.path.exists(self.lives_file):
            try:
                with open(self.lives_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []

    def save_lives(self):
        with open(self.lives_file, 'w', encoding='utf-8') as f:
            json.dump(self.lives_list, f, indent=2, ensure_ascii=False)

    def add_live(self, cc, status='✅', response='', country='', bank='', card_type='', gate=''):
        live = {
            "cc": cc, "status": status, "response": response,
            "country": country, "bank": bank, "type": card_type,
            "gate": gate, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.lives_list.append(live)
        if len(self.lives_list) > 100:
            self.lives_list.pop(0)
        self.save_lives()
        return live

    def get_recent_lives(self, limit=10):
        return self.lives_list[-limit:]

logger = Logger()
db = DatabaseManager()
lives_mgr = LivesManager()
