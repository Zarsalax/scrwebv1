import threading
import asyncio
import random
import time
import os
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
channelid = -1003101739772  # ID del canal Team RedCards
approved_count = 0
declined_count = 0
app = Flask(__name__)

# ============ FUNCIONES UTILITARIAS ============

def luhn_checksum(cardnumber):
    """Algoritmo de Luhn para validar tarjetas"""
    digits = [int(d) for d in str(cardnumber)]
    odd = digits[-1::-2]
    even = digits[-2::-2]
    checksum = sum(odd)
    for d in even:
        checksum += sum([int(x) for x in str(d * 2)])
    return checksum % 10

def generate_luhn_digit(partial_cardnumber):
    """Genera un dígito de verificación válido según Luhn"""
    checksum = 0
    for i, digit in enumerate(reversed(partial_cardnumber)):
        d = int(digit)
        if i % 2 == 0:
            checksum += d
        else:
            checksum += sum([int(x) for x in str(d * 2)])
    return (10 - (checksum % 10)) % 10

def generate_cc_variants(ccbase, count=10):
    """Genera variantes de tarjetas con algoritmo de Luhn"""
    parts = ccbase.strip().split(',')
    
    if len(parts) >= 3:
        cardnumber = parts[0]
        month = parts[1]
        year = parts[2]
    else:
        cardnumber = ccbase
        month = '12'
        year = '25'
    
    if len(cardnumber) < 12:
        return []
    
    base_number = cardnumber[:-4]
    variants = []
    attempts = 0
    
    while len(variants) < count and attempts < count * 3:
        attempts += 1
        random_digits = str(random.randint(0, 9)) + str(random.randint(0, 9)) + str(random.randint(0, 9))
        partial_number = base_number + random_digits
        luhn_digit = generate_luhn_digit(partial_number)
        complete_number = partial_number + str(luhn_digit)
        
        if luhn_checksum(complete_number) == 0:
            cvv = random.randint(100, 999)
            variant = f"{complete_number},{month},{year},{cvv}"
            if variant not in variants:
                variants.append(variant)
    
    return variants

# ============ MANEJADOR DE EVENTOS ============

async def response_handler(event):
    """Maneja respuestas de mensajes aprobados/rechazados"""
    global approved_count, declined_count, channelid
    
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
        
        # ✅ NUEVO FORMATO - Team RedCards (MEJORADO Y SIMPLIFICADO)
        formatted_message = f"""╔══════════════════════════╗
     Team RedCards 💳
╚══════════════════════════╝

💳 **CC:** `{cc_number}`
✅ **Status:** {status}
📊 **Response:** {response}

🗺️ **Country:** {country}
🏦 **Bank:** {bank}
💰 **Type:** {card_type}
💵 **GATE:** {gate}"""
        
        # ENVIAR AL CANAL - SIN BOTÓN DE BUY VIP (MEJORADO)
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
    """Envía CCs al bot de Telegram"""
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
                
                log_messages.append(f"INFO: Generando variantes para {current_cc[:12]}...")
                cc_variants = generate_cc_variants(current_cc, 10)
                
                if not cc_variants:
                    log_messages.append(f"ERROR: No se pudieron generar variantes")
                    await asyncio.sleep(20)
                    continue
                
                commands = await load_commands()
                
                for i in range(0, len(cc_variants), 2):
                    pair = cc_variants[i:i+2]
                    for cc in pair:
                        selected_command = random.choice(commands)
                        message = f"{selected_command} {cc}"
                        
                        try:
                            await client.send_message('@Alphachekerbot', message)
                            log_messages.append(f"✓ Enviado: {cc[:12]}...")
                        except FloodWaitError as e:
                            log_messages.append(f"WARNING: Esperando {e.seconds}s...")
                            await asyncio.sleep(e.seconds)
                        except RPCError as e:
                            log_messages.append(f"ERROR RPC: {e}")
                        
                        await asyncio.sleep(21)
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
                max-width: 1200px;
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
            .logs-section {
                background: rgba(255, 255, 255, 0.05);
                padding: 25px;
                border-radius: 10px;
                border: 1px solid rgba(231, 76, 60, 0.3);
            }
            .logs-section h2 {
                margin-bottom: 20px;
                color: #e74c3c;
                font-size: 1.5em;
            }
            .logs-container {
                background: rgba(0, 0, 0, 0.3);
                padding: 15px;
                border-radius: 5px;
                height: 400px;
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
            /* Scrollbar personalizado */
            .logs-container::-webkit-scrollbar {
                width: 8px;
            }
            .logs-container::-webkit-scrollbar-track {
                background: rgba(0, 0, 0, 0.1);
                border-radius: 10px;
            }
            .logs-container::-webkit-scrollbar-thumb {
                background: #e74c3c;
                border-radius: 10px;
            }
            .logs-container::-webkit-scrollbar-thumb:hover {
                background: #c0392b;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>💳 Team RedCards</h1>
                <p>Panel de Control - CC Checker Bot</p>
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
                    <h3>📊 Total</h3>
                    <div class="number" id="total">{{ approved + declined }}</div>
                </div>
            </div>
            
            <div class="control-panel">
                <h2>⚙️ Cambiar Canal</h2>
                <div class="form-group">
                    <input type="text" id="channel-input" placeholder="Ingresa el ID del canal (ej: -1003101739772)">
                    <button onclick="changeChannel()">Cambiar</button>
                </div>
            </div>
            
            <div class="logs-section">
                <h2>📋 Logs en Tiempo Real</h2>
                <div class="logs-container" id="logs">
                    {{ log }}
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
                                else if (line.includes('WARNING')) className = 'warning';
                                return `<div class="log-entry ${className}">${line}</div>`;
                            })
                            .join('');
                        
                        document.getElementById('approved').textContent = data.approved;
                        document.getElementById('declined').textContent = data.declined;
                        document.getElementById('total').textContent = data.approved + data.declined;
                        
                        // Auto scroll al final
                        const logsContainer = document.getElementById('logs');
                        logsContainer.scrollTop = logsContainer.scrollHeight;
                    });
            }
            
            // Actualizar logs cada 2 segundos
            setInterval(updateLogs, 2000);
            updateLogs();
            
            // Permitir Enter para cambiar canal
            document.getElementById('channel-input').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') changeChannel();
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

@app.route('/health')
def health():
    """Health check para Railway"""
    return jsonify({"status": "ok", "approved": approved_count, "declined": declined_count})

# ============ INICIO ============

if __name__ == '__main__':
    # Iniciar Telethon en hilo separado
    telethon_thread = threading.Thread(target=telethon_thread_fn, daemon=True)
    telethon_thread.start()
    time.sleep(2)
    
    # Iniciar Flask
    app.run('0.0.0.0', PORT, debug=False)
