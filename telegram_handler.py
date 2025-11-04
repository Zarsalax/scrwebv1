"""
MANEJADOR TELEGRAM
"""
from telethon import events
from telethon.errors import FloodWaitError, RPCError
from database import lives_mgr, logger
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
            logger.add(f"✅ APPROVED - Total: {approved_count}")
        elif "❌" in full_message or "declined" in message_lower:
            declined_count += 1
            logger.add(f"❌ DECLINED - Total: {declined_count}")

    logger.add("✅ Event handlers configurados")

def get_statistics():
    return {
        'approved': approved_count,
        'declined': declined_count,
        'total': approved_count + declined_count
    }
