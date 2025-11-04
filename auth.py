from functools import wraps
from datetime import datetime, timedelta
from flask import request, jsonify
from config import MAX_LOGIN_ATTEMPTS, LOGIN_ATTEMPT_TIMEOUT, SESSION_TIMEOUT
from database import db, logger
from utils import PasswordManager

pm = PasswordManager()

def login_user(username, password):
    failed = db.get_failed_login_attempts(username, LOGIN_ATTEMPT_TIMEOUT // 60)
    if failed >= MAX_LOGIN_ATTEMPTS:
        logger.add(f"⚠️ Bloqueada: {username}")
        return None, "Cuenta bloqueada"

    user = db.get_user(username)
    if not user:
        db.record_login_attempt(username, False)
        return None, "Usuario o contraseña incorrectos"

    if not pm.verify_password(password, user['password_hash']):
        db.record_login_attempt(username, False)
        return None, "Usuario o contraseña incorrectos"

    db.record_login_attempt(username, True)
    db.update_last_login(user['id'])
    logger.add(f"✅ Login: {username}")

    token = pm.generate_session_token()
    expires_at = datetime.now() + timedelta(seconds=SESSION_TIMEOUT)
    db.create_session(user['id'], token, expires_at)

    return {'user_id': user['id'], 'username': username, 'session_token': token}, None

def logout_user(token):
    db.invalidate_session(token)
    logger.add("✅ Logout")

def verify_session(token):
    if not token:
        return None
    return db.get_session(token)

def require_login(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get('session_token')
        if not token:
            return jsonify({'error': 'No autorizado'}), 401
        session = verify_session(token)
        if not session:
            return jsonify({'error': 'Sesión expirada'}), 401
        request.user = {'user_id': session['user_id'], 'username': session['username']}
        return f(*args, **kwargs)
    return decorated

def initialize_default_admin():
    from config import DEFAULT_ADMIN_USER, DEFAULT_ADMIN_PASSWORD
    if not db.user_exists(DEFAULT_ADMIN_USER):
        hash_pwd = pm.hash_password(DEFAULT_ADMIN_PASSWORD)
        db.create_user(DEFAULT_ADMIN_USER, hash_pwd, 'owner')
        logger.add("✅ Admin creado")
