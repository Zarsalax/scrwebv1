"""
MANEJADOR DE EVENTOS TELEGRAM
"""

from telethon import events
from telethon.errors import FloodWaitError, RPCError
from database import lives_mgr
from utils import logger
from config import CHANNEL_ID

approved_count = 0
declined_count = 0

async def setup_event_handlers(client, channel_id):
    @client.on(events.MessageEdited(chats='@Alphachekerbot'))
    async def response_handler(event):
        global approved_count, declined_count

        full_message = event.message.message if event.message.message else ""
        message_lower = full_message.lower()

        if "✅" in full_message or "approved" in message_lower:
            approved_count += 1
            logger.add(f"✅ APPROVED - Contador: {approved_count}")

            lines = full_message.split('\n')
            cc_number = status = response = country = bank = card_type = gate = ""

            for line in lines:
                if 'cc:' in line.lower():
                    cc_number = line.split(':', 1)[1].strip() if ':' in line else ""
                elif 'status:' in line.lower():
                    status = line.split(':', 1)[1].strip() if ':' in line else ""
                elif 'country:' in line.lower():
                    country = line.split(':', 1)[1].strip() if ':' in line else ""
                elif 'bank:' in line.lower():
                    bank = line.split(':', 1)[1].strip() if ':' in line else ""

            if cc_number:
                logger.add(f"💳 LIVE ENCONTRADA: {cc_number[:12]}...")
                lives_mgr.add_live(cc_number, status, response, country, bank, card_type, gate)

        elif "❌" in full_message or "declined" in message_lower:
            declined_count += 1
            logger.add(f"❌ DECLINED - Contador: {declined_count}")

    logger.add(f"✅ Event handlers configurados")

def get_statistics():
    return {
        'approved': approved_count,
        'declined': declined_count,
        'total': approved_count + declined_count
    }
