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
  :root {
    --bg: #0a0a0f;
    --surface: #111118;
    --surface2: #16161f;
    --border: #1e1e2e;
    --accent: #7c6aff;
    --accent2: #a78bfa;
    --green: #22d3a0;
    --red: #f87171;
    --yellow: #fbbf24;
    --text: #e2e2f0;
    --muted: #6b6b8a;
    --radius: 12px;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', sans-serif;
    background: var(--bg); color: var(--text); height: 100vh; display: flex;
    flex-direction: column; overflow: hidden; }

  /* ── Header ── */
  header {
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 0 24px;
    height: 56px;
    display: flex;
    align-items: center;
    gap: 16px;
    flex-shrink: 0;
  }
  .logo { display: flex; align-items: center; gap: 10px; }
  .logo-icon {
    width: 32px; height: 32px; border-radius: 8px;
    background: linear-gradient(135deg, #7c6aff, #a78bfa);
    display: flex; align-items: center; justify-content: center;
    font-size: 16px; flex-shrink: 0;
  }
  .logo h1 { font-size: 1.1rem; font-weight: 700; color: var(--text); letter-spacing: -0.02em; }
  .logo span { font-size: 0.7rem; color: var(--muted); font-weight: 400; }
  .header-spacer { flex: 1; }
  .status-pill {
    display: flex; align-items: center; gap: 6px;
    background: var(--surface2); border: 1px solid var(--border);
    border-radius: 20px; padding: 4px 12px; font-size: 0.75rem; color: var(--muted);
  }
  .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--green);
    box-shadow: 0 0 6px var(--green); animation: pulse 2s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.5} }
  .nav-tabs { display: flex; gap: 2px; }
  .tab { padding: 6px 14px; border-radius: 6px; cursor: pointer; font-size: 0.82rem;
    color: var(--muted); border: none; background: transparent; transition: all 0.15s; }
  .tab:hover { color: var(--text); background: var(--surface2); }
  .tab.active { color: var(--accent2); background: #7c6aff15; }

  /* ── Layout ── */
  .main { display: flex; flex: 1; overflow: hidden; }

  /* ── Sidebar ── */
  .sidebar {
    width: 260px; flex-shrink: 0;
    background: var(--surface);
    border-right: 1px solid var(--border);
    display: flex; flex-direction: column;
    overflow: hidden;
  }
  .sidebar-section { padding: 16px; border-bottom: 1px solid var(--border); }
  .sidebar-section:last-child { border-bottom: none; flex: 1; overflow-y: auto; }
  .section-label {
    font-size: 0.68rem; font-weight: 600; color: var(--muted);
    text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 10px;
  }
  .action-btn {
    display: flex; align-items: center; gap: 10px;
    width: 100%; padding: 8px 10px; margin-bottom: 4px;
    background: transparent; border: 1px solid transparent;
    border-radius: 8px; color: var(--muted); cursor: pointer;
    font-size: 0.83rem; text-align: left; transition: all 0.15s;
  }
  .action-btn:hover { background: var(--surface2); border-color: var(--border); color: var(--text); }
  .action-btn.highlight { color: var(--accent2); }
  .action-btn.highlight:hover { background: #7c6aff12; border-color: #7c6aff30; }
  .action-btn .icon { font-size: 15px; width: 20px; text-align: center; }

  /* ── Connector Status ── */
  .connector-list { display: flex; flex-direction: column; gap: 6px; }
  .connector-item { display: flex; align-items: center; gap: 8px; font-size: 0.8rem; }
  .connector-item .c-icon { font-size: 13px; width: 18px; }
  .connector-item .c-name { flex: 1; color: var(--muted); }
  .c-badge {
    font-size: 0.65rem; padding: 2px 7px; border-radius: 10px; font-weight: 500;
  }
  .c-badge.on { background: #22d3a015; color: var(--green); border: 1px solid #22d3a030; }
  .c-badge.off { background: #f8717115; color: var(--red); border: 1px solid #f8717130; }
  .c-badge.partial { background: #fbbf2415; color: var(--yellow); border: 1px solid #fbbf2430; }

  /* ── Chat Panel ── */
  .chat-panel { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
  .messages {
    flex: 1; overflow-y: auto; padding: 24px;
    display: flex; flex-direction: column; gap: 20px;
  }
  .messages::-webkit-scrollbar { width: 4px; }
  .messages::-webkit-scrollbar-track { background: transparent; }
  .messages::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }

  .msg { display: flex; gap: 10px; max-width: 82%; }
  .msg.user { align-self: flex-end; flex-direction: row-reverse; }
  .msg-avatar {
    width: 30px; height: 30px; border-radius: 8px; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center; font-size: 14px;
  }
  .msg.barry .msg-avatar { background: linear-gradient(135deg,#7c6aff,#a78bfa); }
  .msg.user .msg-avatar { background: var(--surface2); border: 1px solid var(--border); }
  .msg-body { display: flex; flex-direction: column; gap: 4px; }
  .msg.user .msg-body { align-items: flex-end; }
  .msg-name { font-size: 0.7rem; color: var(--muted); font-weight: 500; }
  .msg-bubble {
    padding: 11px 15px; border-radius: 14px;
    font-size: 0.875rem; line-height: 1.6;
    white-space: pre-wrap; word-break: break-word;
  }
  .msg.barry .msg-bubble {
    background: var(--surface2); border: 1px solid var(--border);
    border-top-left-radius: 4px; color: var(--text);
  }
  .msg.user .msg-bubble {
    background: linear-gradient(135deg, #7c6aff, #6355e8);
    color: #fff; border-top-right-radius: 4px;
    box-shadow: 0 4px 15px #7c6aff30;
  }
  .msg-time { font-size: 0.65rem; color: var(--muted); }
  .thinking-indicator {
    display: flex; gap: 4px; align-items: center; padding: 4px 0;
  }
  .thinking-indicator span {
    width: 6px; height: 6px; background: var(--accent);
    border-radius: 50%; animation: bounce 1.2s infinite;
  }
  .thinking-indicator span:nth-child(2) { animation-delay: 0.2s; }
  .thinking-indicator span:nth-child(3) { animation-delay: 0.4s; }
  @keyframes bounce { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-5px)} }

  /* ── Input ── */
  .input-wrap {
    padding: 16px 24px 20px;
    background: var(--surface);
    border-top: 1px solid var(--border);
  }
  .input-row {
    display: flex; align-items: flex-end; gap: 10px;
    background: var(--surface2); border: 1px solid var(--border);
    border-radius: 14px; padding: 8px 8px 8px 16px;
    transition: border-color 0.2s;
  }
  .input-row:focus-within { border-color: #7c6aff60; box-shadow: 0 0 0 3px #7c6aff12; }
  textarea {
    flex: 1; background: transparent; border: none; outline: none;
    color: var(--text); font-size: 0.9rem; font-family: inherit;
    resize: none; line-height: 1.5; min-height: 24px; max-height: 140px;
    padding: 4px 0;
  }
  textarea::placeholder { color: var(--muted); }
  .send-btn {
    width: 36px; height: 36px; border-radius: 10px; border: none; cursor: pointer;
    background: linear-gradient(135deg, #7c6aff, #6355e8);
    color: white; font-size: 16px; display: flex; align-items: center;
    justify-content: center; flex-shrink: 0; transition: all 0.15s;
    box-shadow: 0 2px 8px #7c6aff40;
  }
  .send-btn:hover { transform: scale(1.05); box-shadow: 0 4px 12px #7c6aff50; }
  .send-btn:disabled { opacity: 0.4; transform: none; cursor: not-allowed; }
  .input-hints { display: flex; gap: 8px; margin-top: 8px; flex-wrap: wrap; }
  .hint-chip {
    font-size: 0.72rem; color: var(--muted); background: var(--surface2);
    border: 1px solid var(--border); border-radius: 20px; padding: 3px 10px;
    cursor: pointer; transition: all 0.15s;
  }
  .hint-chip:hover { color: var(--accent2); border-color: #7c6aff40; background: #7c6aff08; }

  /* ── Info Panel (right side) ── */
  .info-panel {
    width: 280px; flex-shrink: 0;
    background: var(--surface);
    border-left: 1px solid var(--border);
    overflow-y: auto; display: flex; flex-direction: column; gap: 0;
  }
  .info-panel::-webkit-scrollbar { width: 3px; }
  .info-panel::-webkit-scrollbar-thumb { background: var(--border); }
  .info-card { padding: 16px; border-bottom: 1px solid var(--border); }
  .info-card h4 { font-size: 0.7rem; font-weight: 600; color: var(--muted);
    text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 12px; }
  .stat-row { display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 8px; }
  .stat-label { font-size: 0.8rem; color: var(--muted); }
  .stat-val { font-size: 0.85rem; font-weight: 600; color: var(--text); }
  .stat-val.green { color: var(--green); }
  .stat-val.yellow { color: var(--yellow); }
  .event-item { padding: 8px 0; border-bottom: 1px solid var(--border); }
  .event-item:last-child { border-bottom: none; }
  .event-time { font-size: 0.7rem; color: var(--accent2); font-weight: 500; }
  .event-title { font-size: 0.82rem; color: var(--text); margin-top: 2px; }
  .todo-item { display: flex; align-items: flex-start; gap: 8px; padding: 6px 0; }
  .todo-check { width: 16px; height: 16px; border-radius: 4px; border: 1.5px solid var(--border);
    flex-shrink: 0; cursor: pointer; margin-top: 1px; }
  .todo-text { font-size: 0.82rem; color: var(--text); line-height: 1.4; }
  .priority-dot { width: 6px; height: 6px; border-radius: 50%; margin-top: 6px; flex-shrink: 0; }
  .p1 { background: var(--red); }
  .p2 { background: var(--yellow); }
  .p3 { background: var(--muted); }
  .empty-state { text-align: center; color: var(--muted); font-size: 0.8rem; padding: 12px 0; }

  /* ── Tabs ── */
  .tab-content { display: none; }
  .tab-content.active { display: flex; flex: 1; overflow: hidden; }
</style>
</head>
<body>

<header>
  <div class="logo">
    <div class="logo-icon">⚡</div>
    <div>
      <h1>Barry</h1>
      <span>AI Assistant</span>
    </div>
  </div>
  <div class="nav-tabs">
    <button class="tab active" onclick="switchTab('chat')">Chat</button>
    <button class="tab" onclick="switchTab('briefing')">Briefing</button>
    <button class="tab" onclick="switchTab('todos')">Todos</button>
  </div>
  <div class="header-spacer"></div>
  <div class="status-pill">
    <div class="dot" id="statusDot"></div>
    <span id="statusText">Connecting...</span>
  </div>
</header>

<div class="main">

  <!-- Sidebar -->
  <div class="sidebar">
    <div class="sidebar-section">
      <div class="section-label">Quick Actions</div>
      <button class="action-btn highlight" onclick="q('Give me my morning briefing')">
        <span class="icon">☀️</span> Morning Briefing
      </button>
      <button class="action-btn" onclick="q('What are my top priorities right now?')">
        <span class="icon">🎯</span> Priorities
      </button>
      <button class="action-btn" onclick="q(\\'What\\'s on my calendar this week?\\')">
        <span class="icon">📅</span> Calendar
      </button>
      <button class="action-btn" onclick="q(\\'Any important emails I should know about?\\')">
        <span class="icon">📧</span> Emails
      </button>
      <button class="action-btn" onclick="q(\\'Any WhatsApp messages?\\')">
        <span class="icon">💬</span> WhatsApp
      </button>
      <button class="action-btn" onclick="q(\\'Draft a reply to the latest email matching my tone\\')">
        <span class="icon">✍️</span> Draft Reply
      </button>
    </div>

    <div class="sidebar-section">
      <div class="section-label">System</div>
      <button class="action-btn" onclick="pollNow()">
        <span class="icon">🔄</span> Sync Now
      </button>
      <button class="action-btn" onclick="generateBriefing()">
        <span class="icon">📋</span> Gen Briefing
      </button>
      <button class="action-btn" onclick="resetConv()">
        <span class="icon">🗑️</span> Clear Chat
      </button>
      <button class="action-btn" onclick="showIphoneSetup()">
        <span class="icon">📱</span> iPhone Setup
      </button>
    </div>

    <div class="sidebar-section">
      <div class="section-label">Connectors</div>
      <div class="connector-list" id="connectorList">
        <div class="connector-item">
          <span class="c-icon">📅</span>
          <span class="c-name">Google Cal</span>
          <span class="c-badge off" id="c-google">off</span>
        </div>
        <div class="connector-item">
          <span class="c-icon">🍎</span>
          <span class="c-name">iCloud</span>
          <span class="c-badge off" id="c-icloud">off</span>
        </div>
        <div class="connector-item">
          <span class="c-icon">📧</span>
          <span class="c-name">Email</span>
          <span class="c-badge off" id="c-email">off</span>
        </div>
        <div class="connector-item">
          <span class="c-icon">💬</span>
          <span class="c-name">WhatsApp</span>
          <span class="c-badge off" id="c-whatsapp">off</span>
        </div>
        <div class="connector-item">
          <span class="c-icon">📱</span>
          <span class="c-name">iPhone</span>
          <span class="c-badge on" id="c-iphone">on</span>
        </div>
      </div>
    </div>
  </div>

  <!-- Chat Tab -->
  <div class="tab-content active" id="tab-chat">
    <div class="chat-panel">
      <div class="messages" id="messages">
        <div class="msg barry">
          <div class="msg-avatar">⚡</div>
          <div class="msg-body">
            <div class="msg-name">Barry</div>
            <div class="msg-bubble">Hey! I'm Barry, your personal AI assistant.

I'm connected to your calendar, emails, WhatsApp, and iPhone. I can see everything going on in your life and help you stay on top of it.

Try asking me:
• "Give me my morning briefing"
• "What should I focus on today?"
• "Draft a reply to [person]'s email"
• "Add a todo: call dentist tomorrow"</div>
            <div class="msg-time" id="welcome-time"></div>
          </div>
        </div>
      </div>
      <div class="input-wrap">
        <div class="input-row">
          <textarea id="chatInput" placeholder="Ask Barry anything..." rows="1"
            onkeydown="handleKey(event)" oninput="autoResize(this)"></textarea>
          <button class="send-btn" id="sendBtn" onclick="sendFromInput()">↑</button>
        </div>
        <div class="input-hints">
          <span class="hint-chip" onclick="q(\\'What are my priorities?\\')">Priorities</span>
          <span class="hint-chip" onclick="q(\\'Give me my briefing\\')">Briefing</span>
          <span class="hint-chip" onclick="q(\\'Check my calendar\\')">Calendar</span>
          <span class="hint-chip" onclick="q(\\'Any urgent emails?\\')">Urgent emails</span>
        </div>
      </div>
    </div>

    <!-- Right panel -->
    <div class="info-panel">
      <div class="info-card">
        <h4>Overview</h4>
        <div class="stat-row"><span class="stat-label">Pending todos</span><span class="stat-val yellow" id="s-todos">—</span></div>
        <div class="stat-row"><span class="stat-label">Events this week</span><span class="stat-val" id="s-events">—</span></div>
        <div class="stat-row"><span class="stat-label">Unread emails</span><span class="stat-val" id="s-emails">—</span></div>
        <div class="stat-row"><span class="stat-label">Facts learned</span><span class="stat-val green" id="s-facts">—</span></div>
        <div class="stat-row"><span class="stat-label">Tone profiles</span><span class="stat-val green" id="s-tone">—</span></div>
      </div>

      <div class="info-card">
        <h4>Upcoming</h4>
        <div id="upcomingEvents"><div class="empty-state">No events synced yet</div></div>
      </div>

      <div class="info-card">
        <h4>Top Todos</h4>
        <div id="topTodos"><div class="empty-state">No todos yet</div></div>
      </div>
    </div>
  </div>

  <!-- Briefing Tab -->
  <div class="tab-content" id="tab-briefing">
    <div style="flex:1;display:flex;flex-direction:column;overflow:hidden;">
      <div style="padding:20px 24px;border-bottom:1px solid var(--border);display:flex;gap:12px;align-items:center;background:var(--surface);">
        <h2 style="font-size:1rem;font-weight:600;">Daily Briefing</h2>
        <div style="flex:1"></div>
        <button class="action-btn highlight" style="width:auto;padding:7px 16px;" onclick="generateBriefing()">⚡ Generate Now</button>
      </div>
      <div id="briefingContent" style="flex:1;overflow-y:auto;padding:24px;font-size:0.9rem;line-height:1.8;color:var(--text);white-space:pre-wrap;">
        <div style="text-align:center;color:var(--muted);padding:40px 0;">
          Click "Generate Now" to get your daily briefing
        </div>
      </div>
    </div>
  </div>

  <!-- Todos Tab -->
  <div class="tab-content" id="tab-todos">
    <div style="flex:1;display:flex;flex-direction:column;overflow:hidden;">
      <div style="padding:16px 24px;border-bottom:1px solid var(--border);display:flex;gap:12px;align-items:center;background:var(--surface);">
        <h2 style="font-size:1rem;font-weight:600;">Todos</h2>
        <div style="flex:1"></div>
        <button class="action-btn" style="width:auto;padding:6px 14px;" onclick="loadTodos()">🔄 Refresh</button>
        <button class="action-btn highlight" style="width:auto;padding:6px 14px;" onclick="promptAddTodo()">+ Add</button>
      </div>
      <div id="todoList" style="flex:1;overflow-y:auto;padding:16px 24px;">
        <div style="text-align:center;color:var(--muted);padding:40px 0;">Loading todos...</div>
      </div>
    </div>
  </div>

</div>

<script>
let streaming = false;

// Time
document.getElementById('welcome-time').textContent = new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'});

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 140) + 'px';
}

function switchTab(name) {
  document.querySelectorAll('.tab').forEach((t,i) => {
    t.classList.toggle('active', ['chat','briefing','todos'][i] === name);
  });
  document.querySelectorAll('.tab-content').forEach(c => {
    c.classList.toggle('active', c.id === 'tab-'+name);
  });
  if (name === 'todos') loadTodos();
}

async function loadStatus() {
  try {
    const r = await fetch('/status');
    const d = await r.json();
    document.getElementById('statusText').textContent = d.owner + ' · online';
    document.getElementById('statusDot').style.background = '#22d3a0';
    document.getElementById('s-todos').textContent = d.memory.todos;
    document.getElementById('s-events').textContent = d.last_events;
    document.getElementById('s-emails').textContent = d.last_emails;
    document.getElementById('s-facts').textContent = d.memory.facts;
    document.getElementById('s-tone').textContent = d.memory.tone_profiles;
    // Connectors
    const c = d.connectors || {};
    const map = {google_calendar:'c-google', icloud:'c-icloud', email:'c-email',
                 whatsapp:'c-whatsapp', iphone_shortcuts:'c-iphone'};
    for (const [k,id] of Object.entries(map)) {
      const el = document.getElementById(id);
      if (el) { el.textContent = c[k] ? 'on' : 'off'; el.className = 'c-badge ' + (c[k] ? 'on' : 'off'); }
    }
  } catch(e) {
    document.getElementById('statusText').textContent = 'offline';
    document.getElementById('statusDot').style.background = '#f87171';
  }
}

function addMessage(role, content) {
  const msgs = document.getElementById('messages');
  const wrap = document.createElement('div');
  wrap.className = 'msg ' + role;
  const avatar = document.createElement('div');
  avatar.className = 'msg-avatar';
  avatar.textContent = role === 'barry' ? '⚡' : '👤';
  const body = document.createElement('div');
  body.className = 'msg-body';
  body.innerHTML = `<div class="msg-name">${role === 'barry' ? 'Barry' : 'You'}</div>`;
  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  bubble.textContent = content;
  body.appendChild(bubble);
  body.innerHTML += `<div class="msg-time">${new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}</div>`;
  body.insertBefore(bubble, body.lastChild);
  wrap.appendChild(avatar);
  wrap.appendChild(body);
  msgs.appendChild(wrap);
  msgs.scrollTop = msgs.scrollHeight;
  return bubble;
}

function addThinking() {
  const msgs = document.getElementById('messages');
  const wrap = document.createElement('div');
  wrap.className = 'msg barry'; wrap.id = 'thinking-msg';
  wrap.innerHTML = `<div class="msg-avatar">⚡</div>
    <div class="msg-body"><div class="msg-name">Barry</div>
    <div class="thinking-indicator"><span></span><span></span><span></span></div></div>`;
  msgs.appendChild(wrap);
  msgs.scrollTop = msgs.scrollHeight;
}

function removeThinking() {
  const el = document.getElementById('thinking-msg');
  if (el) el.remove();
}

async function q(msg) {
  if (streaming) return;
  switchTab('chat');
  await sendMessage(msg);
}

async function sendMessage(msg) {
  if (streaming) return;
  streaming = true;
  document.getElementById('sendBtn').disabled = true;

  addMessage('user', msg);
  addThinking();

  try {
    const resp = await fetch('/chat', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({message: msg, stream: true})
    });
    removeThinking();
    const bubble = addMessage('barry', '');
    const reader = resp.body.getReader();
    const dec = new TextDecoder();
    let text = '';
    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      const chunk = dec.decode(value);
      for (const line of chunk.split('\\n')) {
        if (line.startsWith('data: ') && !line.includes('[DONE]')) {
          text += line.slice(6);
          bubble.textContent = text;
          document.getElementById('messages').scrollTop = 999999;
        }
      }
    }
  } catch(e) {
    removeThinking();
    addMessage('barry', 'Connection error: ' + e.message);
  }
  streaming = false;
  document.getElementById('sendBtn').disabled = false;
  loadStatus();
}

function sendFromInput() {
  const inp = document.getElementById('chatInput');
  const msg = inp.value.trim();
  if (!msg || streaming) return;
  inp.value = ''; inp.style.height = 'auto';
  sendMessage(msg);
}

function handleKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendFromInput(); }
}

async function generateBriefing() {
  switchTab('briefing');
  document.getElementById('briefingContent').textContent = 'Generating briefing...';
  try {
    const r = await fetch('/briefing');
    const d = await r.json();
    document.getElementById('briefingContent').textContent = d.briefing;
  } catch(e) {
    document.getElementById('briefingContent').textContent = 'Error: ' + e.message;
  }
}

async function loadTodos() {
  const list = document.getElementById('todoList');
  list.innerHTML = '<div style="text-align:center;color:var(--muted);padding:20px">Loading...</div>';
  try {
    const r = await fetch('/todos');
    const d = await r.json();
    const todos = d.todos || [];
    if (!todos.length) {
      list.innerHTML = '<div style="text-align:center;color:var(--muted);padding:40px 0">No todos yet! You\\'re all caught up 🎉</div>';
      return;
    }
    const icons = {1:'🔴',2:'🟠',3:'🟡',4:'⚪'};
    list.innerHTML = todos.map(t => `
      <div style="display:flex;align-items:flex-start;gap:12px;padding:12px;margin-bottom:6px;background:var(--surface2);border:1px solid var(--border);border-radius:10px;">
        <span style="font-size:16px;margin-top:1px">${icons[t.priority]||'⚪'}</span>
        <div style="flex:1">
          <div style="font-size:0.875rem;font-weight:500;color:var(--text)">${t.title}</div>
          ${t.due_date ? `<div style="font-size:0.72rem;color:var(--muted);margin-top:3px">Due ${t.due_date.slice(0,10)}</div>` : ''}
          ${t.ai_reason ? `<div style="font-size:0.72rem;color:var(--accent2);margin-top:3px;font-style:italic">${t.ai_reason}</div>` : ''}
        </div>
        <button onclick="completeTodo(${t.id})" style="background:transparent;border:1px solid var(--border);color:var(--muted);border-radius:6px;padding:3px 10px;cursor:pointer;font-size:0.75rem">Done</button>
      </div>`).join('');
  } catch(e) {
    list.innerHTML = '<div style="color:var(--red);padding:12px">Error loading todos: '+e.message+'</div>';
  }
}

async function completeTodo(id) {
  await fetch('/todos/'+id+'/complete', {method:'PUT'});
  loadTodos(); loadStatus();
}

async function promptAddTodo() {
  const title = prompt('New todo:');
  if (!title) return;
  await fetch('/todos', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({title})});
  loadTodos();
}

async function pollNow() {
  await fetch('/scheduler/run/poll', {method:'POST'});
  setTimeout(loadStatus, 2000);
}

async function resetConv() {
  await fetch('/reset', {method:'POST'});
  document.getElementById('messages').innerHTML = '';
  addMessage('barry', 'Conversation reset. What can I help you with?');
}

async function showIphoneSetup() {
  const r = await fetch('/iphone/setup');
  const d = await r.json();
  q('Show me the iPhone setup guide');
}

loadStatus();
setInterval(loadStatus, 30000);
</script>
</body>
</html>"""
