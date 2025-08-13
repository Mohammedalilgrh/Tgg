
# Configuration file for Telegram Scraper
# Replace these values with your own

# Get these from https://my.telegram.org
API_ID = "YOUR_API_ID"
API_HASH = "YOUR_API_HASH"

# Your phone number with country code (e.g., +1234567890)
PHONE_NUMBER = "YOUR_PHONE_NUMBER"

# Anti-ban protection settings
ANTI_BAN_CONFIG = {
    "min_delay": 30,        # Minimum seconds between actions
    "max_delay": 120,       # Maximum seconds between actions
    "daily_limit": 50,      # Max adds per day
    "hourly_limit": 10,     # Max adds per hour
    "session_limit": 5,     # Max adds per session
    "batch_size": 100,      # Members to scrape at once
    "retry_delay": 300,     # Delay after getting rate limited (5 mins)
}

# Logging configuration
LOG_CONFIG = {
    "level": "INFO",
    "file": "telegram_bot.log",
    "format": "%(asctime)s - %(levelname)s - %(message)s"
}
