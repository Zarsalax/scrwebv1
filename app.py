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

def get_current_date():
    """Obtiene la fecha actual en formato MM/YY"""
    now = datetime.now()
    return f"{now.month:02d}/{now.year % 100:02d}"

def is_date_valid(month, year):
    """Verifica si una fecha MM/YY es válida (no está vencida)"""
    try:
        month = int(month)
        year = int(year)
        
        # Convertir a año completo (00-30 = 2000-2030, 31-99 = 1931-1999)
        if year <= 30:
            year += 2000
        elif year <= 99:
            year += 1900
        
        # Crear fecha del último día del mes
        if month == 12:
            expiry_date = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            expiry_date = datetime(year, month + 1, 1) - timedelta(days=1)
        
        # Comparar con fecha actual
        return expiry_date >= datetime.now()
    except:
        return False

def generate_random_valid_date():
    """Genera una fecha aleatoria válida (actual o más adelante)"""
    now = datetime.now()
    # Generar fecha entre hoy y 5 años en el futuro
    days_ahead = random.randint(0, 365 * 5)
    future_date = now + timedelta(days=days_ahead)
    month = f"{future_date.month:02d}"
    year = f"{future_date.year}"
    return month, year

def generate_cc_variants(ccbase, count=20):
    """
    Genera 20 variantes de tarjetas SIN algoritmo de Luhn
    - Si la fecha es vencida: genera nueva fecha válida y QUITA los últimos 5-6 dígitos
    - Si la fecha es válida: cambia solo los 4 últimos dígitos
    """
    # Detectar separador (coma o pipe)
    if ',' in ccbase:
        separator = ','
    elif '|' in ccbase:
        separator = '|'
    else:
        log_messages.append(f"ERROR: Formato desconocido: {ccbase}")
        return []
    
    parts = ccbase.strip().split(separator)
    
    # Parsear datos originales
    if len(parts) >= 4:
        cardnumber = parts[0]
        month = parts[1]
        year = parts[2]
        cvv = parts[3]
    else:
        log_messages.append(f"ERROR: Formato de CC inválido: {ccbase}")
        return []
    
    # Verificar longitud de tarjeta
    if len(cardnumber) < 12:
        log_messages.append(f"ERROR: Tarjeta muy corta: {cardnumber}")
        return []
    
    # Verificar si la fecha es válida
    date_is_valid = is_date_valid(month, year)
    
    variants = []
    
    # Si la fecha NO es válida (vencida)
    if not date_is_valid:
        log_messages.append(f"⚠️ Fecha vencida detectada: {month}/{year}. Generando nueva fecha...")
        month, year = generate_random_valid_date()
        
        # Generar 20 variantes QUITANDO los últimos 5-6 dígitos
        for i in range(count):
            num_list = list(cardnumber)
            
            # Quitar los últimos 6 dígitos (reemplazar con X)
            # Dejar solo los primeros len(cardnumber) - 6 dígitos
            for j in range(len(num_list) - 6, len(num_list)):
                if j >= 0:
                    num_list[j] = str(random.randint(0, 9))
            
            complete_number = ''.join(num_list)
            random_cvv = random.randint(100, 999)
            variant = f"{complete_number}{separator}{month}{separator}{year}{separator}{random_cvv}"
            
            if variant not in variants:
                variants.append(variant)
        
        log_messages.append(f"✓ Generadas {len(variants)} CCs con fecha actualizada (últimos 6 dígitos cambiados)")
    
    # Si la fecha SÍ es válida
    else:
        base_number = cardnumber[:-4]  # Quitar los 4 últimos dígitos
        
        # Generar 20 variantes cambiando los 4 últimos dígitos
        for i in range(count):
            # Generar 4 dígitos aleatorios
            last_four = ''.join([str(random.randint(0, 9)) for _ in range(4)])
            complete_number = base_number + last_four
            
            # Generar CVV aleatorio
            random_cvv = random.randint(100, 999)
            variant = f"{complete_number}{separator}{month}{separator}{year}{separator}{random_cvv}"
            
            if variant not in variants:
                variants.append(variant)
        
        log_messages.append(f"✓ Generadas {len(variants)} variantes (4 últimos dígitos cambiados)")
    
    return variants

# ============ MANEJADOR DE EVENTOS ============

async def response_handler(event):
    """Maneja respuestas de mensajes aprobados/rechazados"""
    global approved_count, declined_count, channelid, lives_list
    
    full_message = event.message.message if event.message.message else ""
    message_lower = full_message.lower()
    
    # Detectar si es APPROVED
    if "✅" in full_message or "approved" in message_lower:
        approved_count += 1
        log_messages.append(f"✓ APPROVED: {full_message[:100]}")
        
        # Extraer información del mensaje
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
        
        # ✅ NUEVO FORMATO - Team RedCards (MEJORADO Y BRUTAL)
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
        
        # Guardar LIVE en la lista
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
        
        # Mantener solo los últimos 100 lives
        if len(lives_list) > 100:
            lives_list.pop(0)
        
        # ENVIAR AL CANAL
        try:
            image_path = 'x1.jpg'
            
            # Enviar con imagen si existe, si no, solo texto
            if os.path.exists(image_path):
                await client.send_file(
                    channelid,
                    image_path,
                    caption=formatted_message,
                    parse_mode='markdown'
                )
                log_messages.append(f"✓ Enviado al canal con imagen")
            else:
                await client.send_message(
                    channelid,
                    formatted_message,
                    parse_mode='markdown'
                )
                log_messages.append(f"✓ Enviado al canal sin imagen")
        
        except Exception as e:
            log_messages.append(f"ERROR al enviar: {e}")
    
    elif "❌" in full_message or "declined" in message_lower:
        declined_count += 1
        log_messages.append(f"✗ DECLINED: {full_message[:100]}")
    
    # Mantener solo los últimos 100 logs
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
        log_messages.append(f"ERROR: Error cargando comandos: {e}")
        return ['/check']

async def send_to_bot():
    """
    Envía CCs al bot de Telegram
    - Genera 20 variantes por BIN
    - Si fecha vencida: genera nueva fecha y quita últimos 6 dígitos
    - Si fecha válida: cambia solo los 4 últimos dígitos
    """
    while True:
        try:
            if not os.path.exists('ccs.txt'):
                log_messages.append("INFO: ccs.txt no encontrado. Esperando...")
                await asyncio.sleep(30)
                continue
            
            with open('ccs.txt', 'r', encoding='utf-8') as f:
                ccs_list = f.readlines()
            
            if ccs_list:
                current_cc = ccs_list[0].strip()
                
                # Eliminar la CC que se procesará
                if len(ccs_list) > 1:
                    with open('ccs.txt', 'w', encoding='utf-8') as f:
                        f.writelines(ccs_list[1:])
                else:
                    with open('ccs.txt', 'w', encoding='utf-8') as f:
                        f.write("")
                
                log_messages.append(f"INFO: Generando 20 variantes para {current_cc[:12]}...")
                
                # GENERAR 20 VARIANTES
                cc_variants = generate_cc_variants(current_cc, count=20)
                
                if not cc_variants:
                    log_messages.append(f"ERROR: No se pudieron generar variantes")
                    await asyncio.sleep(20)
                    continue
                
                commands = await load_commands()
                
                # Enviar las 20 CCs generadas
                for i, cc in enumerate(cc_variants):
                    selected_command = random.choice(commands)
                    message = f"{selected_command} {cc}"
                    
                    try:
                        await client.send_message('@Alphachekerbot', message)
                        log_messages.append(f"✓ Enviado CC #{i+1}/20: {cc[:12]}...")
                    except FloodWaitError as e:
                        log_messages.append(f"WARNING: Esperando {e.seconds}s...")
                        await asyncio.sleep(e.seconds)
                    except RPCError as e:
                        log_messages.append(f"ERROR RPC: {e}")
                    
                    await asyncio.sleep(21)
                
                log_messages.append(f"✓ Lote completado: 20/20 CCs enviadas")
            else:
                log_messages.append("INFO: No hay CCs. Esperando...")
                await asyncio.sleep(20)
        
        except Exception as e:
            log_messages.append(f"ERROR: {e}")
            await asyncio.sleep(20)

async def start_client():
    """Inicia el cliente de Telegram"""
    try:
        log_messages.append("INFO: Iniciando cliente de Telegram...")
        await client.start()
        log_messages.append("✓ Cliente autenticado correctamente")
        
        # Escuchar mensajes EDITADOS del bot checker
        client.add_event_handler(response_handler, events.MessageEdited(chats='@Alphachekerbot'))
        
        await asyncio.gather(send_to_bot(), client.run_until_disconnected())
    except Exception as e:
        log_messages.append(f"ERROR: Error al iniciar cliente: {e}")

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
        <title>Team RedCards - Panel</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            body {
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
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
                padding: 30px;
                background: rgba(255, 255, 255, 0.05);
                border-radius: 15px;
                border: 2px solid #e74c3c;
                box-shadow: 0 0 20px rgba(231, 76, 60, 0.3);
            }
            .header h1 {
                font-size: 2.5em;
                margin-bottom: 10px;
                color: #e74c3c;
                text-shadow: 0 0 10px rgba(231, 76, 60, 0.5);
            }
            .header p {
                font-size: 1.1em;
                color: #bdc3c7;
            }
            .stats {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            .stat-box {
                background: rgba(255, 255, 255, 0.08);
                padding: 25px;
                border-radius: 10px;
                border-left: 4px solid #e74c3c;
                text-align: center;
                backdrop-filter: blur(10px);
                transition: transform 0.3s ease, box-shadow 0.3s ease;
            }
            .stat-box:hover {
                transform: translateY(-5px);
                box-shadow: 0 10px 30px rgba(231, 76, 60, 0.2);
            }
            .stat-box h3 {
                color: #bdc3c7;
                margin-bottom: 10px;
                font-size: 0.9em;
                text-transform: uppercase;
            }
            .stat-box .number {
                font-size: 3em;
                font-weight: bold;
                color: #e74c3c;
            }
            .control-panel {
                background: rgba(255, 255, 255, 0.05);
                padding: 25px;
                border-radius: 10px;
                margin-bottom: 30px;
                border: 1px solid rgba(231, 76, 60, 0.3);
            }
            .control-panel h2 {
                margin-bottom: 20px;
                color: #e74c3c;
                font-size: 1.5em;
            }
            .form-group {
                display: flex;
                gap: 10px;
                flex-wrap: wrap;
            }
            input[type="text"] {
                flex: 1;
                min-width: 200px;
                padding: 12px 15px;
                background: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(231, 76, 60, 0.5);
                border-radius: 5px;
                color: #fff;
                font-size: 1em;
            }
            input[type="text"]::placeholder {
                color: rgba(255, 255, 255, 0.5);
            }
            input[type="text"]:focus {
                outline: none;
                border-color: #e74c3c;
                box-shadow: 0 0 10px rgba(231, 76, 60, 0.3);
            }
            button {
                padding: 12px 30px;
                background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
                border: none;
                border-radius: 5px;
                color: white;
                font-size: 1em;
                font-weight: bold;
                cursor: pointer;
                transition: transform 0.2s ease, box-shadow 0.2s ease;
                text-transform: uppercase;
            }
            button:hover {
                transform: scale(1.05);
                box-shadow: 0 5px 15px rgba(231, 76, 60, 0.4);
            }
            button:active {
                transform: scale(0.98);
            }
            .main-content {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 20px;
                margin-bottom: 30px;
            }
            .logs-section, .lives-section {
                background: rgba(255, 255, 255, 0.05);
                padding: 25px;
                border-radius: 10px;
                border: 1px solid rgba(231, 76, 60, 0.3);
            }
            .logs-section h2, .lives-section h2 {
                margin-bottom: 20px;
                color: #e74c3c;
                font-size: 1.5em;
            }
            .search-box {
                margin-bottom: 15px;
                display: flex;
                gap: 10px;
            }
            .search-box input {
                flex: 1;
                padding: 10px 15px;
                background: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(231, 76, 60, 0.5);
                border-radius: 5px;
                color: #fff;
            }
            .search-box input::placeholder {
                color: rgba(255, 255, 255, 0.5);
            }
            .search-box button {
                padding: 10px 20px;
            }
            .logs-container, .lives-container {
                background: rgba(0, 0, 0, 0.3);
                padding: 15px;
                border-radius: 5px;
                height: 500px;
                overflow-y: auto;
                font-family: 'Courier New', monospace;
                font-size: 0.9em;
                line-height: 1.6;
            }
            .log-entry {
                padding: 5px 0;
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            }
            .log-entry.approved {
                color: #2ecc71;
            }
            .log-entry.declined {
                color: #e74c3c;
            }
            .log-entry.info {
                color: #3498db;
            }
            .log-entry.error {
                color: #e67e22;
            }
            .log-entry.warning {
                color: #f39c12;
            }
            .live-card {
                background: rgba(255, 255, 255, 0.08);
                padding: 15px;
                margin-bottom: 10px;
                border-radius: 8px;
                border-left: 3px solid #2ecc71;
                transition: transform 0.2s ease;
            }
            .live-card:hover {
                transform: translateX(5px);
            }
            .live-card-header {
                display: flex;
                justify-content: space-between;
                margin-bottom: 8px;
                font-weight: bold;
                color: #2ecc71;
            }
            .live-card-info {
                font-size: 0.85em;
                color: #bdc3c7;
                margin: 4px 0;
            }
            .live-card-timestamp {
                font-size: 0.75em;
                color: #7f8c8d;
                margin-top: 8px;
            }
            /* Scrollbar personalizado */
            .logs-container::-webkit-scrollbar,
            .lives-container::-webkit-scrollbar {
                width: 8px;
            }
            .logs-container::-webkit-scrollbar-track,
            .lives-container::-webkit-scrollbar-track {
                background: rgba(0, 0, 0, 0.1);
                border-radius: 10px;
            }
            .logs-container::-webkit-scrollbar-thumb,
            .lives-container::-webkit-scrollbar-thumb {
                background: #e74c3c;
                border-radius: 10px;
            }
            .logs-container::-webkit-scrollbar-thumb:hover,
            .lives-container::-webkit-scrollbar-thumb:hover {
                background: #c0392b;
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
                <h1>💳 Team RedCards</h1>
                <p>Panel de Control - CC Checker Bot 24/7</p>
            </div>
            
            <div class="stats">
                <div class="stat-box">
                    <h3>✅ Aprobadas</h3>
                    <div class="number" id="approved">{{ approved }}</div>
                </div>
                <div class="stat-box">
                    <h3>❌ Rechazadas</h3>
                    <div class="number" id="declined">{{ declined }}</div>
                </div>
                <div class="stat-box">
                    <h3>💰 LIVES Encontradas</h3>
                    <div class="number" id="lives-count">0</div>
                </div>
            </div>
            
            <div class="control-panel">
                <h2>⚙️ Cambiar Canal</h2>
                <div class="form-group">
                    <input type="text" id="channel-input" placeholder="Ingresa el ID del canal (ej: -1003101739772)">
                    <button onclick="changeChannel()">Cambiar</button>
                </div>
            </div>
            
            <div class="main-content">
                <div class="logs-section">
                    <h2>📋 Logs en Tiempo Real</h2>
                    <div class="logs-container" id="logs">
                        {{ log }}
                    </div>
                </div>
                
                <div class="lives-section">
                    <h2>💰 LIVES Encontradas</h2>
                    <div class="search-box">
                        <input type="text" id="search-input" placeholder="Buscar por CC, banco, país...">
                        <button onclick="searchLives()">Buscar</button>
                    </div>
                    <div class="lives-container" id="lives">
                        <div class="log-entry info">Esperando LIVES...</div>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            function changeChannel() {
                const channel = document.getElementById('channel-input').value;
                if (!channel) {
                    alert('Por favor ingresa un ID de canal');
                    return;
                }
                
                const formData = new FormData();
                formData.append('channel', channel);
                
                fetch('/set_channel', {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.ok) {
                        alert('✓ ' + data.message);
                        document.getElementById('channel-input').value = '';
                        updateLogs();
                    } else {
                        alert('Error: ' + data.message);
                    }
                })
                .catch(error => console.error('Error:', error));
            }
            
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
                            <span style="color: #2ecc71;">✅ LIVE</span>
                        </div>
                        <div class="live-card-info">🏦 <strong>Banco:</strong> ${live.bank}</div>
                        <div class="live-card-info">🗺️ <strong>País:</strong> ${live.country}</div>
                        <div class="live-card-info">💰 <strong>Tipo:</strong> ${live.type}</div>
                        <div class="live-card-info">💵 <strong>Gate:</strong> ${live.gate}</div>
                        <div class="live-card-info">✅ <strong>Status:</strong> ${live.status}</div>
                        <div class="live-card-timestamp">🕐 ${live.timestamp}</div>
                    </div>
                `).join('');
            }
            
            function searchLives() {
                const searchText = document.getElementById('search-input').value;
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
                        document.getElementById('logs').innerHTML = data.log
                            .split('\\n')
                            .map(line => {
                                let className = 'info';
                                if (line.includes('✓') || line.includes('APPROVED')) className = 'approved';
                                else if (line.includes('✗') || line.includes('DECLINED')) className = 'declined';
                                else if (line.includes('ERROR')) className = 'error';
                                else if (line.includes('WARNING') || line.includes('⚠️')) className = 'warning';
                                return `<div class="log-entry ${className}">${line}</div>`;
                            })
                            .join('');
                        
                        document.getElementById('approved').textContent = data.approved;
                        document.getElementById('declined').textContent = data.declined;
                        
                        // Auto scroll al final
                        const logsContainer = document.getElementById('logs');
                        logsContainer.scrollTop = logsContainer.scrollHeight;
                    });
                
                // Actualizar lives
                fetch('/get_lives')
                    .then(response => response.json())
                    .then(data => {
                        document.getElementById('lives-count').textContent = data.lives.length;
                        displayLives(data.lives);
                        
                        // Auto scroll al final
                        const livesContainer = document.getElementById('lives');
                        livesContainer.scrollTop = livesContainer.scrollHeight;
                    });
            }
            
            // Actualizar logs cada 2 segundos
            setInterval(updateLogs, 2000);
            updateLogs();
            
            // Permitir Enter para cambiar canal
            document.getElementById('channel-input').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') changeChannel();
            });
            
            // Permitir Enter para buscar
            document.getElementById('search-input').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') searchLives();
            });
        </script>
    </body>
    </html>
    '''
    return render_template_string(html, log='\n'.join(log_messages[-50:]), approved=approved_count, declined=declined_count)

@app.route('/set_channel', methods=['POST'])
def set_channel():
    """Cambia el canal de destino"""
    global channelid
    new_channel = request.form.get('channel')
    try:
        channelid = int(new_channel)
    except ValueError:
        channelid = new_channel
    log_messages.append(f"✓ Canal actualizado a {channelid}")
    return jsonify({"ok": True, "message": f"Canal actualizado a {channelid}"})

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
    # Iniciar Telethon en hilo separado
    telethon_thread = threading.Thread(target=telethon_thread_fn, daemon=True)
    telethon_thread.start()
    time.sleep(2)
    
    # Iniciar Flask
    app.run('0.0.0.0', PORT, debug=False)
