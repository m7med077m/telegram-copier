
"""
Configuration file for Telegram Copier Bot

Instructions:
1. Get your API credentials from https://my.telegram.org/apps
2. Create a bot with @BotFather and get the bot token
3. Get your Telegram user ID (you can use @userinfobot)
4. Fill in the values below
"""

# Telegram API Credentials
# Get these from https://my.telegram.org/apps
# 1. Log in with your Telegram account
# 2. Create a new application or use an existing one
# 3. Copy the api_id and api_hash values below
API_ID = 28129546  # Replace with your API ID (integer)
API_HASH = "f0985e4f023d1406fe8ee76717651e85"  # Replace with your API Hash (string)
BOT_TOKEN = "7704671917:AAFlZdAChPWPlb6yazFMHTRFEXTWSVsTfKc"  # Your Bot Token

# Bot Owner ID
OWNER_ID = 933493534  # Your Telegram ID

# Admin User IDs (list of admin user IDs)
ADMIN_USER_IDS = [OWNER_ID]  # Add more admin IDs if needed

# Database Settings
DATABASE_URL = "sqlite:///bot.db"  # SQLite database URL

# Message Limits
DEFAULT_MESSAGE_LIMIT = 20  # Default message limit for free users
VIP_MESSAGE_LIMIT = float('inf')  # Unlimited messages for VIP users

# Speed Limits (delays in seconds between messages)
FREE_USER_DELAY = 0.5  # Delay for free users (limits speed)
VIP_USER_DELAY = 0.1   # Minimal delay for VIP users (maximum speed)
OWNER_DELAY = 0.05     # Minimal delay for owner (maximum speed)

# Session Settings
SESSION_NAME = "copier_bot"  # Session name for Pyrogram
SESSION_STRING = None  # Session string for user account (if needed)

# Logging Settings
LOG_LEVEL = "INFO"  # Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"  # Log format

# VIP Features
VIP_FEATURES = {
    'unlimited_messages': True,
    'maximum_speed': True,
    'priority_processing': True,
    'advanced_channels': True,
    'premium_support': True
}

# Payment Settings
VIP_PRICE_EGP = 200  # VIP price in EGP
VIP_PRICE_USD = 5  # VIP price in USD

# Payment Methods
PAYMENT_METHODS = {
    'binance_id': '789564679',
    'usdt_trc20': 'TE1S4PeEws1xq5QaehdrZFW4fPZYZbYiUu',
    'vodafone_cash': '01015339426',
    'instapay': 'aboelkhier1573@instapay'
}

# Support Contact
SUPPORT_USERNAME = '@M7MED1573'  # Support username for payment verification

# Session file name
SESSION_FILE = "session.json"

# Copy settings
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds
PROGRESS_UPDATE_INTERVAL = 10  # update progress every N messages 
