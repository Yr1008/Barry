"""
Barry FastAPI Server.

Endpoints:
- POST /chat              — chat with Barry
- GET  /status            — system status
- GET  /briefing          — get daily briefing
- GET  /todos             — get prioritized todos
- POST /todos             — add a todo
- POST /iphone/shortcut   — receive Apple Shortcuts data
- POST /whatsapp/webhook  — receive Twilio WhatsApp webhook
- GET  /auth/google       — start Google OAuth
- GET  /auth/google/callback — Google OAuth callback
- GET  /dashboard         — web dashboard (HTML)
"""
from __future__ import annotations

import asyncio
import hmac
import hashlib
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel

logger = logging.getLogger("barry.api")


# ─── Request / Response Models ────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    stream: bool = True
    session_id: str | None = None


class TodoRequest(BaseModel):
    title: str
    description: str = ""
    priority: int = 3
    due_date: str | None = None
    tags: list[str] = []


class PreferenceRequest(BaseModel):
    key: str
    value: Any


# ─── App Factory ──────────────────────────────────────────────────────────────

def create_app(barry_instance=None) -> FastAPI:
    """Create the FastAPI application."""

    # Import here to avoid circular imports
    from barry import Barry
    from scheduler.poller import BarryScheduler

    barry: Barry = barry_instance or Barry()
    scheduler = BarryScheduler(barry)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Start scheduler on boot
        scheduler.start()

        # Run initial poll
        try:
            await barry.poll_all()
        except Exception as e:
            logger.warning(f"Initial poll failed: {e}")

        yield

        scheduler.stop()

    app = FastAPI(
        title="Barry — AI Assistant",
        description="Your personal Jarvis-like AI assistant",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ─── Chat ─────────────────────────────────────────────────────────────────

    @app.post("/chat")
    async def chat(request: ChatRequest):
        """Chat with Barry."""
        if request.session_id:
            barry._session_id = request.session_id

        if request.stream:
            async def generate():
                async for chunk in await barry.chat(request.message, stream=True):
                    yield f"data: {chunk}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(generate(), media_type="text/event-stream")
        else:
            response = await barry.chat(request.message, stream=False)
            return {"response": response, "session_id": barry._session_id}

    # ─── Status ───────────────────────────────────────────────────────────────

    @app.get("/status")
    async def get_status():
        """Get Barry's current status."""
        return barry.get_status()

    # ─── Briefing ─────────────────────────────────────────────────────────────

    @app.get("/briefing")
    async def get_briefing():
        """Get the daily briefing."""
        briefing = await barry.generate_daily_briefing()
        return {"briefing": briefing, "generated_at": datetime.now().isoformat()}

    # ─── Todos ────────────────────────────────────────────────────────────────

    @app.get("/todos")
    async def get_todos(prioritized: bool = True):
        """Get todo list, optionally prioritized."""
        if prioritized:
            formatted = await barry.get_prioritized_todos()
            return {"todos": barry.memory.get_todos(), "formatted": formatted}
        return {"todos": barry.memory.get_todos()}

    @app.post("/todos")
    async def add_todo(todo: TodoRequest):
        """Add a new todo."""
        result = await barry.actions.add_todo(
            title=todo.title,
            description=todo.description,
            priority=todo.priority,
            due_date=todo.due_date,
            tags=todo.tags,
        )
        return result

    @app.put("/todos/{todo_id}/complete")
    async def complete_todo(todo_id: int):
        """Mark a todo as complete."""
        result = await barry.actions.complete_todo(todo_id)
        return result

    # ─── Memory / Preferences ─────────────────────────────────────────────────

    @app.get("/preferences")
    async def get_preferences():
        """Get all stored preferences."""
        return barry.memory.get_all_preferences()

    @app.post("/preferences")
    async def set_preference(pref: PreferenceRequest):
        """Set a preference."""
        barry.memory.set_preference(pref.key, pref.value)
        return {"success": True, "key": pref.key}

    @app.get("/facts")
    async def get_facts(category: str | None = None):
        """Get stored facts."""
        return barry.memory.get_facts(category)

    @app.get("/tone-profiles")
    async def get_tone_profiles():
        """Get all learned tone profiles."""
        return barry.memory.get_all_tone_profiles()

    # ─── iPhone / Apple Shortcuts Webhook ─────────────────────────────────────

    @app.post("/iphone/shortcut")
    async def receive_shortcut(request: Request, background_tasks: BackgroundTasks):
        """Receive data from Apple Shortcuts on iPhone/Mac."""
        # Verify secret
        secret = request.headers.get("X-Barry-Secret", "")
        if barry.config.shortcuts_webhook_secret and secret != barry.config.shortcuts_webhook_secret:
            raise HTTPException(status_code=403, detail="Invalid secret")

        try:
            payload = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON")

        barry.iphone.receive_shortcut_data(payload)

        # Process in background
        background_tasks.add_task(_process_shortcut_data, barry, payload)

        return {"status": "received", "type": payload.get("type")}

    # ─── WhatsApp Webhook (Twilio) ─────────────────────────────────────────────

    @app.post("/whatsapp/webhook")
    async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
        """Receive WhatsApp messages from Twilio."""
        form_data = await request.form()

        from_number = form_data.get("From", "")
        body = form_data.get("Body", "")
        timestamp = datetime.now().isoformat()

        if from_number and body:
            barry.whatsapp.receive_message(from_number, body, timestamp)
            background_tasks.add_task(_process_whatsapp_message, barry, from_number, body)

        # Twilio expects TwiML response
        return HTMLResponse(
            content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
            media_type="application/xml",
        )

    # ─── Google OAuth ──────────────────────────────────────────────────────────

    @app.get("/auth/google")
    async def google_auth():
        """Start Google OAuth flow."""
        if not barry.config.has_google:
            raise HTTPException(status_code=400, detail="Google not configured")
        try:
            from google_auth_oauthlib.flow import Flow
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": barry.config.google_client_id,
                        "client_secret": barry.config.google_client_secret,
                        "redirect_uris": [barry.config.google_redirect_uri],
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                    }
                },
                scopes=["https://www.googleapis.com/auth/calendar.readonly"],
            )
            flow.redirect_uri = barry.config.google_redirect_uri
            auth_url, _ = flow.authorization_url(prompt="consent")
            return {"auth_url": auth_url}
        except ImportError:
            raise HTTPException(status_code=500, detail="google-auth-oauthlib not installed")

    @app.get("/auth/google/callback")
    async def google_auth_callback(code: str, request: Request):
        """Handle Google OAuth callback."""
        if not barry.config.has_google:
            raise HTTPException(status_code=400, detail="Google not configured")
        try:
            from google_auth_oauthlib.flow import Flow
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": barry.config.google_client_id,
                        "client_secret": barry.config.google_client_secret,
                        "redirect_uris": [barry.config.google_redirect_uri],
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                    }
                },
                scopes=["https://www.googleapis.com/auth/calendar.readonly"],
            )
            flow.redirect_uri = barry.config.google_redirect_uri
            flow.fetch_token(code=code)
            creds = flow.credentials
            with open(barry.config.google_token_path, "w") as f:
                f.write(creds.to_json())
            return {"status": "Google Calendar connected!", "message": "You can close this tab."}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ─── Scheduler Controls ────────────────────────────────────────────────────

    @app.post("/scheduler/run/{job_id}")
    async def run_job(job_id: str, background_tasks: BackgroundTasks):
        """Manually trigger a scheduled job."""
        background_tasks.add_task(scheduler.run_now, job_id)
        return {"status": "triggered", "job": job_id}

    # ─── Web Dashboard ─────────────────────────────────────────────────────────

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        """Barry's web dashboard."""
        return HTMLResponse(content=DASHBOARD_HTML)

    # ─── iPhone Shortcuts Guide ────────────────────────────────────────────────

    @app.get("/iphone/setup")
    async def iphone_setup():
        """Get Apple Shortcuts setup guide."""
        return {"guide": barry.iphone.get_shortcuts_setup_guide()}

    # ─── History ──────────────────────────────────────────────────────────────

    @app.get("/history")
    async def get_history(limit: int = 20):
        """Get conversation history."""
        messages = barry.memory.get_recent_messages(limit)
        return {"messages": messages}

    @app.post("/reset")
    async def reset_conversation():
        """Reset the current conversation."""
        barry.reset_conversation()
        return {"status": "Conversation reset."}

    return app


# ─── Background Task Helpers ──────────────────────────────────────────────────

async def _process_shortcut_data(barry, payload: dict) -> None:
    """Process Apple Shortcuts data in background."""
    try:
        data_type = payload.get("type")
        if data_type == "question":
            # User asked Barry a question via Siri
            question = payload.get("text", "")
            if question:
                response = await barry.chat(question, stream=False)
                # Send response back via push notification
                await barry.actions.notify_self(response[:500], title=f"Barry: {question[:30]}")
    except Exception as e:
        logger.error(f"Shortcut processing failed: {e}")


async def _process_whatsapp_message(barry, from_number: str, body: str) -> None:
    """Process incoming WhatsApp message."""
    try:
        owner_number = barry.config.my_whatsapp_number.replace("whatsapp:", "")
        sender_clean = from_number.replace("whatsapp:", "")

        # If message is from the owner, it's a command to Barry
        if sender_clean == owner_number or owner_number in sender_clean:
            response = await barry.chat(body, stream=False)
            await barry.whatsapp.send_to_self(response[:1600])  # WhatsApp limit
        else:
            # Incoming from someone else — notify owner with context
            notification = f"📱 WhatsApp from {from_number}:\n{body}"
            await barry.actions.notify_self(notification, title="New WhatsApp")

    except Exception as e:
        logger.error(f"WhatsApp processing failed: {e}")


# ─── Dashboard HTML ───────────────────────────────────────────────────────────

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Barry — AI Assistant</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
               background: #0f0f0f; color: #e0e0e0; height: 100vh; display: flex; flex-direction: column; }
        header { background: #1a1a2e; padding: 16px 24px; display: flex; align-items: center; gap: 12px;
                 border-bottom: 1px solid #333; }
        header h1 { font-size: 1.4rem; color: #7c83fd; }
        header .status-dot { width: 10px; height: 10px; background: #4caf50; border-radius: 50%; }
        .main { display: flex; flex: 1; overflow: hidden; }
        .sidebar { width: 280px; background: #161616; padding: 16px; overflow-y: auto;
                   border-right: 1px solid #2a2a2a; }
        .sidebar h3 { font-size: 0.8rem; color: #888; text-transform: uppercase;
                      letter-spacing: 0.1em; margin: 16px 0 8px; }
        .sidebar h3:first-child { margin-top: 0; }
        .btn { display: block; width: 100%; padding: 8px 12px; margin-bottom: 6px;
               background: #2a2a3e; border: 1px solid #444; border-radius: 6px;
               color: #ccc; cursor: pointer; text-align: left; font-size: 0.85rem;
               transition: background 0.2s; }
        .btn:hover { background: #3a3a5e; }
        .btn.primary { background: #7c83fd22; border-color: #7c83fd66; color: #7c83fd; }
        .chat-area { flex: 1; display: flex; flex-direction: column; }
        .messages { flex: 1; overflow-y: auto; padding: 20px; }
        .msg { margin-bottom: 16px; max-width: 85%; }
        .msg.user { margin-left: auto; }
        .msg-bubble { padding: 10px 14px; border-radius: 12px; line-height: 1.5; font-size: 0.9rem; }
        .msg.user .msg-bubble { background: #7c83fd; color: white; border-radius: 12px 12px 4px 12px; }
        .msg.barry .msg-bubble { background: #1e1e1e; border: 1px solid #333;
                                  border-radius: 12px 12px 12px 4px; white-space: pre-wrap; }
        .msg-label { font-size: 0.75rem; color: #666; margin-bottom: 4px; }
        .msg.user .msg-label { text-align: right; }
        .input-area { padding: 16px; background: #161616; border-top: 1px solid #2a2a2a;
                      display: flex; gap: 10px; }
        .input-area textarea { flex: 1; background: #1e1e1e; border: 1px solid #444;
                               border-radius: 8px; padding: 10px; color: #e0e0e0;
                               resize: none; font-size: 0.9rem; font-family: inherit;
                               outline: none; min-height: 44px; max-height: 120px; }
        .input-area textarea:focus { border-color: #7c83fd; }
        .send-btn { padding: 10px 20px; background: #7c83fd; color: white; border: none;
                    border-radius: 8px; cursor: pointer; font-size: 0.9rem; white-space: nowrap; }
        .send-btn:hover { background: #6470fc; }
        .typing { color: #7c83fd; font-size: 0.85rem; padding: 4px; animation: pulse 1.5s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        pre { background: #0a0a0a; padding: 10px; border-radius: 6px; overflow-x: auto;
              font-size: 0.8rem; margin: 8px 0; }
        strong { color: #fff; }
    </style>
</head>
<body>
    <header>
        <div class="status-dot" id="statusDot"></div>
        <h1>⚡ Barry</h1>
        <span id="statusText" style="color:#888;font-size:0.85rem">Loading...</span>
    </header>
    <div class="main">
        <div class="sidebar">
            <h3>Quick Actions</h3>
            <button class="btn primary" onclick="sendMessage('Give me my morning briefing')">☀️ Morning Briefing</button>
            <button class="btn" onclick="sendMessage('What are my priorities today?')">📋 Today\\'s Priorities</button>
            <button class="btn" onclick="sendMessage('What\\'s on my calendar this week?')">📅 Calendar</button>
            <button class="btn" onclick="sendMessage('Any important emails?')">📧 Emails</button>
            <button class="btn" onclick="sendMessage('Any WhatsApp messages?')">💬 WhatsApp</button>

            <h3>System</h3>
            <button class="btn" onclick="runJob('poll')">🔄 Poll Now</button>
            <button class="btn" onclick="loadStatus()">📊 Status</button>
            <button class="btn" onclick="resetConv()">🗑️ Reset Chat</button>

            <h3>iPhone Setup</h3>
            <button class="btn" onclick="showIphoneSetup()">📱 Setup Guide</button>
        </div>
        <div class="chat-area">
            <div class="messages" id="messages">
                <div class="msg barry">
                    <div class="msg-label">Barry</div>
                    <div class="msg-bubble">Hey! I\\'m Barry, your AI assistant. How can I help you today?
\\nTry: "Give me my morning briefing" or "What are my priorities?"</div>
                </div>
            </div>
            <div class="input-area">
                <textarea id="input" placeholder="Ask Barry anything... (Shift+Enter for new line)"
                          onkeydown="handleKey(event)"></textarea>
                <button class="send-btn" onclick="sendFromInput()">Send ↗</button>
            </div>
        </div>
    </div>
    <script>
        let isStreaming = false;

        async function loadStatus() {
            try {
                const r = await fetch('/status');
                const data = await r.json();
                document.getElementById('statusText').textContent =
                    `${data.owner} · ${data.memory.todos} todos · ${data.memory.facts} facts`;
                document.getElementById('statusDot').style.background = '#4caf50';
            } catch(e) {
                document.getElementById('statusDot').style.background = '#f44336';
            }
        }

        function addMessage(role, content) {
            const msgs = document.getElementById('messages');
            const div = document.createElement('div');
            div.className = `msg ${role}`;
            const label = document.createElement('div');
            label.className = 'msg-label';
            label.textContent = role === 'user' ? 'You' : 'Barry';
            const bubble = document.createElement('div');
            bubble.className = 'msg-bubble';
            bubble.textContent = content;
            div.appendChild(label);
            div.appendChild(bubble);
            msgs.appendChild(div);
            msgs.scrollTop = msgs.scrollHeight;
            return bubble;
        }

        async function sendMessage(msg) {
            if (isStreaming) return;
            isStreaming = true;

            addMessage('user', msg);
            const barryBubble = addMessage('barry', '⚡ Thinking...');

            try {
                const resp = await fetch('/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: msg, stream: true})
                });

                const reader = resp.body.getReader();
                const decoder = new TextDecoder();
                let text = '';
                barryBubble.textContent = '';

                while (true) {
                    const {done, value} = await reader.read();
                    if (done) break;
                    const chunk = decoder.decode(value);
                    const lines = chunk.split('\\n');
                    for (const line of lines) {
                        if (line.startsWith('data: ') && !line.includes('[DONE]')) {
                            text += line.slice(6);
                            barryBubble.textContent = text;
                            document.getElementById('messages').scrollTop = 999999;
                        }
                    }
                }
            } catch(e) {
                barryBubble.textContent = 'Error: ' + e.message;
            }
            isStreaming = false;
        }

        function sendFromInput() {
            const input = document.getElementById('input');
            const msg = input.value.trim();
            if (!msg) return;
            input.value = '';
            sendMessage(msg);
        }

        function handleKey(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendFromInput();
            }
        }

        async function runJob(jobId) {
            await fetch(`/scheduler/run/${jobId}`, {method: 'POST'});
            addMessage('barry', `🔄 Running ${jobId} job...`);
        }

        async function resetConv() {
            await fetch('/reset', {method: 'POST'});
            document.getElementById('messages').innerHTML = '';
            addMessage('barry', 'Conversation reset. What can I help you with?');
        }

        async function showIphoneSetup() {
            const r = await fetch('/iphone/setup');
            const data = await r.json();
            addMessage('barry', data.guide);
        }

        loadStatus();
        setInterval(loadStatus, 60000);
    </script>
</body>
</html>"""

    return app
