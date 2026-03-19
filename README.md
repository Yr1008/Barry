# ⚡ Barry — Your Personal AI Assistant

Barry is a Jarvis-like AI assistant powered by Claude Opus 4.6. It monitors your calendar, emails, WhatsApp, iPhone, and more — keeping you updated, prioritizing your day, and helping you take action.

## What Barry Does

| Feature | Description |
|---------|-------------|
| 🧠 **Smart Brain** | Claude Opus 4.6 with adaptive thinking — reasons deeply about your day |
| 📅 **Calendar** | Google Calendar + Apple iCloud — sees all your events |
| 📧 **Email** | Gmail/IMAP — monitors inbox, drafts replies in your tone |
| 💬 **WhatsApp** | Receives messages, sends replies via Twilio |
| 📱 **iPhone/Mac** | Apple Shortcuts integration — reminders, notes, battery, focus mode |
| 🎯 **Tone Learning** | Remembers how you write to each person and matches it |
| 📋 **Smart Todos** | AI-prioritized task list based on deadlines and context |
| 🔄 **Auto-Polling** | Checks everything every 5 minutes automatically |
| 💾 **Memory** | Remembers your preferences, facts, and communication styles |
| 🌐 **Web Dashboard** | Clean UI at `http://localhost:8000` |
| 🔔 **Notifications** | Push via WhatsApp or Pushover when something urgent arrives |

## Quick Start

```bash
# 1. Clone and install
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env — at minimum, add ANTHROPIC_API_KEY and BARRY_OWNER_NAME

# 3. Start Barry
python main.py          # Web server + auto-polling
# or
python main.py chat     # Interactive CLI
```

## Commands

```
python main.py              # Start web server (default)
python main.py chat         # Interactive CLI chat
python main.py briefing     # Generate morning briefing
python main.py todos        # Show prioritized todos
python main.py poll         # Poll all sources now
python main.py status       # System status
python main.py iphone-setup # Show Apple Shortcuts setup guide
```

## Configuration

Edit `.env`:

```env
ANTHROPIC_API_KEY=sk-ant-...        # Required
BARRY_OWNER_NAME=Alex               # Your name
BARRY_TIMEZONE=America/New_York     # Your timezone
BARRY_BRIEFING_TIME=07:30           # When to send morning briefing
BARRY_POLL_INTERVAL_MINUTES=5       # How often to check for updates
```

## Connecting Your Services

### Google Calendar + Gmail
1. Create OAuth credentials at [Google Cloud Console](https://console.cloud.google.com)
2. Add `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` to `.env`
3. Start Barry and visit `http://localhost:8000/auth/google`

### Apple iCloud Calendar + Reminders
1. Generate an App-Specific Password at [appleid.apple.com](https://appleid.apple.com)
2. Add to `.env`:
   ```
   ICLOUD_EMAIL=you@icloud.com
   ICLOUD_PASSWORD=xxxx-xxxx-xxxx-xxxx
   ```

### WhatsApp (via Twilio)
1. Sign up at [twilio.com](https://www.twilio.com)
2. Enable WhatsApp Sandbox
3. Add credentials to `.env`
4. Set webhook URL to: `http://YOUR_SERVER/whatsapp/webhook`

### iPhone / Mac (Apple Shortcuts)
```bash
python main.py iphone-setup
```
This shows step-by-step instructions to set up Apple Shortcuts that push your reminders, notes, battery status, and focus mode to Barry automatically. You can also **ask Barry questions via Siri**.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/chat` | Chat with Barry |
| GET | `/status` | System status |
| GET | `/briefing` | Generate briefing |
| GET | `/todos` | Prioritized todo list |
| POST | `/todos` | Add a todo |
| PUT | `/todos/{id}/complete` | Complete a todo |
| GET | `/preferences` | Your stored preferences |
| GET | `/facts` | Facts Barry has learned |
| GET | `/tone-profiles` | Communication tone profiles |
| POST | `/iphone/shortcut` | Apple Shortcuts webhook |
| POST | `/whatsapp/webhook` | Twilio WhatsApp webhook |
| GET | `/auth/google` | Start Google OAuth |
| GET | `/` | Web dashboard |

## Architecture

```
Barry/
├── main.py              # Entry point & CLI
├── barry.py             # Core brain — orchestrates everything
├── config.py            # Configuration (reads .env)
│
├── memory/
│   ├── store.py         # SQLite memory — preferences, todos, facts, tone
│   └── tone.py          # Tone analysis & reply generation
│
├── connectors/
│   ├── calendar_conn.py # Google Calendar + Apple iCloud
│   ├── email_conn.py    # Gmail / IMAP
│   ├── whatsapp_conn.py # WhatsApp via Twilio
│   └── iphone_mac.py   # Apple Shortcuts webhook receiver
│
├── intelligence/
│   ├── briefing.py      # Daily briefing generator
│   ├── priorities.py    # AI-powered todo prioritization
│   └── actions.py       # Action executor (send email, add todo, etc.)
│
├── scheduler/
│   └── poller.py        # Background auto-polling (APScheduler)
│
├── api/
│   └── server.py        # FastAPI server + web dashboard
│
└── iphone/
    └── shortcuts_templates.json  # Apple Shortcuts templates
```

## How Barry Thinks

Barry uses **Claude Opus 4.6 with adaptive thinking** — it reasons through your situation before responding. When you ask "what should I focus on today?", Barry:

1. Looks at your calendar events for conflicts or prep needed
2. Scans unread emails for urgency signals
3. Checks todos for deadlines
4. Considers your past preferences
5. Generates a prioritized, contextual answer

## Memory & Learning

Barry continuously learns:
- **Preferences**: "I prefer meetings after 10am" → stored and used in recommendations
- **Tone profiles**: Analyzes how you write to different people, uses it when drafting replies
- **Facts**: "I'm a morning person", "My biggest client is X" → provides context in all responses
- **Conversation history**: Remembers past sessions to maintain continuity

## iPhone Integration (Apple Shortcuts)

Barry can receive data from your iPhone and Mac via Apple Shortcuts automations:

- **Reminders** → automatically added to Barry's todo list
- **Notes** → Barry can summarize or act on them
- **Battery & Focus mode** → mentioned in briefings
- **Siri questions** → "Hey Siri, Tell Barry to add a meeting tomorrow at 2pm"

Visit `http://localhost:8000/iphone/setup` for the full setup guide.

## Privacy

- All data is stored locally in `./data/barry.db` (SQLite)
- No data is sent anywhere except to Anthropic's API (for Claude) and your configured services
- WhatsApp messages go through Twilio
- You control everything
