"""
SCRAPPER TEAM REDCARDS v5.0 ELITE - REFACTORIZADO
Estructura profesional con 5 capas completas
"""

import threading
import asyncio
import os
from flask import Flask, render_template_string, request, jsonify, make_response
from telethon import TelegramClient

# ============ IMPORTAR MÓDULOS ============
from config import API_ID, API_HASH, SESSION_NAME, PORT, SECRET_KEY, CHANNEL_ID
from config import DEFAULT_ADMIN_USER, DEFAULT_ADMIN_PASSWORD
from database import db, lives_mgr, logger
from auth import login_user, logout_user, verify_session, require_login, require_role, initialize_default_admin
from scraper import scraper_loop
from telegram_handler import setup_event_handlers, get_statistics

# ============ INICIALIZACIÓN FLASK ============
app = Flask(__name__)
app.secret_key = SECRET_KEY
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

def initialize_app():
    logger.add("🚀 Iniciando Scrapper Team RedCards v5.0 Elite...")
    initialize_default_admin()
    logger.add("✅ Aplicación inicializada correctamente")

# ============ HTML TEMPLATES ============

HTML_LOGIN = '''
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Team RedCards - Login VIP</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .container {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            padding: 50px;
            width: 100%;
            max-width: 400px;
        }
        .header {
            text-align: center;
            margin-bottom: 40px;
        }
        .logo { font-size: 48px; margin-bottom: 15px; }
        h1 { color: #333; font-size: 28px; margin-bottom: 10px; }
        .subtitle { color: #999; font-size: 14px; }
        .form-group { margin-bottom: 25px; }
        label { display: block; color: #666; font-weight: 600; margin-bottom: 8px; }
        input {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 14px;
            transition: all 0.3s;
        }
        input:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        button {
            width: 100%;
            padding: 12px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
        }
        button:hover { transform: translateY(-2px); box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3); }
        .error { color: #e74c3c; font-size: 14px; margin-top: 10px; padding: 10px; background: #ffe0e0; border-radius: 5px; display: none; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">💳</div>
            <h1>Team RedCards</h1>
            <p class="subtitle">Acceso VIP v5.0</p>
        </div>
        <form id="loginForm">
            <div class="form-group">
                <label for="username">Usuario</label>
                <input type="text" id="username" placeholder="admin" required>
            </div>
            <div class="form-group">
                <label for="password">Contraseña</label>
                <input type="password" id="password" placeholder="••••••••" required>
            </div>
            <div id="error" class="error"></div>
            <button type="submit">Acceder</button>
        </form>
    </div>
    <script>
        document.getElementById('loginForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            const errorDiv = document.getElementById('error');
            try {
                const response = await fetch('/api/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password })
                });
                const data = await response.json();
                if (response.ok) {
                    document.cookie = `session_token=${data.session_token}; path=/; max-age=86400`;
                    window.location.href = '/dashboard';
                } else {
                    errorDiv.textContent = data.error || 'Error';
                    errorDiv.style.display = 'block';
                }
            } catch (err) {
                errorDiv.textContent = 'Error de conexión';
                errorDiv.style.display = 'block';
            }
        });
    </script>
</body>
</html>
'''

HTML_DASHBOARD = '''
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard - Team RedCards</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI'; background: #0f0f1e; color: #fff; min-height: 100vh; }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 40px; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 15px; }
        h1 { font-size: 32px; }
        .logout-btn { background: #e74c3c; color: white; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: linear-gradient(135deg, #1e1e2e 0%, #2a2a3e 100%); padding: 25px; border-radius: 15px; border-left: 4px solid #667eea; }
        .stat-label { color: #999; font-size: 14px; margin-bottom: 10px; }
        .stat-value { font-size: 36px; font-weight: bold; color: #667eea; }
        .lives-section { background: linear-gradient(135deg, #1e1e2e 0%, #2a2a3e 100%); padding: 25px; border-radius: 15px; margin-bottom: 30px; }
        .lives-section h2 { margin-bottom: 20px; color: #667eea; }
        .live-item { background: rgba(102, 126, 234, 0.1); padding: 15px; border-radius: 8px; margin-bottom: 10px; border-left: 3px solid #27ae60; }
        .logs-section { background: linear-gradient(135deg, #1e1e2e 0%, #2a2a3e 100%); padding: 25px; border-radius: 15px; max-height: 400px; overflow-y: auto; }
        .log-item { font-size: 12px; padding: 8px; border-bottom: 1px solid rgba(255,255,255,0.1); font-family: monospace; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>💳 Dashboard</h1>
            <button class="logout-btn" onclick="logout()">Cerrar</button>
        </div>
        <div class="stats-grid">
            <div class="stat-card"><div class="stat-label">✅ Aprobadas</div><div class="stat-value" id="approved-count">0</div></div>
            <div class="stat-card"><div class="stat-label">❌ Declinadas</div><div class="stat-value" id="declined-count">0</div></div>
            <div class="stat-card"><div class="stat-label">🔄 Total</div><div class="stat-value" id="total-processed">0</div></div>
        </div>
        <div class="lives-section">
            <h2>🔥 LIVES Detectadas</h2>
            <div id="lives-list"></div>
        </div>
        <div class="logs-section">
            <h2>📊 Logs</h2>
            <div id="logs-list"></div>
        </div>
    </div>
    <script>
        function loadData() {
            fetch('/api/stats').then(r => r.json()).then(data => {
                document.getElementById('approved-count').textContent = data.approved;
                document.getElementById('declined-count').textContent = data.declined;
                document.getElementById('total-processed').textContent = data.approved + data.declined;
            });
        }
        function refreshLives() {
            fetch('/api/lives').then(r => r.json()).then(data => {
                const list = document.getElementById('lives-list');
                if (data.lives.length === 0) {
                    list.innerHTML = '<p style="color: #999;">Sin LIVES</p>';
                    return;
                }
                list.innerHTML = data.lives.map(live => `
                    <div class="live-item">
                        <div>${live.cc}</div>
                        <div style="font-size: 12px; margin-top: 5px;">Bank: ${live.bank}</div>
                        <div style="color: #999; font-size: 12px;">${live.timestamp}</div>
                    </div>
                `).join('');
            });
        }
        function refreshLogs() {
            fetch('/api/logs').then(r => r.json()).then(data => {
                const list = document.getElementById('logs-list');
                list.innerHTML = data.logs.map(log => `<div class="log-item">${log}</div>`).join('');
            });
        }
        function logout() {
            fetch('/api/logout', { method: 'POST' });
            document.cookie = 'session_token=; path=/; max-age=0';
            window.location.href = '/';
        }
        loadData();
        refreshLives();
        refreshLogs();
        setInterval(loadData, 5000);
        setInterval(refreshLives, 10000);
        setInterval(refreshLogs, 3000);
    </script>
</body>
</html>
'''

# ============ RUTAS ============

@app.route('/')
def index():
    return render_template_string(HTML_LOGIN)

@app.route('/dashboard')
@require_login
def dashboard():
    return render_template_string(HTML_DASHBOARD)

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    result, error = login_user(data.get('username', ''), data.get('password', ''))
    if error:
        return jsonify({'error': error}), 401
    response = make_response(jsonify({
        'success': True,
        'session_token': result['session_token'],
        'username': result['username']
    }))
    response.set_cookie('session_token', result['session_token'], max_age=86400, httponly=True)
    return response, 200

@app.route('/api/logout', methods=['POST'])
@require_login
def api_logout():
    session_token = request.cookies.get('session_token')
    logout_user(session_token)
    response = make_response(jsonify({'success': True}))
    response.set_cookie('session_token', '', max_age=0)
    return response, 200

@app.route('/api/stats')
@require_login
def api_stats():
    return jsonify(get_statistics()), 200

@app.route('/api/lives')
@require_login
def api_lives():
    return jsonify({'lives': lives_mgr.get_recent_lives(limit=10)}), 200

@app.route('/api/logs')
@require_login
def api_logs():
    return jsonify({'logs': logger.get_recent(limit=50)}), 200

@app.route('/api/health')
def api_health():
    return jsonify({'status': 'healthy', 'version': '5.0'}), 200

# ============ TELETHON ============

async def start_telegram_client():
    try:
        logger.add("📱 Iniciando Telegram...")
        await client.start()
        logger.add("✅ Telegram conectado")
        await setup_event_handlers(client, CHANNEL_ID)
        await scraper_loop(client)
    except Exception as e:
        logger.add(f"❌ Error Telegram: {e}")

def telegram_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_telegram_client())

if __name__ == '__main__':
    initialize_app()
    telegram_t = threading.Thread(target=telegram_thread, daemon=True)
    telegram_t.start()
    logger.add(f"🚀 Servidor en puerto {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False)
