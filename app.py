import threading
import asyncio
import random
import time
import os
import json
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, jsonify
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

# Crear cliente
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

log_messages = []
lives_list = []
channelid = -1003101739772
approved_count = 0
declined_count = 0
app = Flask(__name__)
LIVES_FILE = 'lives_database.json'

# ============ CARGAR LIVES DEL ARCHIVO ============
def load_lives_from_file():
    """Carga lives guardadas del archivo"""
    global lives_list
    if os.path.exists(LIVES_FILE):
        try:
            with open(LIVES_FILE, 'r', encoding='utf-8') as f:
                lives_list = json.load(f)
            log_messages.append(f"✅ Cargadas {len(lives_list)} LIVES del archivo")
        except Exception as e:
            log_messages.append(f"❌ Error cargando lives: {e}")
            lives_list = []
    else:
        lives_list = []

def save_lives_to_file():
    """Guarda lives en archivo JSON"""
    try:
        with open(LIVES_FILE, 'w', encoding='utf-8') as f:
            json.dump(lives_list, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log_messages.append(f"❌ Error guardando lives: {e}")

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
        checksum += sum(digits_of(d*2))
    return checksum % 10

def generate_luhn_digit(partial_card):
    """Genera el dígito de verificación de Luhn"""
    check_digit = luhn_checksum(str(partial_card) + '0')
    return (10 - check_digit) % 10

def is_date_valid(month, year):
    """Verifica si una fecha MM/YY es válida"""
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

    elif "❌" in full_message or "declined" in message_lower:
        declined_count += 1
        log_messages.append(f"❌ DECLINADA")

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

                log_messages.append(f"🔄 Scrapper - Procesando: {current_cc[:12]}...")
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
                                log_messages.append(f"✓ Enviado #{num}/20")
                            except FloodWaitError as e:
                                log_messages.append(f"⏸️ Esperando {e.seconds}s...")
                                await asyncio.sleep(e.seconds)
                            except RPCError as e:
                                log_messages.append(f"❌ Error: {e}")

                        tasks.append(send_cc(message, j))

                    await asyncio.gather(*tasks)
                    await asyncio.sleep(21)

                log_messages.append(f"🎉 Lote completado: 20/20")
            else:
                log_messages.append("⏳ Sin CCs en cola...")
                await asyncio.sleep(20)

        except Exception as e:
            log_messages.append(f"❌ Error: {e}")
            await asyncio.sleep(20)

async def start_client():
    """Inicia el cliente de Telegram - SIN PEDIR TELÉFONO"""
    try:
        log_messages.append("🚀 Iniciando Scrapper...")
        
        # Si ya existe sesión, no pide teléfono
        if client.is_connected():
            log_messages.append("✅ Scrapper ya conectado")
        else:
            await client.start()
            log_messages.append("✅ Scrapper conectado")
        
        client.add_event_handler(response_handler, events.MessageEdited(chats='@Alphachekerbot'))
        await asyncio.gather(send_to_bot(), client.run_until_disconnected())
    except Exception as e:
        log_messages.append(f"❌ Error: {e}")

def telethon_thread_fn():
    """Ejecuta Telethon en hilo separado"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(start_client())
    except:
        pass

# Cargar lives al iniciar
load_lives_from_file()

# ============ RUTAS FLASK ============
@app.route('/')
def index():
    """Panel principal"""
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Scrapper Control</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                background: #0a0a0a;
                color: #fff;
                font-family: monospace;
                padding: 20px;
            }
            .container { max-width: 1200px; margin: 0 auto; }
            .header {
                text-align: center;
                padding: 20px;
                background: #1a1a1a;
                border: 2px solid #00ff88;
                margin-bottom: 20px;
                border-radius: 5px;
            }
            .header h1 { color: #00ff88; font-size: 2em; }
            .stats {
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 10px;
                margin: 20px 0;
            }
            .stat {
                background: #1a1a1a;
                padding: 15px;
                border: 1px solid #00ff88;
                text-align: center;
                border-radius: 5px;
            }
            .stat-num { font-size: 2em; color: #00ff88; font-weight: bold; }
            .logs {
                background: #1a1a1a;
                border: 1px solid #00ff88;
                padding: 10px;
                height: 300px;
                overflow-y: auto;
                margin: 20px 0;
                border-radius: 5px;
            }
            .log-line { 
                padding: 2px 0;
                border-bottom: 1px solid #333;
                font-size: 0.9em;
            }
            .lives {
                background: #1a1a1a;
                border: 1px solid #00ff88;
                padding: 10px;
                height: 400px;
                overflow-y: auto;
                margin: 20px 0;
                border-radius: 5px;
            }
            .live-item {
                background: #0a3a0a;
                padding: 10px;
                margin: 5px 0;
                border-left: 3px solid #00ff88;
                font-size: 0.85em;
            }
            h2 { color: #00ff88; margin: 10px 0; }
            ::-webkit-scrollbar { width: 8px; }
            ::-webkit-scrollbar-track { background: #1a1a1a; }
            ::-webkit-scrollbar-thumb { background: #00ff88; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔥 Scrapper Control 💳</h1>
            </div>

            <div class="stats">
                <div class="stat">
                    <div>✅ LIVES</div>
                    <div class="stat-num" id="approved">0</div>
                </div>
                <div class="stat">
                    <div>❌ DECLINADAS</div>
                    <div class="stat-num" id="declined">0</div>
                </div>
                <div class="stat">
                    <div>📊 TOTAL</div>
                    <div class="stat-num" id="total">0</div>
                </div>
            </div>

            <h2>📝 LOG EN VIVO</h2>
            <div class="logs" id="logs"></div>

            <h2>💰 LIVES ENCONTRADAS</h2>
            <div class="lives" id="lives"></div>
        </div>

        <script>
            setInterval(function() {
                fetch('/get_logs')
                    .then(r => r.json())
                    .then(data => {
                        let html = '';
                        data.forEach(log => {
                            html += '<div class="log-line">' + log + '</div>';
                        });
                        document.getElementById('logs').innerHTML = html;
                        document.getElementById('logs').scrollTop = document.getElementById('logs').scrollHeight;
                    });
            }, 1000);

            setInterval(function() {
                fetch('/get_lives')
                    .then(r => r.json())
                    .then(data => {
                        let html = '';
                        data.forEach(live => {
                            html += '<div class="live-item">' +
                                '<strong>CC:</strong> ' + live.cc + '<br>' +
                                '<strong>Status:</strong> ' + live.status + '<br>' +
                                '<strong>Country:</strong> ' + live.country + '<br>' +
                                '<strong>Bank:</strong> ' + live.bank + '<br>' +
                                '<strong>Gate:</strong> ' + live.gate +
                            '</div>';
                        });
                        document.getElementById('lives').innerHTML = html || '<div class="log-line">Sin lives...</div>';
                    });
            }, 2000);

            setInterval(function() {
                fetch('/api/stats')
                    .then(r => r.json())
                    .then(data => {
                        document.getElementById('approved').innerText = data.approved;
                        document.getElementById('declined').innerText = data.declined;
                        document.getElementById('total').innerText = data.total;
                    });
            }, 2000);
        </script>
    </body>
    </html>
    '''
    return render_template_string(html)

@app.route('/get_logs')
def get_logs():
    """API para logs"""
    return jsonify(log_messages[-50:])

@app.route('/get_lives')
def get_lives():
    """API para lives"""
    return jsonify(lives_list[-20:])

@app.route('/api/stats')
def get_stats():
    """API para estadísticas"""
    return jsonify({
        'approved': approved_count,
        'declined': declined_count,
        'total': approved_count + declined_count
    })

# ============ INICIAR ============
if __name__ == '__main__':
    try:
        telethon_thread = threading.Thread(target=telethon_thread_fn, daemon=True)
        telethon_thread.start()
        
        log_messages.append("🚀 Panel web iniciado...")
        app.run(host='0.0.0.0', port=PORT, debug=False)
    except KeyboardInterrupt:
        log_messages.append("❌ Detenido")
    except Exception as e:
        log_messages.append(f"❌ Error: {e}")
