
# 🚀 Advanced Telegram Scraper with Anti-Ban Protection

A powerful and safe Telegram automation tool for scraping channel members and adding them to groups with comprehensive anti-ban protection.

## ⚡ Features

### 🔍 Scraping Capabilities
- Scrape members from public channels/groups
- Extract usernames, IDs, names, and phone numbers
- Smart batch processing to avoid rate limits
- Export data in JSON format

### 👥 Adding Features
- Add members to your groups safely
- Multiple adding methods (username, ID)
- Intelligent retry mechanisms
- Real-time success/failure tracking

### 🛡️ Anti-Ban Protection
- **Rate Limiting**: Configurable daily/hourly/session limits
- **Random Delays**: 30-120 second delays between actions
- **Flood Protection**: Automatic handling of Telegram flood waits
- **Error Recovery**: Comprehensive error handling and logging
- **Session Management**: Safe session handling and cleanup

## 🔧 Installation & Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Get API Credentials
1. Go to https://my.telegram.org
2. Log in with your phone number
3. Go to "API development tools"
4. Create a new application
5. Copy your `api_id` and `api_hash`

### 3. Configure Credentials
```bash
python setup.py
```

### 4. Run the Tool
```bash
python telegram_scraper.py
```

## 📖 Usage Guide

### 🔍 Scraping Members
1. Choose option `1` from the menu
2. Enter the channel username (e.g., `@channelname`)
3. Wait for the scraping to complete
4. Data will be saved automatically

### 👥 Adding Members
1. First scrape members or load existing data
2. Choose option `4` for bulk adding
3. Enter your target group username
4. The tool will add members safely with delays

### ⚙️ Safety Settings
The tool includes multiple safety mechanisms:

- **Daily Limit**: 50 adds per day (configurable)
- **Hourly Limit**: 10 adds per hour (configurable)
- **Session Limit**: 5 adds per session (configurable)
- **Delays**: 30-120 seconds between actions
- **Flood Protection**: Automatic retry with exponential backoff

## 🛡️ Anti-Ban Features

### Rate Limiting
```python
daily_limit = 50      # Max adds per day
hourly_limit = 10     # Max adds per hour
session_limit = 5     # Max adds per session
```

### Smart Delays
```python
min_delay = 30        # Minimum delay (seconds)
max_delay = 120       # Maximum delay (seconds)
```

### Error Handling
- `FloodWaitError`: Automatic retry after specified time
- `UserPrivacyRestrictedError`: Skip user and continue
- `PeerFloodError`: Stop operation for safety
- `UserAlreadyParticipantError`: Skip user (already added)

## 📊 What This Tool Can Do

### ✅ Scraping Features
- ✅ Scrape public channels
- ✅ Scrape public groups
- ✅ Scrape supergroups
- ✅ Extract user data (username, ID, name, phone)
- ✅ Handle large channels (1M+ members)
- ✅ Export data in multiple formats

### ✅ Adding Features
- ✅ Add members to your groups
- ✅ Add by username
- ✅ Add by user ID
- ✅ Add from contact list
- ✅ Bulk adding with protection
- ✅ Real-time statistics

### ✅ Protection Features
- ✅ Anti-ban algorithms
- ✅ Rate limiting
- ✅ Random delays
- ✅ Flood protection
- ✅ Error recovery
- ✅ Session management
- ✅ Logging and monitoring

## ⚠️ Important Notes

### 🔐 Account Safety
- Use only with your own account
- Start with low limits
- Take regular breaks
- Monitor your account for any restrictions

### 📜 Legal Compliance
- Only scrape public data
- Respect user privacy
- Follow Telegram's Terms of Service
- Don't spam or harass users

### 🚨 Risk Mitigation
- **Phone Number Protection**: The tool includes delays and limits to protect your account
- **Session Management**: Proper session handling to avoid conflicts
- **Error Recovery**: Comprehensive error handling to prevent crashes
- **Logging**: Detailed logs for monitoring and debugging

## 🔧 Configuration

### Basic Settings (telegram_scraper.py)
```python
# Replace these with your values
self.api_id = "YOUR_API_ID"
self.api_hash = "YOUR_API_HASH"
self.phone = "YOUR_PHONE_NUMBER"
```

### Anti-Ban Settings
```python
self.min_delay = 30      # Minimum delay between actions
self.max_delay = 120     # Maximum delay between actions
self.daily_limit = 50    # Max adds per day
self.hourly_limit = 10   # Max adds per hour
self.session_limit = 5   # Max adds per session
```

## 🚀 Quick Start

1. **Setup**: Run `python setup.py` and enter your credentials
2. **Scrape**: Choose option 1, enter a channel like `@telegram`
3. **Add**: Choose option 4, enter your group username
4. **Monitor**: Check logs and statistics regularly

## 📝 Logging

The tool creates detailed logs in `telegram_bot.log`:
- All actions performed
- Success/failure rates
- Error messages
- Timing information

## 🔄 Updates & Maintenance

The tool automatically handles:
- Session renewals
- Token refreshes
- Error recovery
- Rate limit resets

---

**⚠️ Disclaimer**: Use this tool responsibly and in compliance with Telegram's Terms of Service. The authors are not responsible for any account restrictions or bans that may result from misuse.
