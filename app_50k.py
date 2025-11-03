#!/usr/bin/env python3
"""
SCRAPPER ELITE v5.3 - 50K+ CÓDIGO COMPLETO
Requiere: session.session subida a Railway Files
"""
import threading
import asyncio
import random
import time
import os
import sys
import json
import sqlite3
import secrets
import re
import base64
from functools import wraps
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, jsonify, redirect, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash

try:
    from telethon import TelegramClient, events
    from telethon.errors import SessionPasswordNeededError, RPCError, FloodWaitError
    TELETHON_AVAILABLE = True
except:
    TELETHON_AVAILABLE = False

try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

# ============ CONFIG MAESTRO ============
API_ID = int(os.environ.get('API_ID', '22154650'))
API_HASH = os.environ.get('API_HASH', '2b554e270efb419af271c47ffe1d72d3')
SESSION_NAME = 'session'
SESSION_FILE = 'session.session'
PORT = int(os.environ.get('PORT', 8080))
PHONE_NUMBER = os.environ.get('PHONE_NUMBER', '+34123456789')
BOT_USERNAME = '@Alphachekerbot'
CHANNEL_ID = int(os.environ.get('CHANNEL_ID', '-1003101739772'))

# ============ CLIENTE TELETHON ============
if TELETHON_AVAILABLE:
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
else:
    client = None

# ============ VARIABLES GLOBALES ============
log_messages = []
lives_list = []
sent_ccs = []
response_messages = []
approved_count = 0
declined_count = 0
total_sent = 0
total_checked = 0
client_connected = False
telethon_running = False
start_time = datetime.now()

# Estadísticas adicionales
stats = {
    "session_loaded": False,
    "telethon_errors": 0,
    "last_error": "",
    "uptime_seconds": 0,
    "ccs_per_hour": 0,
    "lives_per_hour": 0,
}

# ============ FLASK APP ============
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.permanent_session_lifetime = timedelta(days=30)

# ============ ARCHIVOS PERSISTENTES ============
LIVES_FILE = 'lives_database.json'
DB_FILE = 'users.db'
OWNER_CONFIG_FILE = 'owner_config.json'
SENT_CCS_FILE = 'sent_ccs.json'
RESPONSES_FILE = 'responses.json'
STATS_FILE = 'stats.json'

OWNER_CONFIG = None

# ============ INICIALIZADORES ============

def init_owner_config():
    global OWNER_CONFIG
    if os.path.exists(OWNER_CONFIG_FILE):
        try:
            with open(OWNER_CONFIG_FILE, 'r') as f:
                OWNER_CONFIG = json.load(f)
                return OWNER_CONFIG
        except:
            pass
    
    config = {
        "secret_url": secrets.token_urlsafe(32),
        "username": "admin",
        "password": "ChangeMe123!@#",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    
    with open(OWNER_CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    
    OWNER_CONFIG = config
    print(f"\n{'='*100}")
    print(f"🔐 OWNER CONFIG CREADA")
    print(f"🔗 URL: /secret/{config['secret_url']}/owner_login")
    print(f"👤 Usuario: {config['username']}")
    print(f"🔑 Contraseña: {config['password']}")
    print(f"{'='*100}\n")
    return config

def get_owner_config():
    global OWNER_CONFIG
    if OWNER_CONFIG is None:
        init_owner_config()
    return OWNER_CONFIG

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
        print("✅ BD Inicializada")
    except Exception as e:
        print(f"❌ Error BD: {e}")

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def load_persistent_files():
    global lives_list, sent_ccs, response_messages
    try:
        if os.path.exists(LIVES_FILE):
            with open(LIVES_FILE, 'r', encoding='utf-8') as f:
                lives_list = json.load(f)
    except:
        lives_list = []
    
    try:
        if os.path.exists(SENT_CCS_FILE):
            with open(SENT_CCS_FILE, 'r') as f:
                sent_ccs = json.load(f)
    except:
        sent_ccs = []
    
    try:
        if os.path.exists(RESPONSES_FILE):
            with open(RESPONSES_FILE, 'r', encoding='utf-8') as f:
                response_messages = json.load(f)
    except:
        response_messages = []

def save_persistent_files():
    try:
        with open(LIVES_FILE, 'w', encoding='utf-8') as f:
            json.dump(lives_list[-100:], f, indent=2, ensure_ascii=False)
    except:
        pass
    
    try:
        with open(SENT_CCS_FILE, 'w') as f:
            json.dump(sent_ccs[-1000:], f, indent=2)
    except:
        pass
    
    try:
        with open(RESPONSES_FILE, 'w', encoding='utf-8') as f:
            json.dump(response_messages[-500:], f, indent=2, ensure_ascii=False)
    except:
        pass

def save_stats():
    try:
        stats['uptime_seconds'] = int((datetime.now() - start_time).total_seconds())
        with open(STATS_FILE, 'w') as f:
            json.dump(stats, f, indent=2)
    except:
        pass

# ============ SEGURIDAD ============

def check_brute_force(username):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT failed_attempts, locked_until FROM users WHERE username = ?', (username,))
        user = c.fetchone()
        conn.close()
        if user and user['locked_until']:
            if datetime.fromisoformat(user['locked_until']) > datetime.now():
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

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ============ VALIDADORES LUHN ============

def luhn_checksum(card_number):
    digits = [int(d) for d in str(card_number)]
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    checksum = sum(odd_digits)
    for d in even_digits:
        checksum += sum([int(x) for x in str(d * 2)])
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
            expiry = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            expiry = datetime(year, month + 1, 1) - timedelta(days=1)
        return expiry >= datetime.now()
    except:
        return False

def generate_random_valid_date():
    future = datetime.now() + timedelta(days=random.randint(0, 365 * 5))
    return f"{future.month:02d}", str(future.year)

def generate_cc_variants(ccbase, count=20):
    if ',' in ccbase:
        separator = ','
    elif '|' in ccbase:
        separator = '|'
    else:
        return []
    
    parts = ccbase.strip().split(separator)
    if len(parts) < 4:
        return []
    
    cardnumber = parts[0].strip()
    month = parts[1].strip()
    year = parts[2].strip()
    
    if len(cardnumber) < 12:
        return []
    
    if not is_date_valid(month, year):
        month, year = generate_random_valid_date()
    
    bin_number = cardnumber[:-4]
    variants = []
    
    for i in range(count):
        random_digits = ''.join([str(random.randint(0, 9)) for _ in range(3)])
        partial = bin_number + random_digits
        luhn_digit = generate_luhn_digit(partial)
        complete = partial + str(luhn_digit)
        cvv = random.randint(100, 999)
        variant = f"{complete}{separator}{month}{separator}{year}{separator}{cvv}"
        if variant not in variants:
            variants.append(variant)
    
    return variants

# ============ TELETHON HANDLERS ============

async def response_handler(event):
    global approved_count, declined_count, lives_list, total_checked
    try:
        full_message = event.message.message if event.message.message else ""
        message_lower = full_message.lower()
        total_checked += 1
        
        if "✅" in full_message or "approved" in message_lower or "valid" in message_lower:
            approved_count += 1
            log_messages.append(f"✅ LIVE DETECTADA")
            
            lines = full_message.split('\n')
            data = {
                "cc": "",
                "status": "✅ APPROVED",
                "response": full_message,
                "country": "🌍 Unknown",
                "bank": "🏦 Unknown",
                "type": "💳 VISA",
                "gate": "AlphaChecker",
                "bin": "",
                "avs": "Match",
                "cvv": "Match",
                "zip": "Match",
                "address": "Match",
                "amount": "N/A",
                "currency": "USD",
                "processor": "Stripe",
                "error": "",
                "reason": "APPROVED",
                "code": "00",
                "descriptor": "APPROVED",
                "merchant": "Merchant",
                "raw": full_message,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            for line in lines:
                line_lower = line.lower()
                if 'cc:' in line_lower:
                    data["cc"] = line.split(':', 1)[1].strip() if ':' in line else ""
                elif 'bank:' in line_lower:
                    data["bank"] = line.split(':', 1)[1].strip() if ':' in line else ""
                elif 'country:' in line_lower:
                    data["country"] = line.split(':', 1)[1].strip() if ':' in line else ""
                elif 'status:' in line_lower:
                    data["status"] = line.split(':', 1)[1].strip() if ':' in line else "✅ APPROVED"
            
            lives_list.append(data)
            save_persistent_files()
            
            if client and TELETHON_AVAILABLE and client_connected:
                try:
                    msg = f"""
╔════════════════════════════════════════════╗
           🟢 LIVE ENCONTRADA 🟢
╚════════════════════════════════════════════╝

💳 CC: {data['cc']}
✅ Status: {data['status']}
🏦 Banco: {data['bank']}
🌍 País: {data['country']}
💰 Tipo: {data['type']}
🎯 Gate: {data['gate']}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✔️ AVS: {data['avs']}
✔️ CVV: {data['cvv']}
📮 ZIP: {data['zip']}
📍 Address: {data['address']}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💵 Amount: {data['amount']}
🪙 Currency: {data['currency']}
🔧 Processor: {data['processor']}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ {data['timestamp']}
"""
                    await client.send_message(CHANNEL_ID, msg)
                    log_messages.append(f"📤 ENVIADO AL CANAL")
                except Exception as e:
                    log_messages.append(f"⚠️ Error envío: {str(e)[:50]}")
        
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

async def send_ccs_to_bot():
    global total_sent, client_connected
    
    while True:
        try:
            if not client_connected or not client:
                await asyncio.sleep(5)
                continue
            
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
                
                for i in range(len(cc_variants)):
                    try:
                        selected_command = random.choice(commands)
                        message = f"{selected_command} {cc_variants[i]}"
                        await client.send_message(BOT_USERNAME, message)
                        sent_ccs.append({
                            "cc": cc_variants[i],
                            "command": selected_command,
                            "timestamp": datetime.now().isoformat()
                        })
                        total_sent += 1
                        log_messages.append(f"✓ #{i+1}/20")
                        await asyncio.sleep(1)
                    except FloodWaitError as e:
                        log_messages.append(f"⚠️ Flood {e.seconds}s")
                        await asyncio.sleep(e.seconds + 1)
                    except Exception as e:
                        log_messages.append(f"❌ Error: {str(e)[:30]}")
                
                save_persistent_files()
                save_stats()
                log_messages.append(f"🎉 LOTE #{len(lives_list)}")
                await asyncio.sleep(21)
            else:
                await asyncio.sleep(30)
        except Exception as e:
            log_messages.append(f"❌ Send Error: {str(e)[:50]}")
            await asyncio.sleep(30)

async def telethon_main():
    global client_connected, telethon_running, stats
    
    if not client or not TELETHON_AVAILABLE:
        print("⚠️ Telethon no disponible")
        return
    
    try:
        print("🚀 Telethon iniciando...")
        log_messages.append("🚀 Telethon iniciando...")
        
        # Verificar si session.session existe
        if not os.path.exists(SESSION_FILE):
            print(f"⚠️ {SESSION_FILE} no encontrado")
            print(f"⚠️ Sube {SESSION_FILE} a Railway Files o ejecuta local primero")
            log_messages.append(f"⚠️ Falta {SESSION_FILE}")
            stats["session_loaded"] = False
            await asyncio.sleep(30)
            return
        
        print(f"✅ {SESSION_FILE} encontrado")
        log_messages.append(f"✅ {SESSION_FILE} encontrado")
        stats["session_loaded"] = True
        
        # Verificar autorización
        if not await client.is_user_authorized():
            print("⚠️ Sesión expirada o inválida")
            log_messages.append("⚠️ Sesión inválida")
            stats["session_loaded"] = False
            await asyncio.sleep(30)
            return
        
        # Conectar
        await client.start()
        client_connected = True
        telethon_running = True
        log_messages.append("✅ Telethon CONECTADO")
        print("✅ Telethon conectado")
        
        # Registrar event handler
        client.add_event_handler(response_handler, events.MessageEdited(chats=BOT_USERNAME))
        
        # Iniciar tareas
        await asyncio.gather(
            send_ccs_to_bot(),
            client.run_until_disconnected()
        )
    except EOFError:
        client_connected = False
        telethon_running = False
        print("⚠️ EOF (sin stdin)")
        log_messages.append("⚠️ EOF Error")
        stats["telethon_errors"] += 1
        stats["last_error"] = "EOF"
        await asyncio.sleep(30)
    except Exception as e:
        client_connected = False
        telethon_running = False
        error = str(e)[:100]
        print(f"❌ Error: {error}")
        log_messages.append(f"❌ Error: {error}")
        stats["telethon_errors"] += 1
        stats["last_error"] = error
        await asyncio.sleep(30)

def telethon_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(telethon_main())
    except Exception as e:
        print(f"❌ Thread Error: {e}")

# ============ FLASK ROUTES ============

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
            return jsonify({'error': 'Campos requeridos'}), 400
        
        if check_brute_force(username):
            return jsonify({'error': 'Bloqueado 15min'}), 429
        
        try:
            conn = get_db()
            c = conn.cursor()
            c.execute('SELECT id, username, password_hash, is_active FROM users WHERE username = ?', (username,))
            user = c.fetchone()
            conn.close()
            
            if not user or not user['is_active']:
                increment_failed_attempts(username)
                return jsonify({'error': 'No encontrado'}), 401
            
            if not check_password_hash(user['password_hash'], password):
                increment_failed_attempts(username)
                return jsonify({'error': 'Contraseña incorrecta'}), 401
            
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
            return jsonify({'error': 'Error servidor'}), 500
    
    html = '''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>🔐 SCRAPPER ELITE LOGIN</title><style>*{margin:0;padding:0;box-sizing:border-box}
body{background:linear-gradient(135deg,#0a0e27 0%,#1a1a3e 30%,#2d1b3d 60%,#0a0e27 100%);font-family:'Segoe UI',sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center;overflow:hidden;position:relative}
body::before{content:'';position:fixed;top:0;left:0;right:0;bottom:0;background:radial-gradient(circle at 20%50%,rgba(255,20,20,0.15) 0%,transparent 40%),radial-gradient(circle at 80%80%,rgba(20,20,255,0.15) 0%,transparent 40%);pointer-events:none;z-index:0;animation:float 20s ease-in-out infinite}
.login-container{background:rgba(255,20,20,0.07);border:3px solid #ff1414;border-radius:30px;padding:70px 60px;width:100%;max-width:500px;box-shadow:0 0 100px rgba(255,20,20,0.3);backdrop-filter:blur(20px);position:relative;z-index:10;animation:slideUp 0.8s}
.login-container h1{color:#ff1414;margin-bottom:10px;text-align:center;font-size:3em;text-shadow:0 0 30px rgba(255,20,20,0.8);letter-spacing:3px;font-weight:900}
.login-container p{color:#ffaa00;text-align:center;margin-bottom:35px;font-size:1em;letter-spacing:1px}
.form-group{margin-bottom:30px}
.form-group label{display:block;color:#ffaa00;margin-bottom:12px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;font-size:0.95em}
.form-group input{width:100%;padding:16px 20px;background:rgba(0,0,0,0.4);border:2px solid #ff1414;border-radius:12px;color:#fff;font-size:1.05em;transition:all 0.4s;box-shadow:inset 0 2px 8px rgba(0,0,0,0.3)}
.form-group input:focus{outline:none;border-color:#ffaa00;box-shadow:0 0 30px rgba(255,170,0,0.6);transform:translateY(-2px)}
.login-btn{width:100%;padding:16px;background:linear-gradient(135deg,#ff1414 0%,#cc0000 100%);border:3px solid #ffaa00;border-radius:12px;color:white;font-weight:900;font-size:1.15em;cursor:pointer;text-transform:uppercase;transition:all 0.4s;box-shadow:0 8px 30px rgba(255,20,20,0.5);letter-spacing:2px}
.login-btn:hover{transform:translateY(-3px);box-shadow:0 12px 50px rgba(255,20,20,0.7)}
.error-message{color:#ff6b6b;text-align:center;margin-bottom:20px;font-weight:700;padding:15px;background:rgba(255,20,20,0.15);border-left:4px solid #ff1414;border-radius:8px;display:none}
@keyframes slideUp{from{opacity:0;transform:translateY(40px)}to{opacity:1;transform:translateY(0)}}
@keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(20px)}}
</style></head><body><div class="login-container"><h1>🔐 SCRAPPER</h1><p>Team RedCards 💎 ELITE VIP</p>
<div id="error-msg" class="error-message"></div><form id="login-form"><div class="form-group"><label>👤 Usuario</label><input type="text" name="username" placeholder="usuario" required></div>
<div class="form-group"><label>🔑 Contraseña</label><input type="password" name="password" placeholder="contraseña" required></div>
<button type="submit" class="login-btn">🚀 ENTRAR</button></form></div>
<script>document.getElementById('login-form').addEventListener('submit',function(e){e.preventDefault();fetch('/login',{method:'POST',body:new FormData(this)}).then(r=>r.json()).then(d=>{if(d.success)window.location.href=d.redirect;else{document.getElementById('error-msg').textContent='❌ '+d.error;document.getElementById('error-msg').style.display='block';}});});</script>
</body></html>'''
    return render_template_string(html)

@app.route('/dashboard')
@login_required
def dashboard():
    html = '''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>🎮 SCRAPPER ELITE DASHBOARD</title><style>*{margin:0;padding:0;box-sizing:border-box}
body{background:linear-gradient(135deg,#0a0e27,#1a1a3e,#2d1b3d);font-family:'Segoe UI',sans-serif;color:#fff;min-height:100vh;padding:25px}::selection{background:#ff1414;color:#fff}
.container{max-width:1920px;margin:0 auto}.top-bar{display:flex;justify-content:space-between;align-items:center;margin-bottom:30px;padding:25px 40px;background:linear-gradient(135deg,rgba(255,20,20,0.2),rgba(20,20,255,0.1));border:3px solid #ff1414;border-radius:20px;box-shadow:0 15px 50px rgba(255,20,20,0.2)}
.user-info{color:#ffaa00;font-weight:bold;font-size:1.2em;display:flex;align-items:center;gap:12px}
.logout-btn{padding:14px 30px;background:linear-gradient(135deg,#ff1414,#cc0000);border:3px solid #ffaa00;border-radius:10px;color:white;font-weight:bold;cursor:pointer;transition:all 0.3s;text-transform:uppercase}
.logout-btn:hover{transform:translateY(-2px);box-shadow:0 8px 25px rgba(255,20,20,0.5)}
.header{text-align:center;margin-bottom:50px;padding:60px 50px;background:linear-gradient(135deg,rgba(255,20,20,0.15),rgba(255,20,20,0.08));border:4px solid #ff1414;border-radius:25px;box-shadow:0 20px 60px rgba(255,20,20,0.2)}
.header h1{font-size:4.5em;color:#ff1414;text-shadow:0 0 40px rgba(255,20,20,0.9);margin-bottom:15px;letter-spacing:3px;font-weight:900}
.header p{color:#ffaa00;font-size:1.15em;letter-spacing:1px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:30px;margin-bottom:50px}
.stat-box{background:linear-gradient(135deg,rgba(255,20,20,0.15),rgba(255,20,20,0.08));padding:50px;border-radius:25px;border:4px solid #ff1414;text-align:center;box-shadow:0 15px 50px rgba(255,20,20,0.2);transition:all 0.4s;position:relative}
.stat-box:hover{transform:translateY(-8px);box-shadow:0 25px 70px rgba(255,20,20,0.3)}
.stat-box h3{color:#ffaa00;margin-bottom:20px;font-size:1.4em;text-transform:uppercase;letter-spacing:1.5px}
.stat-box .number{font-size:6em;font-weight:900;color:#ff1414;text-shadow:0 0 30px rgba(255,20,20,0.6);font-family:monospace}
.stat-box .icon{font-size:3.5em;margin-bottom:20px}
.main{display:grid;grid-template-columns:1fr 1.3fr;gap:30px;margin-bottom:40px}
.section{background:linear-gradient(135deg,rgba(255,20,20,0.12),rgba(255,20,20,0.05));padding:40px;border-radius:25px;border:3px solid #ff1414;box-shadow:0 15px 50px rgba(255,20,20,0.15)}
.section h2{color:#ffaa00;margin-bottom:30px;font-size:2em;text-transform:uppercase;letter-spacing:1.5px;font-weight:700}
.box{background:rgba(0,0,0,0.7);padding:25px;border-radius:18px;height:650px;overflow-y:auto;border:2px solid #ff1414;box-shadow:inset 0 4px 15px rgba(0,0,0,0.5)}
.item{padding:15px;border-bottom:2px solid rgba(255,20,20,0.3);color:#ffaa00;margin-bottom:8px;border-radius:4px;transition:all 0.3s;font-family:monospace;font-size:0.9em}
.item:hover{background:rgba(255,20,20,0.05)}
.live-card{background:linear-gradient(135deg,rgba(0,255,0,0.1),rgba(0,255,0,0.05));padding:20px;margin-bottom:15px;border-radius:12px;border-left:5px solid #00ff00;box-shadow:0 5px 15px rgba(0,255,0,0.1)}
.live-title{color:#00ff00;font-weight:bold;font-size:1em;margin-bottom:10px}
.live-info{color:#ffaa00;font-size:0.85em;line-height:1.6;display:grid;grid-template-columns:1fr 1fr;gap:8px}
.box::-webkit-scrollbar{width:10px}
.box::-webkit-scrollbar-track{background:rgba(0,0,0,0.4);border-radius:10px}
.box::-webkit-scrollbar-thumb{background:#ff1414;border-radius:10px}
.box::-webkit-scrollbar-thumb:hover{background:#ffaa00}
</style></head><body><div class="container">
<div class="top-bar"><div class="user-info">👤 {{ username }}</div><button class="logout-btn" onclick="location.href='/logout'">🚪 SALIR</button></div>
<div class="header"><h1>🎮 SCRAPPER ELITE 🔴</h1><p>Dashboard Control Real-Time 💎</p></div>
<div class="stats">
<div class="stat-box"><div class="icon">✅</div><h3>Lives</h3><div class="number" id="approved">0</div></div>
<div class="stat-box"><div class="icon">❌</div><h3>Declinadas</h3><div class="number" id="declined">0</div></div>
<div class="stat-box"><div class="icon">📤</div><h3>Enviadas</h3><div class="number" id="sent">0</div></div>
<div class="stat-box"><div class="icon">💎</div><h3>Guardadas</h3><div class="number" id="lives-count">0</div></div>
</div>
<div class="main">
<div class="section"><h2>📤 CCS ENVIADAS</h2><div class="box" id="ccs"></div></div>
<div class="section"><h2>✅ LIVES ELITE</h2><div class="box" id="lives"></div></div>
</div></div>
<script>function update(){fetch('/get_logs').then(r=>r.json()).then(d=>{document.getElementById('approved').textContent=d.approved;document.getElementById('declined').textContent=d.declined;});
fetch('/get_sent').then(r=>r.json()).then(d=>{document.getElementById('sent').textContent=d.total;const div=document.getElementById('ccs');div.innerHTML=d.sent.slice(-50).reverse().map(s=>`<div class="item">💳 ${s.cc}</div>`).join('');});
fetch('/get_lives').then(r=>r.json()).then(d=>{document.getElementById('lives-count').textContent=d.lives.length;const div=document.getElementById('lives');div.innerHTML=d.lives.slice(-20).reverse().map(l=>`<div class="live-card"><div class="live-title">✅ ${l.cc.substring(0,12)}</div><div class="live-info"><span>🏦 ${l.bank}</span><span>🗺️ ${l.country}</span><span>💰 ${l.type}</span><span>🎯 ${l.gate}</span></div></div>`).join('');}); }setInterval(update,1500);update();</script>
</body></html>'''
    return render_template_string(html, username=session.get('username'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/get_logs')
@login_required
def get_logs():
    return jsonify({"approved": approved_count, "declined": declined_count, "logs": log_messages[-50:]})

@app.route('/get_lives')
@login_required
def get_lives():
    return jsonify({"lives": lives_list})

@app.route('/get_sent')
@login_required
def get_sent():
    return jsonify({"sent": sent_ccs[-50:], "total": total_sent})

@app.route('/health')
def health():
    save_stats()
    return jsonify({
        "status": "ok",
        "approved": approved_count,
        "declined": declined_count,
        "sent": total_sent,
        "lives": len(lives_list),
        "telethon_connected": client_connected,
        "session_loaded": stats.get("session_loaded", False),
        "uptime_seconds": int((datetime.now() - start_time).total_seconds()),
        "errors": stats.get("telethon_errors", 0)
    })

# ============ MAIN ============

if __name__ == '__main__':
    print(f"\n{'='*120}")
    print(f"🚀 SCRAPPER ELITE v5.3 - 50K+ CÓDIGO COMPLETO")
    print(f"🔑 Requiere: session.session en Railway Files")
    print(f"{'='*120}\n")
    
    init_db()
    init_owner_config()
    load_persistent_files()
    
    print(f"✅ Sistema inicializado\n")
    
    if TELETHON_AVAILABLE:
        telethon_t = threading.Thread(target=telethon_thread, daemon=True)
        telethon_t.start()
        time.sleep(2)
    
    print(f"\n{'='*120}")
    print(f"🌐 Flask en http://0.0.0.0:{PORT}")
    print(f"🔗 Telethon: {'Disponible' if TELETHON_AVAILABLE else 'No disponible'}")
    print(f"📁 Session: {SESSION_FILE}")
    print(f"💎 ELITE VIP - Team RedCards")
    print(f"{'='*120}\n")
    
    app.run('0.0.0.0', PORT, debug=False, use_reloader=False, threaded=True)
