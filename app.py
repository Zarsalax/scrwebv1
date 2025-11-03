import threading
import asyncio
import random
import time
import os
import json
import sqlite3
import secrets
import hashlib
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

PORT = int(os.environ.get('PORT', 5000))

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
log_messages = []
lives_list = []
channelid = -1003101739772
approved_count = 0
declined_count = 0
app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

LIVES_FILE = 'lives_database.json'
DB_FILE = 'users.db'
OWNER_SECRET_FILE = '.owner_secret.json'  # Archivo secreto OCULTO

# ============ CONFIGURAR CREDENCIALES OWNER ============

def setup_owner_credentials():
    """Configura credenciales OWNER ultra secretas"""
    if not os.path.exists(OWNER_SECRET_FILE):
        # Generar valores por defecto SUPER SEGUROS
        owner_config = {
            "secret_url": secrets.token_urlsafe(32),  # URL secreta aleatoria
            "username": "admin",
            "password_hash": generate_password_hash("ChangeMe123!@#"),  # CAMBIAR INMEDIATAMENTE
            "created_at": datetime.now().isoformat()
        }
        
        try:
            with open(OWNER_SECRET_FILE, 'w') as f:
                json.dump(owner_config, f)
            os.chmod(OWNER_SECRET_FILE, 0o600)  # Solo lectura para owner
        except:
            pass

def get_owner_secret():
    """Obtiene las credenciales OWNER"""
    try:
        with open(OWNER_SECRET_FILE, 'r') as f:
            return json.load(f)
    except:
        return None

def update_owner_password(new_password):
    """Actualiza contraseña OWNER"""
    try:
        secret = get_owner_secret()
        if secret:
            secret['password_hash'] = generate_password_hash(new_password)
            with open(OWNER_SECRET_FILE, 'w') as f:
                json.dump(secret, f)
            os.chmod(OWNER_SECRET_FILE, 0o600)
            return True
    except:
        pass
    return False

# ============ BASE DE DATOS ============

def init_db():
    """Inicializa la base de datos"""
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
    
    c.execute('''CREATE TABLE IF NOT EXISTS login_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        ip_address TEXT NOT NULL,
        status TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    conn.commit()
    conn.close()

def get_db():
    """Obtiene conexión a base de datos"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def log_login_attempt(username, ip, status):
    """Registra intentos de login"""
    conn = get_db()
    c = conn.cursor()
    c.execute('INSERT INTO login_logs (username, ip_address, status) VALUES (?, ?, ?)',
             (username, ip, status))
    conn.commit()
    conn.close()

def check_brute_force(username):
    """Verifica si el usuario está bloqueado"""
    conn = get_db()
    c = conn.cursor()
    
    c.execute('SELECT failed_attempts, locked_until FROM users WHERE username = ?', (username,))
    user = c.fetchone()
    conn.close()
    
    if not user:
        return False
    
    if user['locked_until']:
        locked_time = datetime.fromisoformat(user['locked_until'])
        if datetime.now() < locked_time:
            return True
    
    return False

def increment_failed_attempts(username):
    """Incrementa intentos fallidos"""
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
            c.execute('UPDATE users SET failed_attempts = ? WHERE username = ?',
                     (new_attempts, username))
        
        conn.commit()
    
    conn.close()

def reset_failed_attempts(username):
    """Reinicia los intentos fallidos"""
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE username = ?', (username,))
    conn.commit()
    conn.close()

# ============ CARGAR LIVES ============

def load_lives_from_file():
    """Carga lives guardadas"""
    global lives_list
    if os.path.exists(LIVES_FILE):
        try:
            with open(LIVES_FILE, 'r', encoding='utf-8') as f:
                lives_list = json.load(f)
                log_messages.append(f"✅ Cargadas {len(lives_list)} LIVES")
        except:
            lives_list = []

def save_lives_to_file():
    """Guarda lives"""
    try:
        with open(LIVES_FILE, 'w', encoding='utf-8') as f:
            json.dump(lives_list, f, indent=2, ensure_ascii=False)
    except:
        pass

# ============ DECORADORES ============

def login_required(f):
    """Protege rutas normales"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def owner_required(f):
    """Protege rutas OWNER secretas"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'owner_authenticated' not in session or not session['owner_authenticated']:
            return redirect(url_for('owner_login'))
        return f(*args, **kwargs)
    return decorated_function

# ============ FUNCIONES UTILITARIAS ============

def luhn_checksum(card_number):
    """Calcula checksum de Luhn"""
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
    """Genera dígito Luhn"""
    check_digit = luhn_checksum(str(partial_card) + '0')
    return (10 - check_digit) % 10

def is_date_valid(month, year):
    """Verifica fecha válida"""
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
    """Genera fecha aleatoria válida"""
    now = datetime.now()
    days_ahead = random.randint(0, 365 * 5)
    future_date = now + timedelta(days=days_ahead)
    month = f"{future_date.month:02d}"
    year = f"{future_date.year}"
    return month, year

def generate_cc_variants(ccbase, count=20):
    """Genera 20 variantes con Luhn"""
    if ',' in ccbase:
        separator = ','
    elif '|' in ccbase:
        separator = '|'
    else:
        log_messages.append(f"❌ Formato desconocido")
        return []
    
    parts = ccbase.strip().split(separator)
    
    if len(parts) >= 4:
        cardnumber = parts[0]
        month = parts[1]
        year = parts[2]
        cvv = parts[3]
    else:
        log_messages.append(f"❌ Formato inválido")
        return []
    
    if len(cardnumber) < 12:
        log_messages.append(f"❌ Tarjeta muy corta")
        return []
    
    date_is_valid = is_date_valid(month, year)
    variants = []
    
    if not date_is_valid:
        log_messages.append(f"⚠️ Fecha vencida: {month}/{year}")
        month, year = generate_random_valid_date()
        log_messages.append(f"⚠️ Fecha actualizada: {month}/{year}")
        
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
        
        log_messages.append(f"✅ Generadas 20 CCs")
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
        
        log_messages.append(f"✅ Generadas 20 CCs")
    
    return variants

# ============ MANEJADOR DE EVENTOS ============

async def response_handler(event):
    """Maneja respuestas del bot"""
    global approved_count, declined_count, channelid, lives_list
    
    full_message = event.message.message if event.message.message else ""
    message_lower = full_message.lower()
    
    if "✅" in full_message or "approved" in message_lower:
        approved_count += 1
        
        lines = full_message.split('\n')
        cc_number = status = response = country = bank = card_type = gate = ""
        
        for line in lines:
            if 'cc:' in line.lower():
                cc_number = line.split(':', 1)[1].strip() if len(line.split(':', 1)) > 1 else ""
            elif 'status:' in line.lower():
                status = line.split(':', 1)[1].strip() if len(line.split(':', 1)) > 1 else ""
            elif 'response:' in line.lower():
                response = line.split(':', 1)[1].strip() if len(line.split(':', 1)) > 1 else ""
            elif 'country:' in line.lower():
                country = line.split(':', 1)[1].strip() if len(line.split(':', 1)) > 1 else ""
            elif 'bank:' in line.lower():
                bank = line.split(':', 1)[1].strip() if len(line.split(':', 1)) > 1 else ""
            elif 'type:' in line.lower():
                card_type = line.split(':', 1)[1].strip() if len(line.split(':', 1)) > 1 else ""
            elif 'gate:' in line.lower():
                gate = line.split(':', 1)[1].strip() if len(line.split(':', 1)) > 1 else ""
        
        log_messages.append(f"✅ LIVE ENCONTRADA: {cc_number[:12]}...")
        
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
        
        try:
            image_path = 'x1.jpg'
            
            if os.path.exists(image_path):
                await client.send_file(channelid, image_path, caption=formatted_message, parse_mode='markdown')
            else:
                await client.send_message(channelid, formatted_message, parse_mode='markdown')
        except:
            pass
    
    elif "❌" in full_message or "declined" in message_lower:
        declined_count += 1
        log_messages.append(f"❌ DECLINADA")
    
    if len(log_messages) > 100:
        log_messages.pop(0)

# ============ FUNCIONES DE ENVÍO ============

async def load_commands():
    """Carga comandos"""
    try:
        if os.path.exists('cmds.txt'):
            with open('cmds.txt', 'r', encoding='utf-8') as f:
                cmds = [line.strip() for line in f.readlines() if line.strip()]
                if cmds:
                    return cmds
        return ['/check', '/validate', '/test']
    except:
        return ['/check']

async def send_to_bot():
    """Envía CCs al bot"""
    while True:
        try:
            if not os.path.exists('ccs.txt'):
                await asyncio.sleep(30)
                continue
            
            with open('ccs.txt', 'r', encoding='utf-8') as f:
                ccs_list = f.readlines()
            
            if ccs_list:
                current_cc = ccs_list[0].strip()
                
                if len(ccs_list) > 1:
                    with open('ccs.txt', 'w', encoding='utf-8') as f:
                        f.writelines(ccs_list[1:])
                else:
                    with open('ccs.txt', 'w', encoding='utf-8') as f:
                        f.write("")
                
                log_messages.append(f"🔄 Procesando BIN: {current_cc[:12]}...")
                
                cc_variants = generate_cc_variants(current_cc, count=20)
                
                if not cc_variants:
                    log_messages.append(f"❌ Error")
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
                            except FloodWaitError as e:
                                await asyncio.sleep(e.seconds)
                            except:
                                pass
                        
                        tasks.append(send_cc(message, j))
                    
                    await asyncio.gather(*tasks)
                    await asyncio.sleep(21)
                
                log_messages.append(f"🎉 Lote completado")
            else:
                await asyncio.sleep(20)
        
        except:
            await asyncio.sleep(20)

async def start_client():
    """Inicia cliente Telegram"""
    try:
        log_messages.append("🚀 Iniciando...")
        await client.start()
        log_messages.append("✅ Conectado")
        
        client.add_event_handler(response_handler, events.MessageEdited(chats='@Alphachekerbot'))
        
        await asyncio.gather(send_to_bot(), client.run_until_disconnected())
    except:
        pass

def telethon_thread_fn():
    """Thread de Telegram"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_client())

# ============ RUTAS LOGIN NORMAL ============

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login normal para usuarios"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        ip_address = request.remote_addr
        
        if not username or not password:
            return jsonify({'error': 'Usuario y contraseña requeridos'}), 400
        
        if check_brute_force(username):
            log_login_attempt(username, ip_address, 'BLOCKED')
            return jsonify({'error': 'Cuenta bloqueada'}), 429
        
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT id, username, password_hash, is_active FROM users WHERE username = ?', (username,))
        user = c.fetchone()
        conn.close()
        
        if not user:
            increment_failed_attempts(username)
            log_login_attempt(username, ip_address, 'INVALID_USER')
            return jsonify({'error': 'Usuario o contraseña incorrectos'}), 401
        
        if not user['is_active']:
            log_login_attempt(username, ip_address, 'INACTIVE')
            return jsonify({'error': 'Usuario inactivo'}), 401
        
        if not check_password_hash(user['password_hash'], password):
            increment_failed_attempts(username)
            log_login_attempt(username, ip_address, 'INVALID_PASSWORD')
            return jsonify({'error': 'Usuario o contraseña incorrectos'}), 401
        
        reset_failed_attempts(username)
        
        conn = get_db()
        c = conn.cursor()
        c.execute('UPDATE users SET last_login = ? WHERE id = ?', (datetime.now().isoformat(), user['id']))
        conn.commit()
        conn.close()
        
        session['user_id'] = user['id']
        session['username'] = user['username']
        
        log_login_attempt(username, ip_address, 'SUCCESS')
        
        return jsonify({'success': True, 'redirect': url_for('dashboard')})
    
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🔐 SCRAPPER LOGIN</title>
        <style>
            * {margin: 0; padding: 0; box-sizing: border-box;}
            body {
                background: linear-gradient(135deg, #0a0e27 0%, #1a1a3e 50%, #2d1b3d 100%);
                font-family: Arial, sans-serif;
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .login-container {
                background: rgba(255, 20, 20, 0.08);
                border: 3px solid #ff1414;
                border-radius: 20px;
                padding: 50px;
                width: 100%;
                max-width: 400px;
                box-shadow: 0 0 40px rgba(255, 20, 20, 0.6);
            }
            .login-container h1 {
                color: #ff1414;
                margin-bottom: 30px;
                text-align: center;
                font-size: 2em;
                text-shadow: 0 0 15px rgba(255, 20, 20, 0.6);
            }
            .form-group {margin-bottom: 20px;}
            .form-group label {
                display: block;
                color: #ffaa00;
                margin-bottom: 8px;
                font-weight: bold;
            }
            .form-group input {
                width: 100%;
                padding: 12px;
                background: rgba(0, 0, 0, 0.3);
                border: 2px solid #ff1414;
                border-radius: 8px;
                color: #fff;
                font-size: 1em;
            }
            .form-group input:focus {
                outline: none;
                border-color: #ffaa00;
                box-shadow: 0 0 15px rgba(255, 170, 0, 0.5);
            }
            .login-btn {
                width: 100%;
                padding: 12px;
                background: linear-gradient(135deg, #ff1414 0%, #cc0000 100%);
                border: 2px solid #ffaa00;
                border-radius: 8px;
                color: white;
                font-weight: bold;
                font-size: 1.1em;
                cursor: pointer;
                transition: all 0.3s ease;
                text-transform: uppercase;
            }
            .login-btn:hover {
                transform: scale(1.05);
                box-shadow: 0 0 20px rgba(255, 170, 0, 0.8);
            }
            .error-message {
                color: #ff6b6b;
                text-align: center;
                margin-bottom: 20px;
            }
        </style>
    </head>
    <body>
        <div class="login-container">
            <h1>🔐 SCRAPPER LOGIN</h1>
            <div id="error-msg" class="error-message"></div>
            <form id="login-form">
                <div class="form-group">
                    <label>👤 Usuario</label>
                    <input type="text" id="username" name="username" required autocomplete="off">
                </div>
                <div class="form-group">
                    <label>🔑 Contraseña</label>
                    <input type="password" id="password" name="password" required autocomplete="off">
                </div>
                <button type="submit" class="login-btn">🚀 ENTRAR</button>
            </form>
        </div>
        
        <script>
            document.getElementById('login-form').addEventListener('submit', function(e) {
                e.preventDefault();
                const formData = new FormData(this);
                fetch('/login', {method: 'POST', body: formData})
                    .then(r => r.json())
                    .then(data => {
                        if (data.success) window.location.href = data.redirect;
                        else document.getElementById('error-msg').textContent = data.error;
                    });
            });
        </script>
    </body>
    </html>
    '''
    return render_template_string(html)

@app.route('/logout')
def logout():
    """Cerrar sesión normal"""
    session.clear()
    return redirect(url_for('login'))

# ============ RUTAS OWNER SECRETAS ============

@app.route('/secret/<secret_url>/owner_login', methods=['GET', 'POST'])
def owner_login(secret_url):
    """Login OWNER ULTRA SECRETO"""
    owner_secret = get_owner_secret()
    
    if not owner_secret or secret_url != owner_secret['secret_url']:
        return "NOT FOUND", 404
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if username != owner_secret['username']:
            return jsonify({'error': 'Credenciales incorrectas'}), 401
        
        if not check_password_hash(owner_secret['password_hash'], password):
            return jsonify({'error': 'Credenciales incorrectas'}), 401
        
        session['owner_authenticated'] = True
        session['owner_secret_url'] = secret_url
        
        return jsonify({'success': True, 'redirect': url_for('owner_panel', secret_url=secret_url)})
    
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>🔐 OWNER ACCESS</title>
        <style>
            * {margin: 0; padding: 0; box-sizing: border-box;}
            body {
                background: linear-gradient(135deg, #0a0e27 0%, #1a1a3e 50%, #2d1b3d 100%);
                font-family: Arial, sans-serif;
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .login-container {
                background: rgba(20, 20, 255, 0.08);
                border: 3px solid #1414ff;
                border-radius: 20px;
                padding: 50px;
                width: 100%;
                max-width: 400px;
                box-shadow: 0 0 40px rgba(20, 20, 255, 0.6);
            }
            .login-container h1 {
                color: #00aaff;
                margin-bottom: 30px;
                text-align: center;
                font-size: 2em;
                text-shadow: 0 0 15px rgba(0, 170, 255, 0.6);
            }
            .form-group {margin-bottom: 20px;}
            .form-group label {
                display: block;
                color: #00aaff;
                margin-bottom: 8px;
                font-weight: bold;
            }
            .form-group input {
                width: 100%;
                padding: 12px;
                background: rgba(0, 0, 0, 0.3);
                border: 2px solid #1414ff;
                border-radius: 8px;
                color: #fff;
            }
            .form-group input:focus {
                outline: none;
                border-color: #00aaff;
                box-shadow: 0 0 15px rgba(0, 170, 255, 0.5);
            }
            .login-btn {
                width: 100%;
                padding: 12px;
                background: linear-gradient(135deg, #1414ff 0%, #0000cc 100%);
                border: 2px solid #00aaff;
                border-radius: 8px;
                color: white;
                font-weight: bold;
                cursor: pointer;
                text-transform: uppercase;
            }
            .login-btn:hover {
                transform: scale(1.05);
                box-shadow: 0 0 20px rgba(0, 170, 255, 0.8);
            }
            .error-message {
                color: #ff6b6b;
                text-align: center;
                margin-bottom: 20px;
            }
        </style>
    </head>
    <body>
        <div class="login-container">
            <h1>🔐 OWNER PANEL</h1>
            <div id="error-msg" class="error-message"></div>
            <form id="login-form">
                <div class="form-group">
                    <label>👤 Usuario</label>
                    <input type="text" id="username" name="username" required autocomplete="off">
                </div>
                <div class="form-group">
                    <label>🔑 Contraseña</label>
                    <input type="password" id="password" name="password" required autocomplete="off">
                </div>
                <button type="submit" class="login-btn">⚙️ ACCESO OWNER</button>
            </form>
        </div>
        
        <script>
            document.getElementById('login-form').addEventListener('submit', function(e) {
                e.preventDefault();
                const formData = new FormData(this);
                fetch('', {method: 'POST', body: formData})
                    .then(r => r.json())
                    .then(data => {
                        if (data.success) window.location.href = data.redirect;
                        else document.getElementById('error-msg').textContent = data.error;
                    });
            });
        </script>
    </body>
    </html>
    '''
    return render_template_string(html)

@app.route('/secret/<secret_url>/owner_panel')
@owner_required
def owner_panel(secret_url):
    """Panel OWNER ULTRA SECRETO"""
    owner_secret = get_owner_secret()
    
    if not owner_secret or secret_url != owner_secret['secret_url']:
        return "NOT FOUND", 404
    
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT id, username, email, is_active, created_at, last_login FROM users')
    users = c.fetchall()
    conn.close()
    
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>🛡️ OWNER PANEL SECRETO</title>
        <style>
            * {margin: 0; padding: 0; box-sizing: border-box;}
            body {
                background: linear-gradient(135deg, #0a0e27 0%, #1a1a3e 50%, #2d1b3d 100%);
                font-family: Arial, sans-serif;
                color: #fff;
                min-height: 100vh;
                padding: 20px;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
            }
            .top-bar {
                margin-bottom: 30px;
                padding: 20px 25px;
                background: linear-gradient(135deg, rgba(20, 20, 255, 0.15) 0%, rgba(0, 0, 139, 0.1) 100%);
                border: 2px solid #1414ff;
                border-radius: 15px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .top-bar h2 {
                color: #00aaff;
                font-size: 1.8em;
                text-shadow: 0 0 10px rgba(0, 170, 255, 0.6);
            }
            .logout-btn {
                padding: 10px 20px;
                background: linear-gradient(135deg, #ff1414 0%, #cc0000 100%);
                border: 2px solid #ffaa00;
                border-radius: 8px;
                color: white;
                cursor: pointer;
                font-weight: bold;
            }
            .header {
                text-align: center;
                margin-bottom: 30px;
                padding: 30px;
                background: linear-gradient(135deg, rgba(20, 20, 255, 0.15) 0%, rgba(0, 0, 139, 0.1) 100%);
                border: 2px solid #1414ff;
                border-radius: 15px;
            }
            .header h1 {
                color: #00aaff;
                font-size: 2.5em;
                text-shadow: 0 0 15px rgba(0, 170, 255, 0.6);
            }
            .create-user {
                background: linear-gradient(135deg, rgba(20, 20, 255, 0.1) 0%, rgba(0, 0, 139, 0.05) 100%);
                padding: 25px;
                border-radius: 15px;
                border: 2px solid #1414ff;
                margin-bottom: 30px;
            }
            .form-group {margin-bottom: 15px;}
            .form-group label {
                display: block;
                color: #00aaff;
                margin-bottom: 5px;
                font-weight: bold;
            }
            .form-group input, .form-group select {
                width: 100%;
                padding: 10px;
                background: rgba(0, 0, 0, 0.3);
                border: 2px solid #1414ff;
                border-radius: 8px;
                color: #fff;
            }
            .form-row {
                display: grid;
                grid-template-columns: 1fr 1fr 1fr 1fr;
                gap: 10px;
            }
            .submit-btn {
                padding: 10px 20px;
                background: linear-gradient(135deg, #00ff00 0%, #00cc00 100%);
                border: none;
                border-radius: 8px;
                color: #000;
                font-weight: bold;
                cursor: pointer;
            }
            .users-table {
                width: 100%;
                border-collapse: collapse;
                background: rgba(0, 0, 0, 0.3);
                border-radius: 10px;
                overflow: hidden;
            }
            .users-table th {
                background: rgba(20, 20, 255, 0.3);
                color: #00aaff;
                padding: 15px;
                text-align: left;
                border-bottom: 2px solid #1414ff;
            }
            .users-table td {
                padding: 15px;
                border-bottom: 1px solid rgba(20, 20, 255, 0.2);
            }
            .users-table tr:hover {
                background: rgba(20, 20, 255, 0.1);
            }
            .edit-btn, .delete-btn, .toggle-btn {
                padding: 8px 12px;
                margin-right: 5px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-weight: bold;
            }
            .edit-btn {
                background: #1414ff;
                color: white;
            }
            .delete-btn {
                background: #ff1414;
                color: white;
            }
            .toggle-btn {
                background: #ffaa00;
                color: #000;
            }
            .status-active {
                color: #00ff00;
            }
            .status-inactive {
                color: #ff1414;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="top-bar">
                <h2>🛡️ OWNER PANEL SECRETO</h2>
                <button class="logout-btn" onclick="window.location.href='/secret/{{ secret_url }}/owner_logout'">🚪 SALIR OWNER</button>
            </div>
            
            <div class="header">
                <h1>Gestión TOTAL de Usuarios VIP</h1>
            </div>
            
            <div class="create-user">
                <h3 style="color: #00aaff; margin-bottom: 20px;">➕ CREAR USUARIO VIP</h3>
                <div class="form-row">
                    <div class="form-group">
                        <label>Usuario</label>
                        <input type="text" id="new-username" placeholder="usuario">
                    </div>
                    <div class="form-group">
                        <label>Email</label>
                        <input type="email" id="new-email" placeholder="email@vip.com">
                    </div>
                    <div class="form-group">
                        <label>Contraseña</label>
                        <input type="password" id="new-password" placeholder="Contraseña fuerte">
                    </div>
                    <div class="form-group">
                        <label>Rol</label>
                        <select id="new-role">
                            <option value="user">User VIP</option>
                        </select>
                    </div>
                </div>
                <button class="submit-btn" onclick="createUser()" style="margin-top: 15px;">✅ CREAR VIP</button>
            </div>
            
            <h3 style="color: #00aaff; margin-bottom: 15px;">👥 USUARIOS REGISTRADOS</h3>
            <table class="users-table">
                <thead>
                    <tr>
                        <th>Usuario</th>
                        <th>Email</th>
                        <th>Estado</th>
                        <th>Creado</th>
                        <th>Último Login</th>
                        <th>Acciones</th>
                    </tr>
                </thead>
                <tbody>
                    {% for user in users %}
                    <tr>
                        <td>{{ user.username }}</td>
                        <td>{{ user.email }}</td>
                        <td>
                            <span class="status-{% if user.is_active %}active{% else %}inactive{% endif %}">
                                {% if user.is_active %}✅ Activo{% else %}❌ Inactivo{% endif %}
                            </span>
                        </td>
                        <td>{{ user.created_at[:10] }}</td>
                        <td>{{ user.last_login[:10] if user.last_login else 'Nunca' }}</td>
                        <td>
                            <button class="toggle-btn" onclick="toggleUser({{ user.id }})">🔄 Estado</button>
                            <button class="edit-btn" onclick="editUser({{ user.id }})">✏️ Pass</button>
                            <button class="delete-btn" onclick="deleteUser({{ user.id }})">🗑️ Eliminar</button>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        
        <script>
            function createUser() {
                const username = document.getElementById('new-username').value;
                const email = document.getElementById('new-email').value;
                const password = document.getElementById('new-password').value;
                const role = document.getElementById('new-role').value;
                
                fetch('/api/owner_api/users/create', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username, email, password, role})
                })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        alert('✅ Usuario VIP creado!');
                        location.reload();
                    } else {
                        alert('❌ ' + data.error);
                    }
                });
            }
            
            function deleteUser(id) {
                if (confirm('¿ELIMINAR este usuario PERMANENTEMENTE?')) {
                    fetch('/api/owner_api/users/delete/' + id, {method: 'POST'})
                    .then(r => r.json())
                    .then(data => {
                        if (data.success) {
                            alert('✅ Eliminado!');
                            location.reload();
                        } else {
                            alert('❌ ' + data.error);
                        }
                    });
                }
            }
            
            function toggleUser(id) {
                fetch('/api/owner_api/users/toggle/' + id, {method: 'POST'})
                    .then(r => r.json())
                    .then(data => {
                        if (data.success) {
                            alert('✅ Estado cambiado!');
                            location.reload();
                        } else {
                            alert('❌ ' + data.error);
                        }
                    });
            }
            
            function editUser(id) {
                const newPassword = prompt('Nueva contraseña:');
                if (newPassword) {
                    fetch('/api/owner_api/users/edit/' + id, {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({password: newPassword})
                    })
                    .then(r => r.json())
                    .then(data => {
                        if (data.success) {
                            alert('✅ Actualizado!');
                            location.reload();
                        } else {
                            alert('❌ ' + data.error);
                        }
                    });
                }
            }
        </script>
    </body>
    </html>
    '''
    return render_template_string(html, secret_url=secret_url, users=users)

@app.route('/secret/<secret_url>/owner_logout')
def owner_logout(secret_url):
    """Logout OWNER"""
    session.clear()
    return redirect(url_for('login'))

# ============ APIs OWNER ============

@app.route('/api/owner_api/users/create', methods=['POST'])
@owner_required
def owner_create_user():
    """Crear usuario VIP"""
    data = request.get_json()
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    role = data.get('role', 'user')
    
    if not username or not email or not password:
        return jsonify({'error': 'Campos requeridos'}), 400
    
    if len(password) < 8:
        return jsonify({'error': 'Mín 8 caracteres'}), 400
    
    try:
        conn = get_db()
        c = conn.cursor()
        password_hash = generate_password_hash(password)
        c.execute('INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)',
                 (username, email, password_hash, role))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Usuario o email existe'}), 400

@app.route('/api/owner_api/users/delete/<int:user_id>', methods=['POST'])
@owner_required
def owner_delete_user(user_id):
    """Eliminar usuario"""
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except:
        return jsonify({'error': 'Error'}), 400

@app.route('/api/owner_api/users/toggle/<int:user_id>', methods=['POST'])
@owner_required
def owner_toggle_user(user_id):
    """Activar/Desactivar usuario"""
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT is_active FROM users WHERE id = ?', (user_id,))
        user = c.fetchone()
        
        if user:
            new_status = 0 if user['is_active'] else 1
            c.execute('UPDATE users SET is_active = ? WHERE id = ?', (new_status, user_id))
            conn.commit()
        
        conn.close()
        return jsonify({'success': True})
    except:
        return jsonify({'error': 'Error'}), 400

@app.route('/api/owner_api/users/edit/<int:user_id>', methods=['POST'])
@owner_required
def owner_edit_user(user_id):
    """Editar usuario"""
    data = request.get_json()
    password = data.get('password', '')
    
    try:
        conn = get_db()
        c = conn.cursor()
        
        if password:
            if len(password) < 8:
                return jsonify({'error': 'Mín 8 caracteres'}), 400
            password_hash = generate_password_hash(password)
            c.execute('UPDATE users SET password_hash = ? WHERE id = ?', (password_hash, user_id))
        
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except:
        return jsonify({'error': 'Error'}), 400

# ============ RUTAS SCRAPPER NORMAL ============

@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard normal"""
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>SCRAPPER TEAM REDCARDS</title>
        <style>
            * {margin: 0; padding: 0; box-sizing: border-box;}
            body {
                background: linear-gradient(135deg, #0a0e27 0%, #1a1a3e 50%, #2d1b3d 100%);
                font-family: 'Arial Black', sans-serif;
                color: #fff;
                min-height: 100vh;
                padding: 20px;
            }
            .container {max-width: 1400px; margin: 0 auto;}
            .top-bar {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 30px;
                padding: 15px 25px;
                background: linear-gradient(135deg, rgba(255, 20, 20, 0.15) 0%, rgba(139, 0, 0, 0.1) 100%);
                border: 2px solid #ff1414;
                border-radius: 15px;
            }
            .user-info {color: #ffaa00; font-weight: bold;}
            .logout-btn {
                padding: 10px 20px;
                background: linear-gradient(135deg, #ff1414 0%, #cc0000 100%);
                border: 2px solid #ffaa00;
                border-radius: 8px;
                color: white;
                cursor: pointer;
                font-weight: bold;
            }
            .header {
                text-align: center;
                margin-bottom: 30px;
                padding: 40px;
                background: linear-gradient(135deg, rgba(255, 20, 20, 0.15) 0%, rgba(139, 0, 0, 0.1) 100%);
                border: 3px solid #ff1414;
                border-radius: 20px;
            }
            .header h1 {
                font-size: 3.5em;
                color: #ff1414;
                text-shadow: 0 0 20px rgba(255, 20, 20, 0.8);
            }
            .stats {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            .stat-box {
                background: linear-gradient(135deg, rgba(255, 20, 20, 0.1) 0%, rgba(139, 0, 0, 0.05) 100%);
                padding: 30px;
                border-radius: 15px;
                border: 2px solid #ff1414;
                text-align: center;
            }
            .stat-box h3 {color: #ffaa00; margin-bottom: 15px;}
            .stat-box .number {
                font-size: 4em;
                font-weight: 900;
                color: #ff1414;
            }
            .main-content {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 20px;
            }
            .scrapper-section, .lives-section {
                background: linear-gradient(135deg, rgba(255, 20, 20, 0.08) 0%, rgba(139, 0, 0, 0.03) 100%);
                padding: 25px;
                border-radius: 15px;
                border: 2px solid #ff1414;
            }
            .scrapper-section h2, .lives-section h2 {
                margin-bottom: 20px;
                color: #ffaa00;
                font-size: 1.8em;
            }
            .container-box {
                background: rgba(0, 0, 0, 0.5);
                padding: 15px;
                border-radius: 10px;
                height: 500px;
                overflow-y: auto;
                font-family: 'Courier New', monospace;
            }
            .log-entry {
                padding: 8px 0;
                border-bottom: 1px solid rgba(255, 20, 20, 0.2);
            }
            .log-entry.success {color: #00ff00;}
            .log-entry.error {color: #ff1414;}
            .log-entry.info {color: #ffaa00;}
            @media (max-width: 1200px) {
                .main-content {grid-template-columns: 1fr;}
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="top-bar">
                <div class="user-info">👤 Usuario: {{ username }}</div>
                <button class="logout-btn" onclick="window.location.href='/logout'">🚪 SALIR</button>
            </div>
            
            <div class="header">
                <h1>🎮 SCRAPPER TEAM REDCARDS 🔴</h1>
            </div>
            
            <div class="stats">
                <div class="stat-box">
                    <h3>✅ LIVES</h3>
                    <div class="number" id="approved">0</div>
                </div>
                <div class="stat-box">
                    <h3>❌ DECLINADAS</h3>
                    <div class="number" id="declined">0</div>
                </div>
                <div class="stat-box">
                    <h3>💎 GUARDADAS</h3>
                    <div class="number" id="lives-count">0</div>
                </div>
            </div>
            
            <div class="main-content">
                <div class="scrapper-section">
                    <h2>🔄 SCRAPPER</h2>
                    <div class="container-box" id="scrapper"></div>
                </div>
                
                <div class="lives-section">
                    <h2>💎 LIVES</h2>
                    <div class="container-box" id="lives"></div>
                </div>
            </div>
        </div>
        
        <script>
            function updateLogs() {
                fetch('/get_logs').then(r => r.json()).then(data => {
                    document.getElementById('scrapper').innerHTML = data.log.split('\\n')
                        .map(line => {
                            let cls = 'info';
                            if (line.includes('✓') || line.includes('✅')) cls = 'success';
                            else if (line.includes('❌')) cls = 'error';
                            return `<div class="log-entry ${cls}">${line}</div>`;
                        }).join('');
                    document.getElementById('approved').textContent = data.approved;
                    document.getElementById('declined').textContent = data.declined;
                });
                
                fetch('/get_lives').then(r => r.json()).then(data => {
                    document.getElementById('lives-count').textContent = data.lives.length;
                    document.getElementById('lives').innerHTML = data.lives
                        .map(l => `<div class="log-entry info">💳 ${l.cc} | ${l.bank}</div>`)
                        .join('');
                });
            }
            
            setInterval(updateLogs, 3000);
            updateLogs();
        </script>
    </body>
    </html>
    '''
    return render_template_string(html, username=session.get('username'))

# ============ APIs NORMALES ============

@app.route('/get_logs')
@login_required
def get_logs():
    """Logs públicos"""
    return jsonify({
        "log": '\n'.join(log_messages[-50:]),
        "approved": approved_count,
        "declined": declined_count
    })

@app.route('/get_lives')
@login_required
def get_lives():
    """Lives públicas"""
    return jsonify({"lives": lives_list})

@app.route('/')
def index():
    """Redirecciona a login"""
    return redirect(url_for('login'))

# ============ INICIO ============

if __name__ == '__main__':
    init_db()
    setup_owner_credentials()
    load_lives_from_file()
    
    owner_secret = get_owner_secret()
    if owner_secret:
        print(f"\n🔐 URL SECRETA OWNER: /secret/{owner_secret['secret_url']}/owner_login")
        print(f"👤 Usuario: {owner_secret['username']}")
        print(f"⚠️ CAMBIAR CONTRASEÑA INMEDIATAMENTE\n")
    
    telethon_thread = threading.Thread(target=telethon_thread_fn, daemon=True)
    telethon_thread.start()
    time.sleep(2)
    
    app.run('0.0.0.0', PORT, debug=False)
