
# Telegram Message Copier Bot

A fully interactive Telegram bot for copying messages between channels with button-based controls, progress tracking, and media support.

## Features

✅ **Button-Based Interface** - No commands needed, everything is done through interactive buttons
✅ **Session Management** - Load existing sessions, create new ones, or manually input session strings
✅ **Channel Validation** - Automatic verification of source and target channels
✅ **Media Support** - Copy photos, videos, documents, and other media types
✅ **Progress Tracking** - Real-time progress updates with speed monitoring
✅ **Error Handling** - Automatic retry logic and flood protection
✅ **Admin Control** - Restrict access to authorized users only
✅ **Session Persistence** - Save and load authentication sessions

## Setup Instructions

### 1. Get Telegram API Credentials

1. Go to https://my.telegram.org/apps
2. Log in with your phone number
3. Create a new application
4. Note down your `API_ID` and `API_HASH`

### 2. Create a Bot

1. Message @BotFather on Telegram
2. Use `/newbot` command
3. Follow the instructions to create your bot
4. Note down the bot token

### 3. Get Your User ID

1. Message @userinfobot on Telegram
2. Note down your user ID

### 4. Configure the Bot

1. Open `telegram_copier_bot.py`
2. Replace the following values at the top of the file:
   ```python
   API_ID = "YOUR_API_ID"  # Your API ID from step 1
   API_HASH = "YOUR_API_HASH"  # Your API hash from step 1
   BOT_TOKEN = "YOUR_BOT_TOKEN"  # Your bot token from step 2
   ADMIN_USER_IDS = [123456789]  # Your user ID from step 3
   ```

### 5. Install Dependencies

```bash
pip install -r requirements.txt
```

### 6. Run the Bot

```bash
python telegram_copier_bot.py
```

## How to Use

### 1. Start the Bot
- Send `/start` to your bot
- Choose from session options:
  - 🔑 **Load Saved Session** - Use previously saved session
  - 🆕 **Create New Session** - Authenticate with phone number
  - ✍️ **Enter Session String** - Manually input session string

### 2. Configure Channels
- 📥 **Set Source Channel** - Channel to copy messages from
- 📤 **Set Target Channel** - Channel to copy messages to
- 🔢 **Set Message Range** - Specify start and end message IDs

### 3. Start Copying
- Review your settings
- Click 🚀 **Start Copying**
- Monitor real-time progress
- View final results and statistics

## Bot Interface Flow

```
Start Bot
├── 🔑 Load Session
├── 🆕 New Session (Phone → Code → Password if 2FA)
├── ✍️ Manual Session
└── ℹ️ Help

After Login:
Control Panel
├── 📥 Set Source Channel
├── 📤 Set Target Channel  
├── 🔢 Set Message Range
└── 🚀 Start Copying (when all configured)

During Copy:
Progress Display
├── Real-time statistics
├── Success/failure counts
├── Speed monitoring
└── Current message ID

After Completion:
Results & Options
├── 🔁 Copy Again
├── 🎛️ Control Panel
└── 🔚 Exit
```

## Security Features

- **Admin-only access** - Only specified user IDs can use the bot
- **Session encryption** - Pyrogram handles session security
- **Input validation** - All user inputs are validated
- **Error handling** - Graceful error recovery

## Technical Details

- **Framework**: Pyrogram (async)
- **Interface**: Telegram inline keyboards
- **Storage**: JSON file for session persistence
- **Error Handling**: FloodWait protection, automatic retries
- **Progress**: Real-time updates every 10 messages
- **Media Support**: All Telegram media types

## Troubleshooting

### Common Issues

1. **"Access denied" error**
   - Make sure your user ID is in `ADMIN_USER_IDS`

2. **"Invalid session" error**  
   - Delete `session.json` and create a new session

3. **"Cannot access channel" error**
   - Make sure you have admin rights in both channels
   - Check channel username/ID format

4. **FloodWait errors**
   - The bot handles these automatically with delays
   - Reduce copying speed if persistent

### Getting Help

1. Check the logs for detailed error messages
2. Ensure all credentials are correctly configured
3. Verify channel permissions and access rights
4. Test with a small message range first

## License

This project is for educational purposes. Make sure to comply with Telegram's Terms of Service when using this bot.

## Disclaimer

- Use responsibly and respect channel owners' rights
- Don't spam or abuse the copying functionality  
- The bot is designed for legitimate use cases only
- Always obtain permission before copying from channels you don't own
