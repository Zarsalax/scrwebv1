#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TEAM REDCARDS - Aplicación Web con Flask
Owner: @Neokotaro - TEAM-RDA
Versión: 3.0 WEB
"""

import subprocess
import sys
import os

# Auto-instalador de dependencias
def instalar_dependencias():
    dependencias = ['flask', 'telethon', 'requests']

    for dep in dependencias:
        try:
            __import__(dep)
        except ImportError:
            print(f"📦 Instalando {dep}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", dep])

instalar_dependencias()

from flask import Flask, render_template_string, request, jsonify, session
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError
import asyncio
import random
import time
from datetime import datetime
import json
from pathlib import Path
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# Configuración Telethon
API_ID = 22154650
API_HASH = "2b554e270efb419af271c47ffe1d72d3"
SESSION_FILE = "teamredcards_web_session"
BOT_USERNAME = "@Alphachekerbot"

# Variables globales
client = None
authenticated = False
logs = []
lives = []
super_lives = []
stats = {
    "total_chk": 0,
    "lives": 0,
    "super_lives": 0,
    "deads": 0
}
checking_active = False

# HTML Template con interfaz completa
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TEAM REDCARDS - Web Interface</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0D1117 0%, #1a1a2e 100%);
            color: #ffffff;
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }

        .header {
            text-align: center;
            padding: 30px 0;
            border-bottom: 3px solid #FF1744;
            margin-bottom: 30px;
        }

        .header h1 {
            font-size: 3em;
            color: #FF1744;
            text-shadow: 0 0 20px rgba(255, 23, 68, 0.5);
            margin-bottom: 10px;
        }

        .header p {
            color: #00FF00;
            font-size: 1.2em;
        }

        .auth-section {
            background: rgba(28, 28, 28, 0.9);
            border: 2px solid #FF1744;
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 8px 32px rgba(255, 23, 68, 0.3);
        }

        .auth-section h2 {
            color: #FF1744;
            margin-bottom: 20px;
        }

        .form-group {
            margin-bottom: 20px;
        }

        .form-group label {
            display: block;
            margin-bottom: 8px;
            color: #00FF00;
            font-weight: bold;
        }

        .form-group input {
            width: 100%;
            padding: 12px;
            background: #0D1117;
            border: 2px solid #FF1744;
            border-radius: 6px;
            color: #ffffff;
            font-size: 16px;
        }

        .form-group input:focus {
            outline: none;
            border-color: #00FF00;
            box-shadow: 0 0 10px rgba(0, 255, 0, 0.3);
        }

        .btn {
            padding: 12px 30px;
            background: #FF1744;
            color: #ffffff;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
            transition: all 0.3s;
        }

        .btn:hover {
            background: #00FF00;
            transform: scale(1.05);
            box-shadow: 0 4px 15px rgba(0, 255, 0, 0.4);
        }

        .btn:disabled {
            background: #555;
            cursor: not-allowed;
            transform: none;
        }

        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 30px;
        }

        .panel {
            background: rgba(28, 28, 28, 0.9);
            border: 2px solid #FF1744;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }

        .panel h3 {
            color: #FF1744;
            margin-bottom: 15px;
            font-size: 1.5em;
        }

        .stats {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            margin-bottom: 30px;
        }

        .stat-card {
            background: rgba(28, 28, 28, 0.9);
            border: 2px solid #FF1744;
            border-radius: 8px;
            padding: 20px;
            text-align: center;
        }

        .stat-card h4 {
            color: #00FF00;
            font-size: 0.9em;
            margin-bottom: 10px;
        }

        .stat-card .value {
            font-size: 2em;
            font-weight: bold;
            color: #FF1744;
        }

        .log-container {
            background: #0D1117;
            border: 2px solid #FF1744;
            border-radius: 8px;
            padding: 15px;
            height: 400px;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
        }

        .log-entry {
            padding: 5px;
            margin-bottom: 5px;
            border-left: 3px solid #FF1744;
            padding-left: 10px;
        }

        .log-entry.success { border-left-color: #00FF00; color: #00FF00; }
        .log-entry.error { border-left-color: #FF0000; color: #FF0000; }
        .log-entry.info { border-left-color: #00BFFF; color: #00BFFF; }
        .log-entry.warning { border-left-color: #FFA500; color: #FFA500; }

        .lives-list {
            background: #0D1117;
            border: 2px solid #00FF00;
            border-radius: 8px;
            padding: 15px;
            height: 300px;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
        }

        .live-item {
            padding: 8px;
            margin-bottom: 5px;
            background: rgba(0, 255, 0, 0.1);
            border-radius: 4px;
            color: #00FF00;
        }

        .super-live-item {
            padding: 8px;
            margin-bottom: 5px;
            background: rgba(255, 165, 0, 0.1);
            border-radius: 4px;
            color: #FFA500;
        }

        @media (max-width: 768px) {
            .grid {
                grid-template-columns: 1fr;
            }

            .stats {
                grid-template-columns: repeat(2, 1fr);
            }
        }

        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }

        .status-indicator.online { background: #00FF00; }
        .status-indicator.offline { background: #FF0000; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎮 TEAM REDCARDS</h1>
            <p>Owner: @Neokotaro | TEAM-RDA</p>
        </div>

        <!-- Sección de Autenticación -->
        <div class="auth-section" id="auth-section">
            <h2>🔐 Autenticación Telegram</h2>
            <div id="auth-status">
                <span class="status-indicator" id="status-dot"></span>
                <span id="status-text">Desconectado</span>
            </div>

            <div class="form-group" id="phone-group">
                <label>📱 Número de Teléfono:</label>
                <input type="text" id="phone" placeholder="+34612345678">
                <button class="btn" onclick="sendCode()">📤 Enviar Código</button>
            </div>

            <div class="form-group" id="code-group" style="display:none;">
                <label>🔐 Código de Verificación:</label>
                <input type="text" id="code" placeholder="12345">
                <button class="btn" onclick="verifyCode()">✅ Verificar</button>
            </div>

            <div class="form-group" id="password-group" style="display:none;">
                <label>🔑 Contraseña 2FA (si aplica):</label>
                <input type="password" id="password" placeholder="Contraseña">
            </div>
        </div>

        <!-- Estadísticas -->
        <div class="stats">
            <div class="stat-card">
                <h4>CHK CCS</h4>
                <div class="value" id="stat-total">0</div>
            </div>
            <div class="stat-card">
                <h4>LIVES</h4>
                <div class="value" id="stat-lives" style="color:#00FF00">0</div>
            </div>
            <div class="stat-card">
                <h4>SUPER LIVES</h4>
                <div class="value" id="stat-super" style="color:#FFA500">0</div>
            </div>
            <div class="stat-card">
                <h4>DEADS</h4>
                <div class="value" id="stat-deads" style="color:#FF0000">0</div>
            </div>
        </div>

        <!-- Grid Principal -->
        <div class="grid">
            <!-- Panel de Control -->
            <div class="panel">
                <h3>⚙️ Control de Checking</h3>

                <div class="form-group">
                    <label>Gateway:</label>
                    <select id="gateway" style="width:100%; padding:12px; background:#0D1117; border:2px solid #FF1744; border-radius:6px; color:#fff;">
                        <option>Paypal</option>
                        <option>Stripe</option>
                        <option>Braintree</option>
                        <option>Adyen</option>
                        <option>Chase</option>
                        <option>MercadoPago</option>
                    </select>
                </div>

                <div class="form-group">
                    <label>BIN:</label>
                    <input type="text" id="bin" placeholder="438108">
                </div>

                <div class="form-group">
                    <label>Cantidad:</label>
                    <input type="number" id="cantidad" value="50" min="1" max="1000">
                </div>

                <button class="btn" onclick="startChecking()" id="start-btn">▶️ INICIAR CHECKING</button>
                <button class="btn" onclick="stopChecking()" id="stop-btn" disabled>⏹️ DETENER</button>
            </div>

            <!-- Panel de Log -->
            <div class="panel">
                <h3>📝 Log en Tiempo Real</h3>
                <div class="log-container" id="log-container"></div>
                <button class="btn" onclick="clearLogs()" style="margin-top:10px;">🗑️ Limpiar Log</button>
            </div>
        </div>

        <!-- Grid de Resultados -->
        <div class="grid">
            <!-- Super Lives -->
            <div class="panel">
                <h3>💎 Super Lives</h3>
                <div class="lives-list" id="super-lives-list"></div>
            </div>

            <!-- Lives -->
            <div class="panel">
                <h3>✅ Lives</h3>
                <div class="lives-list" id="lives-list"></div>
            </div>
        </div>
    </div>

    <script>
        // Actualizar estadísticas cada 1 segundo
        setInterval(updateStats, 1000);
        setInterval(updateLogs, 1000);
        setInterval(updateLives, 1000);
        setInterval(checkAuthStatus, 3000);

        async function checkAuthStatus() {
            const response = await fetch('/check_auth');
            const data = await response.json();

            const statusDot = document.getElementById('status-dot');
            const statusText = document.getElementById('status-text');

            if (data.authenticated) {
                statusDot.className = 'status-indicator online';
                statusText.textContent = 'Conectado ✅';
                document.getElementById('auth-section').style.display = 'none';
            } else {
                statusDot.className = 'status-indicator offline';
                statusText.textContent = 'Desconectado ❌';
            }
        }

        async function sendCode() {
            const phone = document.getElementById('phone').value;

            const response = await fetch('/auth/send_code', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({phone: phone})
            });

            const data = await response.json();

            if (data.success) {
                document.getElementById('phone-group').style.display = 'none';
                document.getElementById('code-group').style.display = 'block';
                alert('✅ Código enviado! Revisa tu Telegram');
            } else {
                alert('❌ Error: ' + data.message);
            }
        }

        async function verifyCode() {
            const code = document.getElementById('code').value;
            const password = document.getElementById('password').value;

            const response = await fetch('/auth/verify_code', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({code: code, password: password})
            });

            const data = await response.json();

            if (data.success) {
                alert('✅ ¡Autenticación exitosa!');
                location.reload();
            } else {
                if (data.need_password) {
                    document.getElementById('password-group').style.display = 'block';
                }
                alert('❌ Error: ' + data.message);
            }
        }

        async function startChecking() {
            const bin = document.getElementById('bin').value;
            const cantidad = document.getElementById('cantidad').value;
            const gateway = document.getElementById('gateway').value;

            if (!bin) {
                alert('❌ Ingresa un BIN');
                return;
            }

            const response = await fetch('/checking/start', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({bin: bin, cantidad: cantidad, gateway: gateway})
            });

            const data = await response.json();

            if (data.success) {
                document.getElementById('start-btn').disabled = true;
                document.getElementById('stop-btn').disabled = false;
            } else {
                alert('❌ Error: ' + data.message);
            }
        }

        async function stopChecking() {
            await fetch('/checking/stop', {method: 'POST'});
            document.getElementById('start-btn').disabled = false;
            document.getElementById('stop-btn').disabled = true;
        }

        async function updateStats() {
            const response = await fetch('/get_stats');
            const data = await response.json();

            document.getElementById('stat-total').textContent = data.total_chk;
            document.getElementById('stat-lives').textContent = data.lives;
            document.getElementById('stat-super').textContent = data.super_lives;
            document.getElementById('stat-deads').textContent = data.deads;
        }

        async function updateLogs() {
            const response = await fetch('/get_logs');
            const data = await response.json();

            const container = document.getElementById('log-container');
            container.innerHTML = '';

            data.logs.slice(-50).forEach(log => {
                const entry = document.createElement('div');
                entry.className = 'log-entry ' + log.type;
                entry.textContent = `[${log.time}] ${log.message}`;
                container.appendChild(entry);
            });

            container.scrollTop = container.scrollHeight;
        }

        async function updateLives() {
            const response = await fetch('/get_lives');
            const data = await response.json();

            const superList = document.getElementById('super-lives-list');
            const livesList = document.getElementById('lives-list');

            superList.innerHTML = '';
            data.super_lives.forEach(card => {
                const item = document.createElement('div');
                item.className = 'super-live-item';
                item.textContent = '💎 ' + card;
                superList.appendChild(item);
            });

            livesList.innerHTML = '';
            data.lives.forEach(card => {
                const item = document.createElement('div');
                item.className = 'live-item';
                item.textContent = '✅ ' + card;
                livesList.appendChild(item);
            });
        }

        function clearLogs() {
            fetch('/clear_logs', {method: 'POST'});
        }

        // Cargar estado inicial
        checkAuthStatus();
        updateStats();
        updateLogs();
        updateLives();
    </script>
</body>
</html>
"""

def add_log(message, log_type="info"):
    """Agrega un log"""
    logs.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "message": message,
        "type": log_type
    })
    print(f"[{log_type.upper()}] {message}")

@app.route('/')
def index():
    """Página principal"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/check_auth')
def check_auth():
    """Verifica estado de autenticación"""
    global authenticated, client

    # Verificar si existe sesión
    session_path = Path(f"{SESSION_FILE}.session")

    if session_path.exists() and not authenticated:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def connect():
                global client, authenticated
                client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
                await client.connect()

                if await client.is_user_authorized():
                    authenticated = True
                    add_log("✅ Conectado con sesión existente", "success")
                    return True
                return False

            result = loop.run_until_complete(connect())

        except Exception as e:
            add_log(f"❌ Error en conexión: {str(e)}", "error")

    return jsonify({"authenticated": authenticated})

@app.route('/auth/send_code', methods=['POST'])
def send_code():
    """Envía código de verificación"""
    global client

    data = request.json
    phone = data.get('phone', '')

    if not phone.startswith('+'):
        phone = '+' + phone

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def send():
            global client
            client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
            await client.connect()
            result = await client.send_code_request(phone)
            session['phone'] = phone
            session['phone_code_hash'] = result.phone_code_hash
            add_log(f"✅ Código enviado a {phone}", "success")
            return True

        result = loop.run_until_complete(send())

        return jsonify({"success": True})

    except Exception as e:
        add_log(f"❌ Error: {str(e)}", "error")
        return jsonify({"success": False, "message": str(e)})

@app.route('/auth/verify_code', methods=['POST'])
def verify_code():
    """Verifica código de autenticación"""
    global client, authenticated

    data = request.json
    code = data.get('code', '')
    password = data.get('password', '')

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def verify():
            global authenticated

            phone = session.get('phone')
            phone_code_hash = session.get('phone_code_hash')

            try:
                await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
                authenticated = True
                add_log("✅ Autenticación exitosa", "success")
                return {"success": True, "need_password": False}

            except SessionPasswordNeededError:
                if password:
                    await client.sign_in(password=password)
                    authenticated = True
                    add_log("✅ Autenticación exitosa con 2FA", "success")
                    return {"success": True, "need_password": False}
                else:
                    return {"success": False, "need_password": True, "message": "Se requiere contraseña 2FA"}

        result = loop.run_until_complete(verify())
        return jsonify(result)

    except Exception as e:
        add_log(f"❌ Error: {str(e)}", "error")
        return jsonify({"success": False, "message": str(e)})

@app.route('/checking/start', methods=['POST'])
def start_checking():
    """Inicia checking"""
    global checking_active, stats

    if not authenticated:
        return jsonify({"success": False, "message": "Debes autenticarte primero"})

    data = request.json
    bin_code = data.get('bin', '')
    cantidad = int(data.get('cantidad', 50))
    gateway = data.get('gateway', 'Paypal')

    checking_active = True
    add_log(f"🚀 Iniciando checking con {cantidad} CCS", "info")
    add_log(f"BIN: {bin_code} | Gateway: {gateway}", "info")

    # Simular checking
    import threading

    def do_checking():
        global checking_active, stats, lives, super_lives

        for i in range(cantidad):
            if not checking_active:
                break

            # Generar tarjeta
            cuerpo = ''.join(str(random.randint(0, 9)) for _ in range(10))
            fecha = f"{random.randint(1,12):02d}/{random.randint(25,35):02d}"
            cvv = str(random.randint(100, 999))
            tarjeta = f"{bin_code}{cuerpo}|{fecha}|{cvv}"

            # Simular resultado
            result = random.choices(
                ["live", "super_live", "dead"],
                weights=[15, 5, 80]
            )[0]

            stats["total_chk"] += 1

            if result == "live":
                stats["lives"] += 1
                lives.append(tarjeta)
                add_log(f"✅ LIVE: {tarjeta}", "success")
            elif result == "super_live":
                stats["super_lives"] += 1
                super_lives.append(tarjeta)
                add_log(f"💎 SUPER LIVE: {tarjeta}", "warning")
            else:
                stats["deads"] += 1

            time.sleep(0.3)

        checking_active = False
        add_log("✅ Checking completado", "success")

    thread = threading.Thread(target=do_checking)
    thread.start()

    return jsonify({"success": True})

@app.route('/checking/stop', methods=['POST'])
def stop_checking():
    """Detiene checking"""
    global checking_active
    checking_active = False
    add_log("⏹️ Checking detenido", "warning")
    return jsonify({"success": True})

@app.route('/get_stats')
def get_stats():
    """Obtiene estadísticas"""
    return jsonify(stats)

@app.route('/get_logs')
def get_logs():
    """Obtiene logs"""
    return jsonify({"logs": logs})

@app.route('/get_lives')
def get_lives():
    """Obtiene lives"""
    return jsonify({
        "lives": lives,
        "super_lives": super_lives
    })

@app.route('/clear_logs', methods=['POST'])
def clear_logs():
    """Limpia logs"""
    global logs
    logs = []
    return jsonify({"success": True})

if __name__ == '__main__':
    print("🚀 TEAM REDCARDS Web Interface")
    print("Owner: @Neokotaro - TEAM-RDA")
    print("")
    print("🌐 Servidor iniciando...")
    print("📍 Accede a: http://0.0.0.0:8080")
    print("")

    app.run(host='0.0.0.0', port=8080, debug=False)
