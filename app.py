import threading
import asyncio
import random
import time
import os
import json
import sqlite3
import secrets
from functools import wraps
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, jsonify, redirect, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, RPCError

# ============ CONFIGURACIÓN ============
API_ID = int(os.environ.get('API_ID', '22154650'))
API_HASH = os.environ.get('API_HASH', '2b554e270efb419af271c47ffe1d72d3')
SESSION_NAME = 'session'

channel_env = os.environ.get('CHANNEL_ID', '-1003101739772')
try:
    CHANNEL_ID = int(channel_env)
except ValueError:
    CHANNEL_ID = channel_env

PORT = int(os.environ.get('PORT', 8080))

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
log_messages = []
lives_list = []
channelid = -1003101739772
approved_count = 0
declined_count = 0
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.permanent_session_lifetime = timedelta(days=7)

LIVES_FILE = 'lives_database.json'
DB_FILE = 'users.db'
OWNER_CONFIG_FILE = 'owner_config.json'

# ============ VARIABLES GLOBALES OWNER ============
OWNER_CONFIG = None

# ============ CONFIGURAR OWNER ============

def init_owner_config():
    """Inicializa configuración OWNER"""
    global OWNER_CONFIG
    
    if os.path.exists(OWNER_CONFIG_FILE):
        try:
            with open(OWNER_CONFIG_FILE, 'r') as f:
                OWNER_CONFIG = json.load(f)
                print(f"\n{'='*70}")
                print(f"✅ Config OWNER cargada")
                print(f"🔐 URL: {OWNER_CONFIG['secret_url']}")
                print(f"👤 Usuario: {OWNER_CONFIG['username']}")
                print(f"🔑 Contraseña: {OWNER_CONFIG['password']}")
                print(f"{'='*70}\n")
                return OWNER_CONFIG
        except:
            pass
    
    config = {
        "secret_url": secrets.token_urlsafe(32),
        "username": "admin",
        "password": "ChangeMe123!@#",
        "created_at": datetime.now().isoformat()
    }
    
    try:
        with open(OWNER_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        
        OWNER_CONFIG = config
        
        print(f"\n{'='*70}")
        print(f"🔐 URL SECRETA OWNER: /secret/{config['secret_url']}/owner_login")
        print(f"👤 Usuario: {config['username']}")
        print(f"🔑 Contraseña: {config['password']}")
        print(f"⚠️ CAMBIAR INMEDIATAMENTE")
        print(f"{'='*70}\n")
        
        return config
    except Exception as e:
        print(f"Error: {e}")
        return None

def get_owner_config():
    global OWNER_CONFIG
    if OWNER_CONFIG is None:
        init_owner_config()
    return OWNER_CONFIG

# ============ BASE DE DATOS ============

def init_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            failed_attempts INTEGER DEFAULT 0,
            locked_until TIMESTAMP
        )''')
        
        conn.commit()
        conn.close()
    except:
        pass

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def load_lives_from_file():
    global lives_list
    if os.path.exists(LIVES_FILE):
        try:
            with open(LIVES_FILE, 'r', encoding='utf-8') as f:
                lives_list = json.load(f)
        except:
            lives_list = []

def save_lives_to_file():
    try:
        with open(LIVES_FILE, 'w', encoding='utf-8') as f:
            json.dump(lives_list, f, indent=2, ensure_ascii=False)
    except:
        pass

def check_brute_force(username):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT failed_attempts, locked_until FROM users WHERE username = ?', (username,))
        user = c.fetchone()
        conn.close()
        
        if user and user['locked_until']:
            locked_time = datetime.fromisoformat(user['locked_until'])
            if datetime.now() < locked_time:
                return True
    except:
        pass
    return False

def increment_failed_attempts(username):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT failed_attempts FROM users WHERE username = ?', (username,))
        user = c.fetchone()
        if user:
            new_attempts = user['failed_attempts'] + 1
            if new_attempts >= 5:
                lock_time = (datetime.now() + timedelta(minutes=15)).isoformat()
                c.execute('UPDATE users SET failed_attempts = ?, locked_until = ? WHERE username = ?',
                         (new_attempts, lock_time, username))
            else:
                c.execute('UPDATE users SET failed_attempts = ? WHERE username = ?', (new_attempts, username))
            conn.commit()
        conn.close()
    except:
        pass

def reset_failed_attempts(username):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE username = ?', (username,))
        conn.commit()
        conn.close()
    except:
        pass

# ============ DECORADORES ============

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ============ FUNCIONES UTILITARIAS ============

def luhn_checksum(card_number):
    def digits_of(n):
        return [int(d) for d in str(n)]
    digits = digits_of(card_number)
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    checksum = sum(odd_digits)
    for d in even_digits:
        checksum += sum(digits_of(d * 2))
    return checksum % 10

def generate_luhn_digit(partial_card):
    check_digit = luhn_checksum(str(partial_card) + '0')
    return (10 - check_digit) % 10

def is_date_valid(month, year):
    try:
        month = int(month)
        year = int(year)
        if year <= 30:
            year += 2000
        elif year <= 99:
            year += 1900
        if month == 12:
            expiry_date = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            expiry_date = datetime(year, month + 1, 1) - timedelta(days=1)
        return expiry_date >= datetime.now()
    except:
        return False

def generate_random_valid_date():
    now = datetime.now()
    days_ahead = random.randint(0, 365 * 5)
    future_date = now + timedelta(days=days_ahead)
    month = f"{future_date.month:02d}"
    year = f"{future_date.year}"
    return month, year

def generate_cc_variants(ccbase, count=20):
    if ',' in ccbase:
        separator = ','
    elif '|' in ccbase:
        separator = '|'
    else:
        log_messages.append(f"❌ Formato desconocido")
        return []
    
    parts = ccbase.strip().split(separator)
    if len(parts) < 4:
        log_messages.append(f"❌ Formato inválido")
        return []
    
    cardnumber = parts[0]
    month = parts[1]
    year = parts[2]
    
    if len(cardnumber) < 12:
        log_messages.append(f"❌ Tarjeta muy corta")
        return []
    
    date_is_valid = is_date_valid(month, year)
    variants = []
    
    if not date_is_valid:
        log_messages.append(f"⚠️ Fecha vencida: {month}/{year}")
        month, year = generate_random_valid_date()
        log_messages.append(f"⚠️ Actualizada: {month}/{year}")
        
        bin_number = cardnumber[:-6]
        for i in range(count):
            random_digits = ''.join([str(random.randint(0, 9)) for _ in range(5)])
            partial = bin_number + random_digits
            luhn_digit = generate_luhn_digit(partial)
            complete_number = partial + str(luhn_digit)
            random_cvv = random.randint(100, 999)
            variant = f"{complete_number}{separator}{month}{separator}{year}{separator}{random_cvv}"
            if variant not in variants:
                variants.append(variant)
        
        log_messages.append(f"✅ 20 CCs generadas")
    else:
        bin_number = cardnumber[:-4]
        for i in range(count):
            random_digits = ''.join([str(random.randint(0, 9)) for _ in range(3)])
            partial = bin_number + random_digits
            luhn_digit = generate_luhn_digit(partial)
            complete_number = partial + str(luhn_digit)
            random_cvv = random.randint(100, 999)
            variant = f"{complete_number}{separator}{month}{separator}{year}{separator}{random_cvv}"
            if variant not in variants:
                variants.append(variant)
        
        log_messages.append(f"✅ 20 CCs generadas")
    
    return variants

# ============ EVENTOS TELETHON ============

async def response_handler(event):
    global approved_count, declined_count, lives_list
    try:
        full_message = event.message.message if event.message.message else ""
        message_lower = full_message.lower()
        
        if "✅" in full_message or "approved" in message_lower:
            approved_count += 1
            lines = full_message.split('\n')
            cc_number = status = response = country = bank = card_type = gate = ""
            
            for line in lines:
                if 'cc:' in line.lower():
                    cc_number = line.split(':', 1)[1].strip() if ':' in line else ""
                elif 'status:' in line.lower():
                    status = line.split(':', 1)[1].strip() if ':' in line else ""
                elif 'response:' in line.lower():
                    response = line.split(':', 1)[1].strip() if ':' in line else ""
                elif 'country:' in line.lower():
                    country = line.split(':', 1)[1].strip() if ':' in line else ""
                elif 'bank:' in line.lower():
                    bank = line.split(':', 1)[1].strip() if ':' in line else ""
                elif 'type:' in line.lower():
                    card_type = line.split(':', 1)[1].strip() if ':' in line else ""
                elif 'gate:' in line.lower():
                    gate = line.split(':', 1)[1].strip() if ':' in line else ""
            
            log_messages.append(f"✅ LIVE: {cc_number[:12]}...")
            
            live_entry = {
                "cc": cc_number,
                "status": status,
                "response": response,
                "country": country,
                "bank": bank,
                "type": card_type,
                "gate": gate,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            lives_list.append(live_entry)
            save_lives_to_file()
            
            if len(lives_list) > 100:
                lives_list.pop(0)
                save_lives_to_file()
            
            formatted_message = f"""╔════════════════════════════════════════╗
           Team RedCards 💳
╚════════════════════════════════════════╝

💳 CC: {cc_number}
✅ Status: {status}
📊 Response: {response}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🗺️ Country: {country}
🏦 Bank: {bank}
💰 Type: {card_type}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💵 GATE: {gate}"""
            
            try:
                if os.path.exists('x1.jpg'):
                    await client.send_file(channelid, 'x1.jpg', caption=formatted_message, parse_mode='markdown')
                else:
                    await client.send_message(channelid, formatted_message, parse_mode='markdown')
            except:
                pass
        
        elif "❌" in full_message or "declined" in message_lower:
            declined_count += 1
            log_messages.append(f"❌ DECLINADA")
        
        if len(log_messages) > 100:
            log_messages.pop(0)
    except:
        pass

async def load_commands():
    try:
        if os.path.exists('cmds.txt'):
            with open('cmds.txt', 'r') as f:
                cmds = [line.strip() for line in f if line.strip()]
                if cmds:
                    return cmds
    except:
        pass
    return ['/check']

async def send_to_bot():
    while True:
        try:
            if not os.path.exists('ccs.txt'):
                await asyncio.sleep(30)
                continue
            
            with open('ccs.txt', 'r') as f:
                ccs_list = f.readlines()
            
            if ccs_list:
                current_cc = ccs_list[0].strip()
                if len(ccs_list) > 1:
                    with open('ccs.txt', 'w') as f:
                        f.writelines(ccs_list[1:])
                else:
                    with open('ccs.txt', 'w') as f:
                        f.write("")
                
                log_messages.append(f"🔄 BIN: {current_cc[:12]}...")
                cc_variants = generate_cc_variants(current_cc, count=20)
                
                if not cc_variants:
                    await asyncio.sleep(20)
                    continue
                
                commands = await load_commands()
                
                for i in range(0, len(cc_variants), 2):
                    pair = cc_variants[i:i+2]
                    tasks = []
                    
                    for j, cc in enumerate(pair):
                        selected_command = random.choice(commands)
                        message = f"{selected_command} {cc}"
                        
                        async def send_cc(msg, idx):
                            try:
                                await client.send_message('@Alphachekerbot', msg)
                                num = i + idx + 1
                                log_messages.append(f"✓ #{num}/20")
                            except:
                                pass
                        
                        tasks.append(send_cc(message, j))
                    
                    await asyncio.gather(*tasks)
                    await asyncio.sleep(21)
                
                log_messages.append(f"🎉 Lote OK")
            else:
                await asyncio.sleep(20)
        except:
            await asyncio.sleep(20)

async def start_client():
    try:
        log_messages.append("🚀 Iniciando...")
        await client.start()
        log_messages.append("✅ Conectado")
        client.add_event_handler(response_handler, events.MessageEdited(chats='@Alphachekerbot'))
        await asyncio.gather(send_to_bot(), client.run_until_disconnected())
    except:
        pass

def telethon_thread_fn():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_client())

# ============ RUTAS ============

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            return jsonify({'error': 'Usuario y contraseña requeridos'}), 400
        
        if check_brute_force(username):
            return jsonify({'error': 'Cuenta bloqueada'}), 429
        
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute('SELECT id, username, password_hash, is_active FROM users WHERE username = ?', (username,))
            user = c.fetchone()
            conn.close()
            
            if not user or not user['is_active']:
                increment_failed_attempts(username)
                return jsonify({'error': 'Credenciales incorrectas'}), 401
            
            if not check_password_hash(user['password_hash'], password):
                increment_failed_attempts(username)
                return jsonify({'error': 'Credenciales incorrectas'}), 401
            
            reset_failed_attempts(username)
            session['user_id'] = user['id']
            session['username'] = user['username']
            session.permanent = True
            
            conn = get_db()
            c = conn.cursor()
            c.execute('UPDATE users SET last_login = ? WHERE id = ?', (datetime.now().isoformat(), user['id']))
            conn.commit()
            conn.close()
            
            return jsonify({'success': True, 'redirect': url_for('dashboard')})
        except:
            return jsonify({'error': 'Error'}), 500
    
    html = '''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>🔐 SCRAPPER LOGIN</title><style>*{margin:0;padding:0;box-sizing:border-box}body{background:linear-gradient(135deg,#0a0e27 0%,#1a1a3e 50%,#2d1b3d 100%);font-family:Arial,sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center}.login-container{background:rgba(255,20,20,0.08);border:3px solid #ff1414;border-radius:20px;padding:50px;width:100%;max-width:400px;box-shadow:0 0 40px rgba(255,20,20,0.6)}.login-container h1{color:#ff1414;margin-bottom:30px;text-align:center;font-size:2em;text-shadow:0 0 15px rgba(255,20,20,0.6)}.form-group{margin-bottom:20px}.form-group label{display:block;color:#ffaa00;margin-bottom:8px;font-weight:bold}.form-group input{width:100%;padding:12px;background:rgba(0,0,0,0.3);border:2px solid #ff1414;border-radius:8px;color:#fff;font-size:1em}.form-group input:focus{outline:none;border-color:#ffaa00;box-shadow:0 0 15px rgba(255,170,0,0.5)}.login-btn{width:100%;padding:12px;background:linear-gradient(135deg,#ff1414 0%,#cc0000 100%);border:2px solid #ffaa00;border-radius:8px;color:white;font-weight:bold;font-size:1.1em;cursor:pointer;text-transform:uppercase}.login-btn:hover{transform:scale(1.05)}.error-message{color:#ff6b6b;text-align:center;margin-bottom:20px}</style></head><body><div class="login-container"><h1>🔐 SCRAPPER LOGIN</h1><div id="error-msg" class="error-message"></div><form id="login-form"><div class="form-group"><label>👤 Usuario</label><input type="text" id="username" name="username" required></div><div class="form-group"><label>🔑 Contraseña</label><input type="password" id="password" name="password" required></div><button type="submit" class="login-btn">🚀 ENTRAR</button></form></div><script>document.getElementById('login-form').addEventListener('submit',function(e){e.preventDefault();fetch('/login',{method:'POST',body:new FormData(this)}).then(r=>r.json()).then(d=>{if(d.success)window.location.href=d.redirect;else document.getElementById('error-msg').textContent=d.error;});});</script></body></html>'''
    return render_template_string(html)

@app.route('/dashboard')
@login_required
def dashboard():
    html = '''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>SCRAPPER TEAM REDCARDS</title><style>*{margin:0;padding:0;box-sizing:border-box}body{background:linear-gradient(135deg,#0a0e27 0%,#1a1a3e 50%,#2d1b3d 100%);font-family:Arial,sans-serif;color:#fff;min-height:100vh;padding:20px}.container{max-width:1400px;margin:0 auto}.top-bar{display:flex;justify-content:space-between;align-items:center;margin-bottom:30px;padding:15px 25px;background:rgba(255,20,20,0.15);border:2px solid #ff1414;border-radius:15px}.user-info{color:#ffaa00;font-weight:bold}.logout-btn{padding:10px 20px;background:#ff1414;border:none;border-radius:8px;color:white;cursor:pointer;font-weight:bold}.logout-btn:hover{transform:scale(1.05)}.header{text-align:center;margin-bottom:30px;padding:40px;background:rgba(255,20,20,0.15);border:3px solid #ff1414;border-radius:20px}.header h1{font-size:3.5em;color:#ff1414;text-shadow:0 0 20px rgba(255,20,20,0.8)}.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px;margin-bottom:30px}.stat-box{background:rgba(255,20,20,0.1);padding:30px;border-radius:15px;border:2px solid #ff1414;text-align:center}.stat-box h3{color:#ffaa00;margin-bottom:15px}.stat-box .number{font-size:4em;font-weight:900;color:#ff1414}.main-content{display:grid;grid-template-columns:1fr 1fr;gap:20px}.section{background:rgba(255,20,20,0.08);padding:25px;border-radius:15px;border:2px solid #ff1414}.section h2{color:#ffaa00;margin-bottom:20px;font-size:1.8em}.container-box{background:rgba(0,0,0,0.5);padding:15px;border-radius:10px;height:500px;overflow-y:auto;font-family:'Courier New',monospace}.log-entry{padding:8px 0;border-bottom:1px solid rgba(255,20,20,0.2)}.log-entry.success{color:#00ff00}.log-entry.error{color:#ff1414}.log-entry.info{color:#ffaa00}@media(max-width:1200px){.main-content{grid-template-columns:1fr}}</style></head><body><div class="container"><div class="top-bar"><div class="user-info">👤 {{ username }}</div><button class="logout-btn" onclick="location.href='/logout'">🚪 SALIR</button></div><div class="header"><h1>🎮 SCRAPPER TEAM REDCARDS 🔴</h1></div><div class="stats"><div class="stat-box"><h3>✅ LIVES</h3><div class="number" id="approved">0</div></div><div class="stat-box"><h3>❌ DECLINADAS</h3><div class="number" id="declined">0</div></div><div class="stat-box"><h3>💎 GUARDADAS</h3><div class="number" id="lives-count">0</div></div></div><div class="main-content"><div class="section"><h2>🔄 SCRAPPER</h2><div class="container-box" id="scrapper"></div></div><div class="section"><h2>💎 LIVES</h2><div class="container-box" id="lives"></div></div></div></div><script>function update(){fetch('/get_logs').then(r=>r.json()).then(d=>{document.getElementById('scrapper').innerHTML=d.log.split('\\n').map(l=>{let c='info';if(l.includes('✓')||l.includes('✅'))c='success';else if(l.includes('❌'))c='error';return`<div class="log-entry ${c}">${l}</div>`;}).join('');document.getElementById('approved').textContent=d.approved;document.getElementById('declined').textContent=d.declined;});fetch('/get_lives').then(r=>r.json()).then(d=>{document.getElementById('lives-count').textContent=d.lives.length;document.getElementById('lives').innerHTML=d.lives.map(l=>`<div class="log-entry info">💳 ${l.cc} | ${l.bank} | ${l.timestamp}</div>`).join('');});}setInterval(update,3000);update();</script></body></html>'''
    return render_template_string(html, username=session.get('username'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/secret/<secret_url>/owner_login', methods=['GET', 'POST'])
def owner_login(secret_url):
    owner_config = get_owner_config()
    
    if not owner_config or secret_url != owner_config.get('secret_url'):
        return "NOT FOUND", 404
    
    if request.method == 'POST':
        # LEER DATOS DEL FORMULARIO - CON name= correcto
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        print(f"\n[DEBUG] POST Recibido")
        print(f"[DEBUG] Username input: '{username}'")
        print(f"[DEBUG] Password input: '{password}'")
        print(f"[DEBUG] Config username: '{owner_config.get('username')}'")
        print(f"[DEBUG] Config password: '{owner_config.get('password')}'")
        
        # COMPARACIÓN EXACTA
        if username == owner_config.get('username') and password == owner_config.get('password'):
            print(f"[SUCCESS] ✅ Login exitoso!")
            session['owner_authenticated'] = True
            session['owner_secret_url'] = secret_url
            session.permanent = True
            
            return jsonify({'success': True, 'redirect': url_for('owner_panel', secret_url=secret_url)})
        else:
            print(f"[ERROR] ❌ Credenciales no coinciden")
            if username != owner_config.get('username'):
                print(f"[ERROR] Usuario no coincide: '{username}' != '{owner_config.get('username')}'")
            if password != owner_config.get('password'):
                print(f"[ERROR] Contraseña no coincide: '{password}' != '{owner_config.get('password')}'")
            
            return jsonify({'error': 'Credenciales INCORRECTAS'}), 401
    
    html = '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>🔐 OWNER ACCESS</title><style>*{margin:0;padding:0;box-sizing:border-box}body{background:linear-gradient(135deg,#0a0e27 0%,#1a1a3e 50%,#2d1b3d 100%);font-family:Arial,sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center}.login-container{background:rgba(20,20,255,0.08);border:3px solid #1414ff;border-radius:20px;padding:50px;width:100%;max-width:400px;box-shadow:0 0 40px rgba(20,20,255,0.6)}.login-container h1{color:#00aaff;margin-bottom:30px;text-align:center;font-size:2em;text-shadow:0 0 15px rgba(0,170,255,0.6)}.form-group{margin-bottom:20px}.form-group label{display:block;color:#00aaff;margin-bottom:8px;font-weight:bold}.form-group input{width:100%;padding:12px;background:rgba(0,0,0,0.3);border:2px solid #1414ff;border-radius:8px;color:#fff}.form-group input:focus{outline:none;border-color:#00aaff;box-shadow:0 0 15px rgba(0,170,255,0.5)}.login-btn{width:100%;padding:12px;background:linear-gradient(135deg,#1414ff 0%,#0000cc 100%);border:2px solid #00aaff;border-radius:8px;color:white;font-weight:bold;cursor:pointer;text-transform:uppercase}.login-btn:hover{transform:scale(1.05)}.error-message{color:#ff6b6b;text-align:center;margin-bottom:20px}</style></head><body><div class="login-container"><h1>🔐 OWNER PANEL</h1><div id="error-msg" class="error-message"></div><div style="margin-bottom:20px;padding:15px;background:rgba(0,255,0,0.1);border:1px solid #00ff00;border-radius:8px;color:#00ff00;font-size:0.9em"><strong>ℹ️ Credenciales:</strong><br>Usuario: admin<br>Contraseña: ChangeMe123!@#</div><form id="owner-form" name="owner-form"><div class="form-group"><label>👤 Usuario</label><input type="text" name="username" id="username" required></div><div class="form-group"><label>🔑 Contraseña</label><input type="password" name="password" id="password" required></div><button type="submit" class="login-btn">⚙️ ACCESO OWNER</button></form></div><script>document.getElementById('owner-form').addEventListener('submit',function(e){e.preventDefault();const form=this;const username=document.getElementById('username').value;const password=document.getElementById('password').value;console.log('Enviando:',{username,password});fetch(window.location.href,{method:'POST',body:new FormData(form)}).then(r=>r.json()).then(d=>{console.log('Response:',d);if(d.success){window.location.href=d.redirect;}else{document.getElementById('error-msg').textContent='❌ '+d.error;}}).catch(e=>{console.error('Error:',e);document.getElementById('error-msg').textContent='❌ Error en la solicitud';});});</script></body></html>'''
    return render_template_string(html)

@app.route('/secret/<secret_url>/owner_panel')
def owner_panel(secret_url):
    if 'owner_authenticated' not in session or session.get('owner_secret_url') != secret_url:
        return redirect(url_for('owner_login', secret_url=secret_url))
    
    owner_config = get_owner_config()
    if not owner_config or secret_url != owner_config.get('secret_url'):
        return "NOT FOUND", 404
    
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT id, username, email, is_active, created_at FROM users')
        users = c.fetchall()
        conn.close()
    except:
        users = []
    
    html = '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>🛡️ OWNER PANEL</title><style>*{margin:0;padding:0;box-sizing:border-box}body{background:linear-gradient(135deg,#0a0e27 0%,#1a1a3e 50%,#2d1b3d 100%);font-family:Arial,sans-serif;color:#fff;min-height:100vh;padding:20px}.container{max-width:1200px;margin:0 auto}.top-bar{margin-bottom:30px;padding:20px 25px;background:rgba(20,20,255,0.15);border:2px solid #1414ff;border-radius:15px;display:flex;justify-content:space-between}.top-bar h2{color:#00aaff}.logout-btn{padding:10px 20px;background:#ff1414;border:none;border-radius:8px;color:white;cursor:pointer;font-weight:bold}.header{text-align:center;margin-bottom:30px;padding:30px;background:rgba(20,20,255,0.15);border:2px solid #1414ff;border-radius:15px}.header h1{color:#00aaff;font-size:2.5em;text-shadow:0 0 15px rgba(0,170,255,0.6)}.create-user{background:rgba(20,20,255,0.1);padding:25px;border-radius:15px;border:2px solid #1414ff;margin-bottom:30px}.form-row{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:10px}.form-group{margin-bottom:15px}.form-group label{display:block;color:#00aaff;margin-bottom:5px;font-weight:bold}.form-group input,.form-group select{width:100%;padding:10px;background:rgba(0,0,0,0.3);border:2px solid #1414ff;border-radius:8px;color:#fff}.submit-btn{padding:10px 20px;background:#00ff00;border:none;border-radius:8px;color:#000;font-weight:bold;cursor:pointer}.users-table{width:100%;border-collapse:collapse;background:rgba(0,0,0,0.3);border-radius:10px;overflow:hidden}.users-table th{background:rgba(20,20,255,0.3);color:#00aaff;padding:15px;text-align:left;border-bottom:2px solid #1414ff}.users-table td{padding:15px;border-bottom:1px solid rgba(20,20,255,0.2)}.users-table tr:hover{background:rgba(20,20,255,0.1)}.btn{padding:8px 12px;margin-right:5px;border:none;border-radius:5px;cursor:pointer;font-weight:bold}.edit-btn{background:#1414ff;color:white}.delete-btn{background:#ff1414;color:white}.toggle-btn{background:#ffaa00;color:#000}</style></head><body><div class="container"><div class="top-bar"><h2>🛡️ OWNER PANEL</h2><button class="logout-btn" onclick="location.href='/secret/{{ secret_url }}/owner_logout'">🚪 SALIR</button></div><div class="header"><h1>Gestión TOTAL de Usuarios VIP</h1></div><div class="create-user"><h3 style="color:#00aaff;margin-bottom:20px;">➕ CREAR USUARIO VIP</h3><div class="form-row"><div class="form-group"><label>Usuario</label><input type="text" id="new-username" placeholder="usuario"></div><div class="form-group"><label>Email</label><input type="email" id="new-email" placeholder="email@vip.com"></div><div class="form-group"><label>Contraseña</label><input type="password" id="new-password" placeholder="Contraseña"></div><div class="form-group"><label>Rol</label><select id="new-role"><option value="user">User VIP</option></select></div></div><button class="submit-btn" onclick="createUser()" style="margin-top:15px;">✅ CREAR VIP</button></div><h3 style="color:#00aaff;margin-bottom:15px;">👥 USUARIOS</h3><table class="users-table"><thead><tr><th>Usuario</th><th>Email</th><th>Estado</th><th>Creado</th><th>Acciones</th></tr></thead><tbody>{% for user in users %}<tr><td>{{ user.username }}</td><td>{{ user.email }}</td><td style="color:{% if user.is_active %}#00ff00{% else %}#ff1414{% endif %}">{% if user.is_active %}✅ Activo{% else %}❌ Inactivo{% endif %}</td><td>{{ user.created_at[:10] if user.created_at else "N/A" }}</td><td><button class="btn toggle-btn" onclick="toggleUser({{ user.id }})">🔄</button><button class="btn edit-btn" onclick="editUser({{ user.id }})">✏️</button><button class="btn delete-btn" onclick="deleteUser({{ user.id }})">🗑️</button></td></tr>{% endfor %}</tbody></table></div><script>function createUser(){fetch('/api/owner/users/create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:document.getElementById('new-username').value,email:document.getElementById('new-email').value,password:document.getElementById('new-password').value,role:document.getElementById('new-role').value})}).then(r=>r.json()).then(d=>{alert(d.success?'✅ Creado':'❌ '+d.error);if(d.success)location.reload();});}function deleteUser(id){if(confirm('¿Eliminar?')){fetch('/api/owner/users/delete/'+id,{method:'POST'}).then(r=>r.json()).then(d=>{alert(d.success?'✅ Eliminado':'❌ Error');if(d.success)location.reload();});}}function toggleUser(id){fetch('/api/owner/users/toggle/'+id,{method:'POST'}).then(r=>r.json()).then(d=>{alert(d.success?'✅ Actualizado':'❌ Error');if(d.success)location.reload();});}function editUser(id){const pass=prompt('Nueva contraseña:');if(pass){fetch('/api/owner/users/edit/'+id,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:pass})}).then(r=>r.json()).then(d=>{alert(d.success?'✅ Actualizado':'❌ Error');if(d.success)location.reload();});}}</script></body></html>'''
    return render_template_string(html, secret_url=secret_url, users=users)

@app.route('/secret/<secret_url>/owner_logout')
def owner_logout(secret_url):
    session.clear()
    return redirect(url_for('login'))

# ============ APIs OWNER ============

@app.route('/api/owner/users/create', methods=['POST'])
def owner_api_create():
    if 'owner_authenticated' not in session:
        return jsonify({'error': 'No autenticado'}), 401
    
    data = request.get_json()
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    
    if not all([username, email, password]) or len(password) < 8:
        return jsonify({'error': 'Datos inválidos'}), 400
    
    try:
        conn = get_db()
        c = conn.cursor()
        password_hash = generate_password_hash(password)
        c.execute('INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)',
                 (username, email, password_hash, 'user'))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except:
        return jsonify({'error': 'Usuario o email existe'}), 400

@app.route('/api/owner/users/delete/<int:user_id>', methods=['POST'])
def owner_api_delete(user_id):
    if 'owner_authenticated' not in session:
        return jsonify({'error': 'No autenticado'}), 401
    
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except:
        return jsonify({'error': 'Error'}), 400

@app.route('/api/owner/users/toggle/<int:user_id>', methods=['POST'])
def owner_api_toggle(user_id):
    if 'owner_authenticated' not in session:
        return jsonify({'error': 'No autenticado'}), 401
    
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT is_active FROM users WHERE id = ?', (user_id,))
        user = c.fetchone()
        if user:
            c.execute('UPDATE users SET is_active = ? WHERE id = ?', (1 - user['is_active'], user_id))
            conn.commit()
        conn.close()
        return jsonify({'success': True})
    except:
        return jsonify({'error': 'Error'}), 400

@app.route('/api/owner/users/edit/<int:user_id>', methods=['POST'])
def owner_api_edit(user_id):
    if 'owner_authenticated' not in session:
        return jsonify({'error': 'No autenticado'}), 401
    
    data = request.get_json()
    password = data.get('password', '')
    
    if not password or len(password) < 8:
        return jsonify({'error': 'Contraseña inválida'}), 400
    
    try:
        conn = get_db()
        c = conn.cursor()
        password_hash = generate_password_hash(password)
        c.execute('UPDATE users SET password_hash = ? WHERE id = ?', (password_hash, user_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except:
        return jsonify({'error': 'Error'}), 400

# ============ APIs PÚBLICAS ============

@app.route('/get_logs')
@login_required
def get_logs():
    return jsonify({"log": '\n'.join(log_messages[-50:]), "approved": approved_count, "declined": declined_count})

@app.route('/get_lives')
@login_required
def get_lives():
    return jsonify({"lives": lives_list})

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

# ============ INICIO ============

if __name__ == '__main__':
    init_db()
    init_owner_config()
    load_lives_from_file()
    
    telethon_thread = threading.Thread(target=telethon_thread_fn, daemon=True)
    telethon_thread.start()
    time.sleep(2)
    
    app.run('0.0.0.0', PORT, debug=False)
