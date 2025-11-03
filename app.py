import threading
import asyncio
import random
import time
import os
import json
import requests
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, jsonify
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, RPCError

# ==================== CONFIGURACIÓN ====================
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
LIVES_FILE = 'lives_database.json'

# ==================== DICCIONARIO DE BANDERAS ====================
country_flags = {
    "Afghanistan": "https://flagcdn.com/w320/af.png",
    "Albania": "https://flagcdn.com/w320/al.png",
    "Algeria": "https://flagcdn.com/w320/dz.png",
    "Andorra": "https://flagcdn.com/w320/ad.png",
    "Angola": "https://flagcdn.com/w320/ao.png",
    "Antigua and Barbuda": "https://flagcdn.com/w320/ag.png",
    "Argentina": "https://flagcdn.com/w320/ar.png",
    "Armenia": "https://flagcdn.com/w320/am.png",
    "Australia": "https://flagcdn.com/w320/au.png",
    "Austria": "https://flagcdn.com/w320/at.png",
    "Azerbaijan": "https://flagcdn.com/w320/az.png",
    "Bahamas": "https://flagcdn.com/w320/bs.png",
    "Bahrain": "https://flagcdn.com/w320/bh.png",
    "Bangladesh": "https://flagcdn.com/w320/bd.png",
    "Barbados": "https://flagcdn.com/w320/bb.png",
    "Belarus": "https://flagcdn.com/w320/by.png",
    "Belgium": "https://flagcdn.com/w320/be.png",
    "Belize": "https://flagcdn.com/w320/bz.png",
    "Benin": "https://flagcdn.com/w320/bj.png",
    "Bhutan": "https://flagcdn.com/w320/bt.png",
    "Bolivia": "https://flagcdn.com/w320/bo.png",
    "Bosnia and Herzegovina": "https://flagcdn.com/w320/ba.png",
    "Botswana": "https://flagcdn.com/w320/bw.png",
    "Brazil": "https://flagcdn.com/w320/br.png",
    "Brunei": "https://flagcdn.com/w320/bn.png",
    "Bulgaria": "https://flagcdn.com/w320/bg.png",
    "Burkina Faso": "https://flagcdn.com/w320/bf.png",
    "Burundi": "https://flagcdn.com/w320/bi.png",
    "Cambodia": "https://flagcdn.com/w320/kh.png",
    "Cameroon": "https://flagcdn.com/w320/cm.png",
    "Canada": "https://flagcdn.com/w320/ca.png",
    "Cape Verde": "https://flagcdn.com/w320/cv.png",
    "Central African Republic": "https://flagcdn.com/w320/cf.png",
    "Chad": "https://flagcdn.com/w320/td.png",
    "Chile": "https://flagcdn.com/w320/cl.png",
    "China": "https://flagcdn.com/w320/cn.png",
    "Colombia": "https://flagcdn.com/w320/co.png",
    "Comoros": "https://flagcdn.com/w320/km.png",
    "Congo (Brazzaville)": "https://flagcdn.com/w320/cg.png",
    "Congo (Kinshasa)": "https://flagcdn.com/w320/cd.png",
    "Costa Rica": "https://flagcdn.com/w320/cr.png",
    "Croatia": "https://flagcdn.com/w320/hr.png",
    "Cuba": "https://flagcdn.com/w320/cu.png",
    "Cyprus": "https://flagcdn.com/w320/cy.png",
    "Czech Republic": "https://flagcdn.com/w320/cz.png",
    "Denmark": "https://flagcdn.com/w320/dk.png",
    "Djibouti": "https://flagcdn.com/w320/dj.png",
    "Dominica": "https://flagcdn.com/w320/dm.png",
    "Dominican Republic": "https://flagcdn.com/w320/do.png",
    "East Timor": "https://flagcdn.com/w320/tl.png",
    "Ecuador": "https://flagcdn.com/w320/ec.png",
    "Egypt": "https://flagcdn.com/w320/eg.png",
    "El Salvador": "https://flagcdn.com/w320/sv.png",
    "Equatorial Guinea": "https://flagcdn.com/w320/gq.png",
    "Eritrea": "https://flagcdn.com/w320/er.png",
    "Estonia": "https://flagcdn.com/w320/ee.png",
    "Eswatini": "https://flagcdn.com/w320/sz.png",
    "Ethiopia": "https://flagcdn.com/w320/et.png",
    "Fiji": "https://flagcdn.com/w320/fj.png",
    "Finland": "https://flagcdn.com/w320/fi.png",
    "France": "https://flagcdn.com/w320/fr.png",
    "Gabon": "https://flagcdn.com/w320/ga.png",
    "Gambia": "https://flagcdn.com/w320/gm.png",
    "Georgia": "https://flagcdn.com/w320/ge.png",
    "Germany": "https://flagcdn.com/w320/de.png",
    "Ghana": "https://flagcdn.com/w320/gh.png",
    "Greece": "https://flagcdn.com/w320/gr.png",
    "Grenada": "https://flagcdn.com/w320/gd.png",
    "Guatemala": "https://flagcdn.com/w320/gt.png",
    "Guinea": "https://flagcdn.com/w320/gn.png",
    "Guinea-Bissau": "https://flagcdn.com/w320/gw.png",
    "Guyana": "https://flagcdn.com/w320/gy.png",
    "Haiti": "https://flagcdn.com/w320/ht.png",
    "Honduras": "https://flagcdn.com/w320/hn.png",
    "Hungary": "https://flagcdn.com/w320/hu.png",
    "Iceland": "https://flagcdn.com/w320/is.png",
    "India": "https://flagcdn.com/w320/in.png",
    "Indonesia": "https://flagcdn.com/w320/id.png",
    "Iran": "https://flagcdn.com/w320/ir.png",
    "Iraq": "https://flagcdn.com/w320/iq.png",
    "Ireland": "https://flagcdn.com/w320/ie.png",
    "Israel": "https://flagcdn.com/w320/il.png",
    "Italy": "https://flagcdn.com/w320/it.png",
    "Ivory Coast": "https://flagcdn.com/w320/ci.png",
    "Jamaica": "https://flagcdn.com/w320/jm.png",
    "Japan": "https://flagcdn.com/w320/jp.png",
    "Jordan": "https://flagcdn.com/w320/jo.png",
    "Kazakhstan": "https://flagcdn.com/w320/kz.png",
    "Kenya": "https://flagcdn.com/w320/ke.png",
    "Kiribati": "https://flagcdn.com/w320/ki.png",
    "Kosovo": "https://flagcdn.com/w320/xk.png",
    "Kuwait": "https://flagcdn.com/w320/kw.png",
    "Kyrgyzstan": "https://flagcdn.com/w320/kg.png",
    "Laos": "https://flagcdn.com/w320/la.png",
    "Latvia": "https://flagcdn.com/w320/lv.png",
    "Lebanon": "https://flagcdn.com/w320/lb.png",
    "Lesotho": "https://flagcdn.com/w320/ls.png",
    "Liberia": "https://flagcdn.com/w320/lr.png",
    "Libya": "https://flagcdn.com/w320/ly.png",
    "Liechtenstein": "https://flagcdn.com/w320/li.png",
    "Lithuania": "https://flagcdn.com/w320/lt.png",
    "Luxembourg": "https://flagcdn.com/w320/lu.png",
    "Madagascar": "https://flagcdn.com/w320/mg.png",
    "Malawi": "https://flagcdn.com/w320/mw.png",
    "Malaysia": "https://flagcdn.com/w320/my.png",
    "Maldives": "https://flagcdn.com/w320/mv.png",
    "Mali": "https://flagcdn.com/w320/ml.png",
    "Malta": "https://flagcdn.com/w320/mt.png",
    "Marshall Islands": "https://flagcdn.com/w320/mh.png",
    "Mauritania": "https://flagcdn.com/w320/mr.png",
    "Mauritius": "https://flagcdn.com/w320/mu.png",
    "Mexico": "https://flagcdn.com/w320/mx.png",
    "Micronesia": "https://flagcdn.com/w320/fm.png",
    "Moldova": "https://flagcdn.com/w320/md.png",
    "Monaco": "https://flagcdn.com/w320/mc.png",
    "Mongolia": "https://flagcdn.com/w320/mn.png",
    "Montenegro": "https://flagcdn.com/w320/me.png",
    "Morocco": "https://flagcdn.com/w320/ma.png",
    "Mozambique": "https://flagcdn.com/w320/mz.png",
    "Myanmar": "https://flagcdn.com/w320/mm.png",
    "Namibia": "https://flagcdn.com/w320/na.png",
    "Nauru": "https://flagcdn.com/w320/nr.png",
    "Nepal": "https://flagcdn.com/w320/np.png",
    "Netherlands": "https://flagcdn.com/w320/nl.png",
    "New Zealand": "https://flagcdn.com/w320/nz.png",
    "Nicaragua": "https://flagcdn.com/w320/ni.png",
    "Niger": "https://flagcdn.com/w320/ne.png",
    "Nigeria": "https://flagcdn.com/w320/ng.png",
    "North Korea": "https://flagcdn.com/w320/kp.png",
    "North Macedonia": "https://flagcdn.com/w320/mk.png",
    "Norway": "https://flagcdn.com/w320/no.png",
    "Oman": "https://flagcdn.com/w320/om.png",
    "Pakistan": "https://flagcdn.com/w320/pk.png",
    "Palau": "https://flagcdn.com/w320/pw.png",
    "Panama": "https://flagcdn.com/w320/pa.png",
    "Papua New Guinea": "https://flagcdn.com/w320/pg.png",
    "Paraguay": "https://flagcdn.com/w320/py.png",
    "Peru": "https://flagcdn.com/w320/pe.png",
    "Philippines": "https://flagcdn.com/w320/ph.png",
    "Poland": "https://flagcdn.com/w320/pl.png",
    "Portugal": "https://flagcdn.com/w320/pt.png",
    "Qatar": "https://flagcdn.com/w320/qa.png",
    "Romania": "https://flagcdn.com/w320/ro.png",
    "Russia": "https://flagcdn.com/w320/ru.png",
    "Rwanda": "https://flagcdn.com/w320/rw.png",
    "Saint Kitts and Nevis": "https://flagcdn.com/w320/kn.png",
    "Saint Lucia": "https://flagcdn.com/w320/lc.png",
    "Saint Vincent and the Grenadines": "https://flagcdn.com/w320/vc.png",
    "Samoa": "https://flagcdn.com/w320/ws.png",
    "San Marino": "https://flagcdn.com/w320/sm.png",
    "Sao Tome and Principe": "https://flagcdn.com/w320/st.png",
    "Saudi Arabia": "https://flagcdn.com/w320/sa.png",
    "Senegal": "https://flagcdn.com/w320/sn.png",
    "Serbia": "https://flagcdn.com/w320/rs.png",
    "Seychelles": "https://flagcdn.com/w320/sc.png",
    "Sierra Leone": "https://flagcdn.com/w320/sl.png",
    "Singapore": "https://flagcdn.com/w320/sg.png",
    "Slovakia": "https://flagcdn.com/w320/sk.png",
    "Slovenia": "https://flagcdn.com/w320/si.png",
    "Solomon Islands": "https://flagcdn.com/w320/sb.png",
    "Somalia": "https://flagcdn.com/w320/so.png",
    "South Africa": "https://flagcdn.com/w320/za.png",
    "South Korea": "https://flagcdn.com/w320/kr.png",
    "South Sudan": "https://flagcdn.com/w320/ss.png",
    "Spain": "https://flagcdn.com/w320/es.png",
    "Sri Lanka": "https://flagcdn.com/w320/lk.png",
    "Sudan": "https://flagcdn.com/w320/sd.png",
    "Suriname": "https://flagcdn.com/w320/sr.png",
    "Sweden": "https://flagcdn.com/w320/se.png",
    "Switzerland": "https://flagcdn.com/w320/ch.png",
    "Syria": "https://flagcdn.com/w320/sy.png",
    "Taiwan": "https://flagcdn.com/w320/tw.png",
    "Tajikistan": "https://flagcdn.com/w320/tj.png",
    "Tanzania": "https://flagcdn.com/w320/tz.png",
    "Thailand": "https://flagcdn.com/w320/th.png",
    "Togo": "https://flagcdn.com/w320/tg.png",
    "Tonga": "https://flagcdn.com/w320/to.png",
    "Trinidad and Tobago": "https://flagcdn.com/w320/tt.png",
    "Tunisia": "https://flagcdn.com/w320/tn.png",
    "Turkey": "https://flagcdn.com/w320/tr.png",
    "Turkmenistan": "https://flagcdn.com/w320/tm.png",
    "Tuvalu": "https://flagcdn.com/w320/tv.png",
    "Uganda": "https://flagcdn.com/w320/ug.png",
    "Ukraine": "https://flagcdn.com/w320/ua.png",
    "United Arab Emirates": "https://flagcdn.com/w320/ae.png",
    "United Kingdom": "https://flagcdn.com/w320/gb.png",
    "United States": "https://flagcdn.com/w320/us.png",
    "Uruguay": "https://flagcdn.com/w320/uy.png",
    "Uzbekistan": "https://flagcdn.com/w320/uz.png",
    "Vanuatu": "https://flagcdn.com/w320/vu.png",
    "Vatican City": "https://flagcdn.com/w320/va.png",
    "Venezuela": "https://flagcdn.com/w320/ve.png",
    "Vietnam": "https://flagcdn.com/w320/vn.png",
    "Yemen": "https://flagcdn.com/w320/ye.png",
    "Zambia": "https://flagcdn.com/w320/zm.png",
    "Zimbabwe": "https://flagcdn.com/w320/zw.png",
}

# ==================== CARGAR LIVES DEL ARCHIVO ====================
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

def download_flag(flag_url):
    """Descarga la bandera de forma temporal"""
    try:
        response = requests.get(flag_url, timeout=5)
        if response.status_code == 200:
            temp_flag_path = f"flag_{int(time.time())}.png"
            with open(temp_flag_path, 'wb') as f:
                f.write(response.content)
            return temp_flag_path
    except Exception as e:
        log_messages.append(f"⚠️ Error descargando bandera: {e}")
    return None

# ==================== FUNCIONES UTILITARIAS ====================
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
    return variants

# ==================== MANEJADOR DE EVENTOS ====================
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
        
        # Guardar LIVE con fecha
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
            # Obtener URL de la bandera según el país
            flag_url = country_flags.get(country, None)
            
            if flag_url:
                # Descargar bandera
                flag_path = download_flag(flag_url)
                if flag_path:
                    await client.send_file(
                        channelid,
                        flag_path,
                        caption=formatted_message,
                        parse_mode='markdown'
                    )
                    # Limpiar archivo temporal
                    try:
                        os.remove(flag_path)
                    except:
                        pass
                else:
                    await client.send_message(
                        channelid,
                        formatted_message,
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
        log_messages.append(f"❌ DECLINADA")
    
    if len(log_messages) > 100:
        log_messages.pop(0)

# ==================== FUNCIONES DE ENVÍO ====================
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
                
                log_messages.append(f"🔄 Scrapper - Procesando BIN: {current_cc[:12]}...")
                
                cc_variants = generate_cc_variants(current_cc, count=20)
                
                if not cc_variants:
                    log_messages.append(f"❌ Error generando variantes")
                    await asyncio.sleep(20)
                    continue
                
                commands = await load_commands()
                
                # ENVIAR 2 SIMULTÁNEAMENTE - SIN MOSTRAR COMANDOS
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
                                # NO MOSTRAR EL COMANDO COMPLETO, SOLO RESUMEN
                                log_messages.append(f"✓ Scrapper enviado #{num}/20")
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
                
                log_messages.append(f"🎉 Scrapper - Lote completado: 20/20")
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

# ==================== RUTAS FLASK ====================
@app.route('/')
def index():
    """Panel web principal"""
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>SCRAPPER TEAM REDCARDS</title>
        <style>
            body { background: #0a0e27; color: #fff; font-family: 'Courier New'; margin: 0; padding: 20px; }
            .container { max-width: 1200px; margin: 0 auto; }
            h1 { text-align: center; color: #ff4444; text-shadow: 0 0 10px #ff4444; }
            .stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin: 20px 0; }
            .stat-box { background: #1a1f3a; border: 2px solid #ff4444; padding: 20px; text-align: center; border-radius: 5px; }
            .stat-number { font-size: 32px; font-weight: bold; color: #00ff00; }
            .stat-label { color: #888; font-size: 12px; text-transform: uppercase; }
            .logs { background: #1a1f3a; border: 2px solid #00ff00; padding: 15px; border-radius: 5px; height: 400px; overflow-y: auto; font-size: 12px; }
            .log-line { padding: 5px 0; border-bottom: 1px solid #333; }
            .lives { background: #1a1f3a; border: 2px solid #ffff00; padding: 15px; border-radius: 5px; margin-top: 20px; }
            table { width: 100%; font-size: 11px; }
            th { background: #ff4444; color: white; padding: 10px; text-align: left; }
            td { padding: 8px; border-bottom: 1px solid #333; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎮 SCRAPPER TEAM REDCARDS 🔴</h1>
            
            <div class="stats">
                <div class="stat-box">
                    <div class="stat-number">{{ approved }}</div>
                    <div class="stat-label">✅ LIVES</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number">{{ declined }}</div>
                    <div class="stat-label">❌ DECLINADAS</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number">0</div>
                    <div class="stat-label">💎 GUARDADAS</div>
                </div>
            </div>
            
            <h2>🔄 SCRAPPER</h2>
            <div class="logs" id="logs">{{ log }}</div>
            
            <h2>💎 LIVES ENCONTRADAS</h2>
            <div class="lives">
                <table id="lives-table">
                    <thead>
                        <tr>
                            <th>CC</th>
                            <th>Status</th>
                            <th>Country</th>
                            <th>Bank</th>
                            <th>Type</th>
                            <th>Timestamp</th>
                        </tr>
                    </thead>
                    <tbody id="lives-body">
                        <tr><td colspan="6">Esperando LIVES...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
        <script>
            setInterval(function() {
                fetch('/get_logs').then(r => r.json()).then(d => {
                    document.querySelector('.stats').children[0].querySelector('.stat-number').textContent = d.approved;
                    document.querySelector('.stats').children[1].querySelector('.stat-number').textContent = d.declined;
                    document.getElementById('logs').textContent = d.log;
                });
                fetch('/get_lives').then(r => r.json()).then(d => {
                    let tbody = document.getElementById('lives-body');
                    if(d.lives.length > 0) {
                        tbody.innerHTML = d.lives.map(l => `<tr><td>${l.cc}</td><td>${l.status}</td><td>${l.country}</td><td>${l.bank}</td><td>${l.type}</td><td>${l.timestamp}</td></tr>`).join('');
                    }
                });
            }, 2000);
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

# ==================== INICIO ====================
if __name__ == '__main__':
    # Cargar LIVES guardadas
    load_lives_from_file()
    
    # Iniciar Telethon
    telethon_thread = threading.Thread(target=telethon_thread_fn, daemon=True)
    telethon_thread.start()
    time.sleep(2)
    
    # Iniciar Flask
    app.run('0.0.0.0', PORT, debug=False)