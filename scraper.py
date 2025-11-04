"""
SCRAPER
"""
import asyncio
import os
from telethon.errors import FloodWaitError, RPCError
from config import CC_BATCH_SIZE, CC_SEND_INTERVAL, BOT_USERNAME
from database import logger
from utils import CCGenerator

sent_count = 0
total_batches = 0

async def load_commands():
    try:
        if os.path.exists('cmds.txt'):
            with open('cmds.txt', 'r', encoding='utf-8') as f:
                cmds = [line.strip() for line in f.readlines() if line.strip()]
                if cmds:
                    return cmds
        return ['/check', '/validate', '/test']
    except Exception as e:
        logger.add(f"❌ Error cargando comandos: {e}")
        return ['/check']

async def load_ccs():
    try:
        if os.path.exists('ccs.txt'):
            with open('ccs.txt', 'r', encoding='utf-8') as f:
                ccs_list = [line.strip() for line in f.readlines() if line.strip()]
                return ccs_list
        return []
    except Exception as e:
        logger.add(f"❌ Error cargando CCs: {e}")
        return []

def save_ccs(ccs_list):
    try:
        with open('ccs.txt', 'w', encoding='utf-8') as f:
            f.write('\n'.join(ccs_list) + '\n' if ccs_list else '')
    except Exception as e:
        logger.add(f"❌ Error guardando CCs: {e}")

async def send_cc_variants_to_bot(client, cc_variants, commands):
    global sent_count, total_batches

    try:
        for i in range(0, len(cc_variants), 2):
            pair = cc_variants[i:i+2]
            tasks = []

            for j, cc in enumerate(pair):
                async def send_single_cc(card, idx):
                    global sent_count
                    try:
                        import random
                        command = random.choice(commands)
                        message = f"{command} {card}"
                        await client.send_message(BOT_USERNAME, message)
                        sent_count += 1
                        num = i + idx + 1
                        logger.add(f"✓ Enviado #{num}/{CC_BATCH_SIZE}")
                    except FloodWaitError as e:
                        logger.add(f"⏸️ Esperando {e.seconds}s")
                        await asyncio.sleep(e.seconds)
                    except RPCError as e:
                        logger.add(f"❌ Error: {e}")

                tasks.append(send_single_cc(cc, j))

            await asyncio.gather(*tasks)

            if i + 2 < len(cc_variants):
                await asyncio.sleep(CC_SEND_INTERVAL)

        total_batches += 1
        logger.add(f"🎉 Lote #{total_batches} completo")

    except Exception as e:
        logger.add(f"❌ Error enviando: {e}")

async def scraper_loop(client):
    logger.add("🚀 Scraper iniciado")

    while True:
        try:
            ccs_list = await load_ccs()

            if not ccs_list:
                logger.add("⏳ Esperando CCs...")
                await asyncio.sleep(30)
                continue

            current_cc = ccs_list[0]
            logger.add(f"🔄 Procesando: {current_cc[:12]}...")

            cc_variants, error = CCGenerator.generate_variants(current_cc, count=CC_BATCH_SIZE)

            if error:
                logger.add(f"❌ Error: {error}")
                ccs_list.pop(0)
                save_ccs(ccs_list)
                await asyncio.sleep(20)
                continue

            commands = await load_commands()
            await send_cc_variants_to_bot(client, cc_variants, commands)

            ccs_list.pop(0)
            save_ccs(ccs_list)

            await asyncio.sleep(CC_SEND_INTERVAL)

        except Exception as e:
            logger.add(f"❌ Error scraper: {e}")
            await asyncio.sleep(20)

def get_scraper_stats():
    return {'sent_count': sent_count, 'batches': total_batches}
