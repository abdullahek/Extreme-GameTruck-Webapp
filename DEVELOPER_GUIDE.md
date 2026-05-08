# Extreme Game Truck — Developer Guide & Architecture Documentation

> **Version:** 1.0  
> **Date:** April 2026  
> **Audience:** Engineering Hiring Team · CEO · Engineers

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Technology Stack](#3-technology-stack)
4. [Directory Structure](#4-directory-structure)
5. [Database Schema](#5-database-schema)
6. [Backend Architecture](#6-backend-architecture)
7. [Frontend Architecture](#7-frontend-architecture)
8. [Inbound SMS Message Flow](#8-inbound-sms-message-flow)
9. [AI Integration](#9-ai-integration)
10. [Real-Time Communication (WebSockets)](#10-real-time-communication-websockets)
11. [Authentication & Security](#11-authentication--security)
12. [Logging & Observability](#12-logging--observability)
13. [API Reference](#13-api-reference)
14. [Deployment & Infrastructure](#14-deployment--infrastructure)
15. [Configuration & Environment Variables](#15-configuration--environment-variables)
16. [Known Delays & Performance Characteristics](#16-known-delays--performance-characteristics)
17. [Development Workflow](#17-development-workflow)
18. [Engineering Decisions & Trade-offs](#18-engineering-decisions--trade-offs)

---

## 1. Project Overview

**Extreme Game Truck** is a full-stack customer communication platform purpose-built for the mobile gaming entertainment industry. It enables staff to manage all customer SMS conversations in a single dashboard — with AI-powered automatic responses, real-time conversation tracking, and comprehensive activity logging.

### Core Capabilities

| Capability | Description |
|---|---|
| **SMS Inbox** | Receive, display, and reply to customer SMS messages via Twilio |
| **AI Auto-Response** | Automatically generate and send context-aware replies using OpenAI |
| **Message Batching** | Queue rapid multi-part messages before sending a single AI request |
| **Real-Time UI** | Live conversation updates via Socket.IO WebSockets |
| **Web Widget Support** | Accept conversations from an embedded chat widget (non-SMS channel) |
| **Analytics Dashboard** | Aggregated stats: total contacts, total messages, top contacts |
| **Audit Logging** | Full structured database logging of all SMS, AI, webhook, and auth events |
| **User Management** | JWT-authenticated accounts with per-user Twilio credential isolation |

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        CLIENT BROWSER                                   │
│                                                                         │
│   React 18 + Vite 5 SPA                                                 │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│   │  Dashboard  │  │  Responses  │  │  Settings   │  │  Login/     │   │
│   │  (Stats)    │  │  (Chat UI)  │  │  (Twilio)   │  │  Signup     │   │
│   └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │
│                TanStack Query + Socket.IO Client                         │
└─────────────────────────┬───────────────────────────────────────────────┘
                          │  HTTP / WebSocket (same port)
┌─────────────────────────▼───────────────────────────────────────────────┐
│                     FLASK BACKEND  (port 5000 dev / PORT env prod)       │
│                                                                         │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌──────────┐ ┌──────────┐   │
│  │ auth_bp   │ │  sms_bp   │ │dashboard_ │ │ logs_bp  │ │ widget_  │   │
│  │ /api/auth │ │ /api/sms  │ │ bp        │ │ /api/logs│ │ message_ │   │
│  └───────────┘ └─────┬─────┘ └───────────┘ └──────────┘ │ bp       │   │
│                      │                                   └──────────┘   │
│               30-second message queue                                   │
│               threading.Timer per contact                               │
│                      │                                                  │
│  Flask-SQLAlchemy  ──┼──  Flask-SocketIO                                │
└──────────────────────┼──────────────────────────────────────────────────┘
                       │
         ┌─────────────┼─────────────┐
         │             │             │
┌────────▼───┐  ┌──────▼──────┐  ┌──▼─────────────────────────────────┐
│ PostgreSQL  │  │   Twilio    │  │  External AI Service               │
│ (Neon       │  │   SMS API   │  │  extreme-game-truck-               │
│  pooled)    │  │             │  │  graelonbrown.replit.app           │
└─────────────┘  └─────────────┘  │  POST /thread  →  thread_id       │
                                   │  POST /chat    →  AI response     │
                                   └────────────────────────────────────┘
```

### Architecture Pattern

- **Monorepo monolith:** React SPA compiled by Vite and served as static files from Flask's `dist/` directory on the same port.
- **Blueprint-modular Flask:** Seven Flask Blueprints group routes by domain concern.
- **Stateless API + stateful WebSocket rooms:** REST for data, Socket.IO for real-time push.
- **Threaded background tasks:** Python `threading.Timer` for the message batching queue — no external task queue (Celery, RQ) required at current scale.

---

## 3. Technology Stack

### Backend

| Package | Version | Role |
|---|---|---|
| Python | 3.x | Runtime |
| Flask | 3.1 | HTTP framework |
| Flask-SQLAlchemy | latest | ORM & connection pooling |
| Flask-CORS | latest | Cross-origin resource sharing |
| Flask-SocketIO | latest | WebSocket server |
| PyJWT | latest | JWT creation & validation |
| Werkzeug | latest | Password hashing (pbkdf2:sha256) |
| Requests | latest | HTTP client for Twilio + AI APIs |
| SQLAlchemy | latest | Connection pool events |
| psycopg2 | latest | PostgreSQL adapter |

### Frontend

| Package | Version | Role |
|---|---|---|
| React | 18.2 | UI framework |
| Vite | 5.0 | Build tool & dev server |
| React Router DOM | 7 | Client-side routing |
| TanStack Query | 5 | Server state, caching, polling |
| Socket.IO Client | 4.8 | WebSocket real-time updates |

### Infrastructure

| Service | Purpose |
|---|---|
| PostgreSQL via Neon | Primary database with connection pooler |
| Twilio | Inbound/outbound SMS gateway |
| OpenAI (external service) | AI thread creation and chat responses |
| Replit Autoscale | Hosting & deployment target |

---

## 4. Directory Structure

```
extreme-game-truck/
│
├── app.py                        # Flask application factory, ORM models, entry point
├── start.sh                      # Build script: Vite build → cache-bust → start Flask
├── vite.config.js                # Vite dev proxy (/api → localhost:5000)
├── package.json                  # npm dependencies (React, Vite, TanStack Query, Socket.IO)
├── pyproject.toml                # Python dependency declarations
│
├── backend/                      # Flask blueprints (domain-driven)
│   ├── __init__.py
│   ├── auth.py                   # POST /api/auth/login, /register, /logout
│   ├── user.py                   # GET/PUT /api/user/profile
│   ├── settings.py               # GET/POST /api/settings (Twilio credentials)
│   ├── dashboard.py              # GET /api/dashboard/stats
│   ├── sms.py                    # Twilio webhook + message queue + AI flow
│   ├── egt_widget_message.py     # POST /api/egt_widget_message (web widget channel)
│   ├── logs.py                   # GET /api/logs, /api/logs/stats
│   └── logger_utils.py           # Shared structured logging helpers
│
├── src/                          # React frontend source
│   ├── index.jsx                 # React DOM root mount
│   ├── App.jsx                   # Router, QueryClientProvider, auth guard
│   ├── App.css                   # Global styles
│   ├── pages/
│   │   ├── Login/                # Login page
│   │   ├── Signup/               # Registration page
│   │   ├── Dashboard/            # Stats overview page
│   │   ├── Responses/            # Main chat/conversation page
│   │   └── Settings/             # Twilio settings configuration
│   └── components/
│       └── Header/               # Fixed top navigation bar
│
├── dist/                         # Vite production build output (auto-generated)
│   ├── index.html
│   └── assets/
│       ├── index-<timestamp>.js
│       └── index-<timestamp>.css
│
└── DEVELOPER_GUIDE.md            # This document
```

---

## 5. Database Schema

All tables are auto-created via `db.create_all()` at startup.

### `user`

| Column | Type | Notes |
|---|---|---|
| `id` | VARCHAR(36) | UUID primary key |
| `full_name` | VARCHAR(100) | Required |
| `email` | VARCHAR(100) | Unique, required |
| `company_name` | VARCHAR(100) | Optional |
| `password` | VARCHAR(200) | pbkdf2:sha256 hash |
| `is_verified` | BOOLEAN | Auto-set to `true` |
| `created_at` | DATETIME | UTC timestamp |

### `user_settings`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER | Auto-increment PK |
| `user_id` | VARCHAR(36) | FK → `user.id` |
| `account_sid` | VARCHAR(100) | Twilio Account SID |
| `account_token` | VARCHAR(100) | Twilio Auth Token |
| `sms_number` | VARCHAR(20) | Twilio phone number |
| `is_number_verified` | BOOLEAN | Verification flag |
| `created_at` / `updated_at` | DATETIME | UTC timestamps |

### `contacts`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER | Auto-increment PK |
| `user_id` | VARCHAR(36) | FK → `user.id` |
| `phone_number` | VARCHAR(20) | E.164 format for SMS; `widget_<suffix>` for widget contacts |
| `name` | VARCHAR(100) | Display name (auto-generated if unknown) |
| `thread_id` | VARCHAR(100) | OpenAI conversation thread ID (persisted per contact) |
| `created_at` / `updated_at` | DATETIME | UTC timestamps |

### `messages`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER | Auto-increment PK |
| `contact_id` | INTEGER | FK → `contacts.id` |
| `message_text` | TEXT | Full message body |
| `message_type` | VARCHAR(10) | `'incoming'` or `'outgoing'` |
| `ai_response` | TEXT | Raw AI response (for outgoing AI messages) |
| `created_at` | DATETIME | UTC timestamp |

### `backend_logs`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER | Auto-increment PK |
| `contact_id` | INTEGER | FK → `contacts.id` (nullable) |
| `user_id` | VARCHAR(36) | FK → `user.id` (nullable) |
| `log_level` | VARCHAR(10) | `INFO`, `ERROR`, `WARNING`, `DEBUG` |
| `log_category` | VARCHAR(50) | `SMS`, `AI_RESPONSE`, `WEBHOOK`, `DATABASE`, `AUTH` |
| `action` | VARCHAR(100) | Specific action label (e.g. `SMS_RECEIVED`) |
| `description` | TEXT | Human-readable description |
| `phone_number` | VARCHAR(20) | Involved phone number |
| `thread_id` | VARCHAR(100) | OpenAI thread ID |
| `request_data` | TEXT | JSON-encoded request payload (10 KB cap) |
| `response_data` | TEXT | JSON-encoded response payload (10 KB cap) |
| `error_details` | TEXT | Error message / traceback (5 KB cap) |
| `duration_ms` | INTEGER | Operation duration in milliseconds |
| `ip_address` | VARCHAR(45) | Client IP (IPv4/IPv6) |
| `user_agent` | VARCHAR(500) | Browser/client user-agent |
| `created_at` | DATETIME | UTC timestamp |

---

## 6. Backend Architecture

### Application Factory Pattern

`app.py` uses the Flask application factory (`create_app()`) to:

1. Configure `SQLALCHEMY_DATABASE_URI` — preferring Neon's connection pooler endpoint
2. Set connection pool parameters (`pool_size=10`, `max_overflow=20`, `pool_recycle=3600`, `pool_pre_ping=True`)
3. Register all seven Flask Blueprints
4. Attach SQLAlchemy models to the `app` object so Blueprints can access them via `current_app.Model`
5. Configure a catch-all route to serve React's `index.html` for any unmatched path (SPA support)

### Blueprint Map

```
Blueprint              Prefix              Auth Required
─────────────────────────────────────────────────────
auth_bp                /api/auth/          No
user_bp                /api/user/          Yes (JWT)
settings_bp            /api/settings/      Yes (JWT)
dashboard_bp           /api/dashboard/     Yes (JWT)
sms_bp                 /api/sms/           Mixed*
egt_widget_message_bp  /api/egt_widget_message  No
logs_bp                /api/logs/          Yes (JWT)
```

> *`/api/sms/webhook` is public (called by Twilio); all other SMS routes require JWT.

### Database Connection Resilience

The `with_db_retry` decorator wraps critical database operations with up to 3 retry attempts, exponential back-off, and connection pool disposal between attempts. It handles `DisconnectionError` and `OperationalError` from SQLAlchemy, which covers transient Neon serverless cold-starts.

---

## 7. Frontend Architecture

### Routing & Auth Guard

`App.jsx` uses React Router DOM v7. Authentication state is bootstrapped from `localStorage.token` on mount. All protected routes redirect to `/login` if no token is present.

```
/          → redirect to /login
/login     → Login page
/signup    → Signup page
/dashboard → Dashboard (protected)
/responses → Responses / Chat (protected)
/settings  → Settings (protected)
```

### Data Fetching Strategy

TanStack Query v5 manages all server state:

| Setting | Value | Effect |
|---|---|---|
| `staleTime` | 5 000 ms | Cache considered fresh for 5 s |
| `refetchInterval` | 15 000 ms | Auto-poll every 15 s |
| `refetchOnWindowFocus` | true | Refetches on browser tab focus |
| `refetchOnReconnect` | true | Refetches on network reconnection |

This creates a near-real-time polling layer on top of the WebSocket push layer.

### Real-Time Layer

`Responses` page opens a Socket.IO connection and subscribes to:

- `new-message` — fires when an inbound or AI outbound message is saved
- The room key is either the phone number (SMS contacts) or `thread_id` (widget contacts)

On receipt, the UI merges the new message into the React Query cache, providing an immediate live update without a full refetch.

### Design System

- **Color palette:** Pure black (`#000000`) backgrounds, dark red accents (`#cc0000`, `#ff0000`)
- **Header:** 50px fixed, single row — logo left, logout right
- **Buttons:** Pill-shaped, border `1px solid #cc0000`, background `#2a0000`
- **Loaders:** 3-dot pulsing wave animation (0 ms / 200 ms / 400 ms delays)
- **Typography:** Condensed, reduced letter-spacing for a professional gaming aesthetic

---

## 8. Inbound SMS Message Flow

This is the critical path. Every inbound customer SMS travels through these stages:

```
Customer sends SMS
        │
        ▼
┌──────────────────┐
│  Twilio Webhook  │   POST /api/sms/webhook
│  (From, Body,    │   Returns <Response></Response> immediately
│   To, MessageSid)│   (Twilio requires fast ack)
└────────┬─────────┘
         │  1. Log webhook receipt
         │  2. Find or create Contact (phone number matching)
         │  3. Save incoming message to DB immediately
         │  4. Acquire queue_lock
         ▼
┌──────────────────────────────────────────────┐
│  Message Queue (in-memory defaultdict)        │
│                                              │
│  contact_timers[contact_id] = Timer(30s)     │
│  message_queue[contact_id].append(message)   │
│                                              │
│  If timer already running: just append       │
│  If no timer: start new 30-second timer      │
└──────────────────┬───────────────────────────┘
                   │
            (30 seconds pass)
                   │
                   ▼
┌──────────────────────────────────────────────┐
│  process_queued_messages()                   │
│  (runs in background thread)                 │
│                                              │
│  1. Drain queue for this contact             │
│  2. Concatenate all message bodies           │
│  3. get_or_create_thread_id(contact)         │
│     ├─ Contact has thread_id? → reuse        │
│     └─ No thread_id?                         │
│        POST /thread (up to 5 retries,        │
│        exponential back-off: 2s/4s/8s/16s)  │
│  4. get_ai_response(thread_id, combined_msg) │
│     POST /chat (30s timeout)                 │
│  5. break_text_into_chunks(response, 490)    │
│  6. For each chunk:                          │
│     ├─ Save outgoing Message to DB           │
│     ├─ POST to Twilio Messages API           │
│     └─ time.sleep(2) anti-rate-limit delay   │
│  7. Commit all outgoing records to DB        │
└──────────────────────────────────────────────┘
         │
         ▼
  AI response delivered to customer via SMS
  Socket.IO event emitted to dashboard UI
```

### Phone Number Matching Logic

The `find_contact_by_phone()` function applies four-tier matching in priority order:

1. **Exact match** — raw string equality
2. **Normalized match** — digits-only comparison
3. **Suffix match** — last 10 digits (handles US country code prefix variations)
4. **Thread ID match** — fallback for widget contacts

If multiple contacts match, the one with the most recent `updated_at` timestamp is used.

---

## 9. AI Integration

The platform integrates with an external OpenAI-powered assistant service hosted at:

```
https://extreme-game-truck-graelonbrown.replit.app
```

### Endpoints Used

| Endpoint | Method | Purpose | Timeout |
|---|---|---|---|
| `/thread` | POST | Create a new conversation thread | 15 s |
| `/chat` | POST | Send message, receive AI response | 30 s |

### Thread Lifecycle

Each contact has exactly one `thread_id` stored in the `contacts` table. This ensures the AI assistant maintains full conversation context across all SMS sessions with that customer.

- **New contact:** `thread_id` is `NULL` → system calls `POST /thread` → stores returned `thread_id` → retained for all future messages
- **Existing contact:** `thread_id` is reused directly, no API call needed

### Retry Strategy for Thread Creation

```
Attempt 1: immediate
Attempt 2: wait 2s  (2^1 × initial_delay)
Attempt 3: wait 4s  (2^2 × initial_delay)
Attempt 4: wait 8s  (2^3 × initial_delay)
Attempt 5: wait 16s (2^4 × initial_delay)
```

If all 5 attempts fail, a `THREAD_CREATION_CRITICAL_FAILURE` log is written and no AI response is sent. The incoming message is still saved to the database.

### Widget Channel

The `/api/egt_widget_message` endpoint handles messages from an embedded web chat widget. Unlike the SMS channel, both the customer message and AI response are submitted together in a single API call (the AI processing happens inside the widget, not in this backend). The backend stores both messages and emits Socket.IO events to the dashboard.

---

## 10. Real-Time Communication (WebSockets)

Flask-SocketIO powers the WebSocket layer, sharing the same port as the HTTP server.

### Event: `new-message`

**Emitted by:** `sms_bp` (after AI response is delivered) and `egt_widget_message_bp` (on widget message save)

**Payload:**
```json
{
  "phone": "<phone_number_or_thread_id>",
  "message": {
    "id": 42,
    "text": "Hi, when is the truck available?",
    "type": "incoming",
    "timestamp": "2026-04-16T14:30:00"
  }
}
```

**Room:** Clients join a room keyed by the contact's phone number or `thread_id`.

The frontend `Responses` page subscribes to `new-message` and injects the payload directly into the TanStack Query cache using `queryClient.setQueryData()`, making the update instantaneous without a network round-trip.

---

## 11. Authentication & Security

### JWT Authentication

- **Algorithm:** HS256
- **Secret key:** Stored in `app.config['SECRET_KEY']`
- **Expiry:** 24 hours from issue
- **Transport:** `Authorization: Bearer <token>` header
- **Storage (client):** `localStorage`

### Token Validation

Each protected Blueprint implements its own `token_required` decorator (copy of the same logic). This is by design to avoid circular imports between Blueprints. A refactor to a shared `decorators.py` module would be a clean improvement.

### Password Hashing

Registration uses Werkzeug's `generate_password_hash` with `pbkdf2:sha256`. Login uses `check_password_hash` with constant-time comparison to prevent timing attacks.

### CORS Policy

Currently set to `origins="*"` for development flexibility. For production hardening, this should be narrowed to the specific deployment domain.

---

## 12. Logging & Observability

The platform implements a two-layer logging strategy:

### Layer 1 — Console Logging

Python's `logging` module writes INFO-level messages to stdout. Available in the Replit workflow console and deployment logs.

### Layer 2 — Database Logging (Structured)

All significant events are written to `backend_logs` via `logger_utils.py`. Each log entry captures:

- Category (`SMS`, `AI_RESPONSE`, `WEBHOOK`, `DATABASE`, `AUTH`)
- Action label (`SMS_RECEIVED`, `AI_REQUEST_SENT`, `THREAD_CREATED_SUCCESS`, etc.)
- Duration in milliseconds
- Associated contact, user, thread, and phone number
- Request/response payloads (truncated to 10 KB)
- Error details (truncated to 5 KB)
- IP address and user-agent

### Log Categories Reference

| Category | When Used |
|---|---|
| `SMS` | Inbound/outbound SMS events |
| `AI_RESPONSE` | Thread creation, AI requests, AI responses |
| `WEBHOOK` | Twilio webhook receipt and validation |
| `DATABASE` | Contact creation, thread_id updates |
| `AUTH` | Login and logout events |

### Log Retrieval API

```
GET /api/logs
  ?contact_id=<int>
  &category=<SMS|AI_RESPONSE|WEBHOOK|DATABASE|AUTH>
  &level=<INFO|ERROR|WARNING|DEBUG>
  &phone_number=<str>
  &days=<int>        (default: 7)
  &limit=<int>       (default: 100)
```

---

## 13. API Reference

### Authentication

```
POST /api/auth/login
Body: { "email": "...", "password": "..." }
Response: { "token": "...", "user": { "id", "fullName", "email" } }

POST /api/auth/register
Body: { "fullName", "email", "password", "companyName" }
Response: { "message": "Registration successful!", "verified": true }

POST /api/auth/logout
Body: { "user_id": "..." }
Response: { "success": true }
```

### Dashboard

```
GET /api/dashboard/stats          (JWT required)
Response: {
  "totalContacts": 42,
  "totalMessages": 318,
  "topContacts": [
    { "name", "phone", "messageCount", "lastMessage" }
  ]
}
Cache-Control: public, max-age=30
```

### SMS

```
POST|GET /api/sms/webhook         (public — Twilio-facing)
  Twilio POSTs: From, Body, To, MessageSid
  Response: <Response></Response>  (TwiML empty response)

GET  /api/messages                (JWT required)
GET  /api/contacts                (JWT required)
POST /api/sms/send                (JWT required)
  Body: { "to": "+1...", "message": "..." }
```

### Widget

```
POST /api/egt_widget_message      (no auth — internal service)
Body: { "thread_id": "...", "message": "...", "response": "..." }
Response: { "success": true, "data": { ... } }
```

### Logs

```
GET /api/logs                     (JWT required)
GET /api/logs/stats               (JWT required)
```

### Health

```
GET /api/health/db
Response: { "status": "healthy", "message": "..." }
```

---

## 14. Deployment & Infrastructure

### Build & Run

```bash
# start.sh (used by the Server workflow)
npm run build                     # Vite compiles React to dist/
# Cache-busting: renames assets with Unix timestamp
python app.py                     # Flask serves dist/ and API on same port
```

### Port Strategy

| Environment | PORT | Source |
|---|---|---|
| Development | 5000 | Hardcoded fallback in `app.py` |
| Production | Dynamic | `PORT` environment variable set by Replit |

```python
port = int(os.environ.get('PORT', 5000))
app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
```

### Deployment Target

- **Type:** Autoscale (stateless, horizontally scalable)
- **Build command:** `npm run build`
- **Run command:** `python3 app.py`

> ⚠️ **Important for scaling:** The message queue (`message_queue`, `contact_timers`) is stored in-process Python memory. If multiple instances run simultaneously, queue state is not shared. For true horizontal scaling, replace with Redis-backed queuing (Celery + Redis or RQ).

### Database

- **Provider:** Neon (serverless PostgreSQL)
- **Connection:** Neon pooler endpoint (`-pooler.us-east-2`) for lower connection overhead
- **Pool config:** size=10, max_overflow=20, recycle=3600s, pre_ping=True, TCP keepalives

---

## 15. Configuration & Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | Optional | Full PostgreSQL connection string (overrides individual PG vars) |
| `PGUSER` | Yes (if no DATABASE_URL) | PostgreSQL username |
| `PGPASSWORD` | Yes (if no DATABASE_URL) | PostgreSQL password |
| `PGHOST` | Yes (if no DATABASE_URL) | PostgreSQL host |
| `PGPORT` | Yes (if no DATABASE_URL) | PostgreSQL port |
| `PGDATABASE` | Yes (if no DATABASE_URL) | PostgreSQL database name |
| `PORT` | Production only | HTTP port (provided by Replit deployment) |

Twilio credentials (`account_sid`, `account_token`, `sms_number`) are stored **per user** in the `user_settings` table — not as environment variables. This allows multiple users with different Twilio accounts to share one deployment.

---

## 16. Known Delays & Performance Characteristics

| Stage | Typical Latency | Notes |
|---|---|---|
| Twilio webhook receipt | < 1 s | Twilio delivers within 1 s of customer sending |
| Webhook handler → DB save | < 100 ms | Immediate; returns TwiML ack |
| **Message queue wait** | **30 seconds** | Intentional batching delay |
| Thread creation (cached) | 0 ms | Existing thread_id reused |
| Thread creation (new contact) | 1–5 s | POST /thread API call |
| AI response generation | 5–30 s | Depends on OpenAI load |
| Twilio SMS delivery | 1–5 s | Per chunk; 2 s sleep between chunks |
| **Total end-to-end (typical)** | **~40–70 seconds** | Queue wait dominates |

### Trade-off: Why 30 Seconds?

The 30-second queue window was chosen to handle customers who send their message in multiple rapid SMS segments (e.g., "Hi!" → "I want to book the game truck for Saturday" → "My son's birthday is the 20th"). Batching gives the AI the full context before responding.

**To reduce latency:** The `threading.Timer(30.0, ...)` value in `backend/sms.py:511` can be reduced. A value of `5–10` seconds is a reasonable balance between responsiveness and batching.

---

## 17. Development Workflow

### Initial Setup

```bash
# Install Python dependencies
pip install flask flask-sqlalchemy flask-cors flask-socketio pyjwt requests psycopg2-binary

# Install Node dependencies
npm install

# Set environment variables (Neon database)
export DATABASE_URL="postgresql://..."

# Start development (separate terminals)
npm run dev        # Vite dev server on :3000 (proxies /api → :5000)
python app.py      # Flask on :5000
```

### Production Build

```bash
bash start.sh
# Runs: npm build → cache-bust → python app.py
```

### Vite Dev Proxy

In development, Vite's proxy (`vite.config.js`) forwards all `/api/*` requests to `localhost:5000`, so the React app never needs to know the Flask port.

### Adding a New API Endpoint

1. Create or open the relevant Blueprint in `backend/`
2. Add route with `@blueprint.route('/api/...')`
3. Apply `@token_required` if auth is needed
4. Write to `backend_logs` via `logger_utils.log_backend_activity()`
5. Register the Blueprint in `app.py → create_app()` if it's a new file

---

## 18. Engineering Decisions & Trade-offs

| Decision | Rationale | Alternative |
|---|---|---|
| **Flask over FastAPI** | Mature ecosystem, simpler deployment, sufficient for current request volume | FastAPI for async I/O at scale |
| **In-process message queue** | Zero infrastructure overhead; simple threading model | Redis + Celery for multi-instance deployments |
| **30-second batch window** | Captures multi-part SMS conversations as a single AI request | Configurable per-user window, or semantic "end of thought" detection |
| **JWT in localStorage** | Simplicity for SPA; acceptable for internal tooling | HttpOnly cookie for public-facing apps |
| **Per-user Twilio credentials** | One deployment serves multiple Twilio accounts | Shared Twilio sub-accounts with routing rules |
| **Neon pooler endpoint** | Serverless PostgreSQL with connection pooling built-in | RDS with pgBouncer |
| **CORS origins: `*`** | Developer convenience | Restrict to deployment domain in production |
| **Monolith (Flask serves SPA)** | Single port, single process, simple deployment | Separate CDN for frontend assets |
| **Thread ID per contact** | Persistent AI memory per customer across sessions | Session-based threads (reset per conversation) |

---

*Extreme Game Truck Customer Communication Platform — Confidential Engineering Documentation*  
*Built on Replit · Flask · React · Twilio · OpenAI*
