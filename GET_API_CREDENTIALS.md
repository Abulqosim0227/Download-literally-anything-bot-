# 🔑 How to Get API Credentials for 2GB Upload Support

To enable **2GB file uploads**, you need Telegram API credentials (`API_ID` and `API_HASH`). Follow this simple guide!

## 📋 Prerequisites

- A Telegram account
- Phone number
- 5 minutes of your time

## 🚀 Step-by-Step Guide

### Step 1: Go to Telegram's Website

Visit: **https://my.telegram.org**

### Step 2: Sign In

1. Enter your **phone number** (with country code)
   - Example: `+1234567890`
2. Click "Next"
3. You'll receive a **verification code** on Telegram
4. Enter the code

### Step 3: Create an Application

1. Click on "**API development tools**"
2. Fill in the form:
   - **App title**: `My Media Bot` (or any name)
   - **Short name**: `mediabot` (or any short name)
   - **URL**: Leave empty or put your website
   - **Platform**: Select "**Other**"
   - **Description**: `Media downloader bot` (optional)

3. Click "**Create application**"

### Step 4: Copy Your Credentials

You'll see a page with your credentials:

```
App api_id: 12345678
App api_hash: 0a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p
```

**Important:**
- ✅ Copy both `API_ID` and `API_HASH`
- ⚠️ Keep them private (like a password)
- 🔐 Never share them publicly

### Step 5: Add to Your Config

Open `config.py` and add your credentials:

```python
# Large File Support (2GB uploads via Client API)
ENABLE_LARGE_FILES = True  # Change to True

# Add your credentials here
API_ID = 12345678  # Your api_id (number, no quotes)
API_HASH = "0a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p"  # Your api_hash (in quotes)
```

### Step 6: Install Pyrogram

```bash
pip install pyrogram tgcrypto
```

### Step 7: Restart Your Bot

```bash
python bot.py
```

Look for this message:
```
✅ Large file support ENABLED - 2GB uploads available!
```

## ✅ Done!

Your bot can now handle files up to **2GB**!

## 🎯 How It Works

**Automatic Smart Upload:**

| File Size | Method Used | Speed |
|-----------|-------------|-------|
| < 50 MB | Bot API (default) | ⚡ Fast |
| 50 MB - 2 GB | Client API (Pyrogram) | 🚀 Fast |

The bot automatically chooses the best method for each file!

## 🔒 Security Notes

**Your API credentials are safe because:**
- ✅ `config.py` is in `.gitignore` (never uploaded to GitHub)
- ✅ Only stored on your server
- ✅ Used only for your bot
- ✅ Can be regenerated anytime

**To regenerate credentials:**
1. Go to https://my.telegram.org/apps
2. Delete old app
3. Create new app
4. Get new credentials

## ❓ FAQ

### Q: Are these credentials free?
**A:** Yes! Completely free from Telegram.

### Q: Is there a limit on file uploads?
**A:** 2GB per file. No daily limit.

### Q: Can I use the same credentials for multiple bots?
**A:** Yes, but it's better to create separate apps for each bot.

### Q: What if I lose my credentials?
**A:** Just create a new app at https://my.telegram.org/apps

### Q: Do I need to verify again?
**A:** No, once created, credentials work forever (until you delete the app).

### Q: Will my bot work without these credentials?
**A:** Yes! Bot works perfectly with 50MB limit. These credentials only enable the 2GB feature.

## 🐛 Troubleshooting

### "Pyrogram not installed" error

```bash
pip install pyrogram tgcrypto
```

### "API_ID or API_HASH not configured" warning

Double-check in `config.py`:
- `API_ID` should be a number (no quotes)
- `API_HASH` should be in quotes
- `ENABLE_LARGE_FILES = True`

### "Failed to initialize" error

1. Check credentials are correct
2. Make sure bot token is valid
3. Check internet connection
4. Try regenerating credentials

### Bot starts but says "using 50MB limit"

Check these in `config.py`:
```python
ENABLE_LARGE_FILES = True  # Must be True
API_ID = 12345678  # Must be your actual ID
API_HASH = "your_hash_here"  # Must be your actual hash
```

## 📚 Additional Resources

- **Telegram API Docs**: https://core.telegram.org/api
- **Pyrogram Docs**: https://docs.pyrogram.org/
- **My Telegram**: https://my.telegram.org

## 🎉 Enjoy 2GB Uploads!

Now your bot can handle large files just like **Godzilla bot** and other premium bots!

---

**Need help?** Open an issue on GitHub or contact the admin.
