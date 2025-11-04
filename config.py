"""
CONFIGURACIÓN
"""
import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.environ.get('API_ID', '22154650'))
API_HASH = os.environ.get('API_HASH', '2b554e270efb419af271c47ffe1d72d3')
SESSION_NAME = os.environ.get('SESSION_NAME', 'session_secure')
BOT_USERNAME = os.environ.get('BOT_USERNAME', '@Alphachekerbot')

CHANNEL_ID_ENV = os.environ.get('CHANNEL_ID', '-1003101739772')
try:
    CHANNEL_ID = int(CHANNEL_ID_ENV)
except ValueError:
    CHANNEL_ID = CHANNEL_ID_ENV

PORT = int(os.environ.get('PORT', '5000'))
SECRET_KEY = os.environ.get('SECRET_KEY', 'change_me_in_production')
FLASK_ENV = os.environ.get('FLASK_ENV', 'development')

PASSWORD_MIN_LENGTH = 8
MAX_LOGIN_ATTEMPTS = 5
LOGIN_ATTEMPT_TIMEOUT = 15 * 60
SESSION_TIMEOUT = 24 * 60 * 60

DATABASE_FILE = 'users.db'
LIVES_FILE = 'lives_database.json'

CC_BATCH_SIZE = 20
CC_SEND_INTERVAL = 21
MAX_LIVES_STORED = 100

DEFAULT_ADMIN_USER = 'admin'
DEFAULT_ADMIN_PASSWORD = 'ChangeMe123!@#'
