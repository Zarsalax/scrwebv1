"""
AUTENTICACIÓN
"""
from functools import wraps
from datetime import datetime, timedelta
from flask import request, jsonify
from config import MAX_LOGIN_ATTEMPTS, LOGIN_ATTEMPT_TIMEOUT, SESSION_TIMEOUT
from database import db, logger
from utils import PasswordManager

password_manager = PasswordManager()

def hash_password(password):
    return password_manager.hash_password(password)

def verify_password(password, password_hash):
    return password_manager.verify_password(password, password_hash)

def generate_session_token():
    return password_manager.generate_session_token()

def check_brute_force(username):
    failed_attempts = db.get_failed_login_attempts(username, LOGIN_ATTEMPT_TIMEOUT // 60)
    if failed_attempts >= MAX_LOGIN_ATTEMPTS:
        logger.add(f"⚠️ ALERTA: Demasiados intentos para {username}")
        return True
    return False

def login_user(username, password):
    if check_brute_force(username):
        logger.add(f"❌ Cuenta bloqueada: {username}")
        return None, "Cuenta bloqueada por demasiados intentos"

    user = db.get_user(username)
    if not user:
        db.record_login_attempt(username, False)
        logger.add(f"❌ Usuario no encontrado: {username}")
        return None, "Usuario o contraseña incorrectos"

    if not verify_password(password, user['password_hash']):
        db.record_login_attempt(username, False)
        logger.add(f"❌ Contraseña incorrecta para: {username}")
        return None, "Usuario o contraseña incorrectos"

    db.record_login_attempt(username, True)
    db.update_last_login(user['id'])
    logger.add(f"✅ Login exitoso: {username}")

    session_token = generate_session_token()
    expires_at = datetime.now() + timedelta(seconds=SESSION_TIMEOUT)
    db.create_session(user['id'], session_token, expires_at)

    return {
        'user_id': user['id'],
        'username': user['username'],
        'role': user['role'],
        'session_token': session_token
    }, None

def logout_user(session_token):
    db.invalidate_session(session_token)
    logger.add(f"✅ Sesión cerrada")

def verify_session(session_token):
    if not session_token:
        return None
    return db.get_session(session_token)

def require_login(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        session_token = request.cookies.get('session_token')
        if not session_token:
            return jsonify({'error': 'No autorizado'}), 401
        session_data = verify_session(session_token)
        if not session_data:
            return jsonify({'error': 'Sesión expirada'}), 401
        request.user = {
            'user_id': session_data['user_id'],
            'username': session_data['username'],
            'role': session_data['role']
        }
        return f(*args, **kwargs)
    return decorated_function

def require_role(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            session_token = request.cookies.get('session_token')
            if not session_token:
                return jsonify({'error': 'No autorizado'}), 401
            session_data = verify_session(session_token)
            if not session_data:
                return jsonify({'error': 'Sesión expirada'}), 401
            if session_data['role'] != role:
                return jsonify({'error': 'Permiso denegado'}), 403
            request.user = {
                'user_id': session_data['user_id'],
                'username': session_data['username'],
                'role': session_data['role']
            }
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def initialize_default_admin():
    from config import DEFAULT_ADMIN_USER, DEFAULT_ADMIN_PASSWORD
    if not db.user_exists(DEFAULT_ADMIN_USER):
        password_hash = hash_password(DEFAULT_ADMIN_PASSWORD)
        db.create_user(DEFAULT_ADMIN_USER, password_hash, role='owner')
        logger.add(f"✅ Usuario admin creado")
    else:
        logger.add(f"✅ Usuario admin existe")
