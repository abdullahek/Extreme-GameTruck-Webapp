<div align="center">

# 🎮 Extreme Game Truck
### AI-Powered Customer Communication Platform

![Platform](https://img.shields.io/badge/Platform-Web-blue?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![Flask](https://img.shields.io/badge/Flask-3.1-000000?style=for-the-badge&logo=flask&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Neon-336791?style=for-the-badge&logo=postgresql&logoColor=white)
![Twilio](https://img.shields.io/badge/Twilio-SMS-F22F46?style=for-the-badge&logo=twilio&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-AI%20Responses-412991?style=for-the-badge&logo=openai&logoColor=white)

> A full-stack real-time SMS communication dashboard with AI-powered auto-responses,  
> built for the mobile gaming entertainment industry.

---

[Features](#-features) • [Architecture](#-architecture) • [Tech Stack](#-tech-stack) • [Getting Started](#-getting-started) • [API Reference](#-api-reference) • [Deployment](#-deployment) • [Docs](#-documentation)

</div>

---

## ✨ Features

<table>
<tr>
<td width="50%">

### 📱 SMS Inbox
Receive, display, and reply to customer messages via Twilio in real time — all in one dashboard.

### 🤖 AI Auto-Responses
OpenAI-powered context-aware replies generated and sent automatically to every customer.

### 💬 Smart Message Batching
30-second queue intelligently groups rapid multi-part messages before sending one AI request.

### ⚡ Live Real-Time UI
Socket.IO WebSockets push new messages to the dashboard the instant they arrive.

</td>
<td width="50%">

### 🌐 Web Widget Channel
Accept conversations from embedded chat widgets alongside the SMS channel.

### 📊 Analytics Dashboard
Total contacts, total messages, and top conversations at a glance.

### 📋 Full Audit Logging
Every SMS, AI call, webhook, and auth event stored in the database with duration metrics.

### 🔐 Secure JWT Auth
24-hour tokens, per-user Twilio credential isolation, and pbkdf2:sha256 password hashing.

</td>
</tr>
</table>

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT BROWSER                              │
│                                                                     │
│   React 18 + Vite 5  ·  TanStack Query (polling)  ·  Socket.IO     │
│   ┌──────────┐  ┌─────────────┐  ┌──────────┐  ┌───────────────┐   │
│   │Dashboard │  │ Responses   │  │ Settings │  │  Login/Signup │   │
│   │ (Stats)  │  │ (Chat UI)   │  │ (Twilio) │  │               │   │
│   └──────────┘  └─────────────┘  └──────────┘  └───────────────┘   │
└──────────────────────────┬──────────────────────────────────────────┘
                           │  HTTP REST  /  WebSocket
┌──────────────────────────▼──────────────────────────────────────────┐
│              FLASK BACKEND  (port 5000 dev / $PORT prod)            │
│                                                                     │
│  ┌─────────┐ ┌─────────┐ ┌───────────┐ ┌──────────┐ ┌──────────┐   │
│  │ auth_bp │ │  sms_bp │ │dashboard_ │ │ logs_bp  │ │ widget_  │   │
│  │/api/auth│ │/api/sms │ │    bp     │ │/api/logs │ │  bp      │   │
│  └─────────┘ └────┬────┘ └───────────┘ └──────────┘ └──────────┘   │
│                   │                                                 │
│        30-second message queue  (threading.Timer per contact)       │
│        Flask-SQLAlchemy  ·  Flask-SocketIO                          │
└───────────┬────────────────────┬────────────────────────────────────┘
            │                    │
  ┌─────────▼──────┐   ┌─────────▼──────┐   ┌──────────────────────┐
  │  PostgreSQL    │   │    Twilio       │   │  OpenAI AI Service   │
  │  (Neon pooled) │   │    SMS API      │   │  POST /thread        │
  └────────────────┘   └─────────────────┘   │  POST /chat          │
                                              └──────────────────────┘
```

---

## 🔄 Inbound SMS Message Flow

```
 Customer sends SMS
         │
         ▼
 ┌───────────────────┐
 │  Twilio Webhook   │  POST /api/sms/webhook
 │  Instant TwiML    │  Saves message to DB immediately
 │  acknowledgement  │  Returns in < 100ms
 └────────┬──────────┘
          │
          ▼
 ┌──────────────────────────────────────┐
 │  In-Memory Message Queue             │
 │                                      │
 │  threading.Timer(30s) per contact    │
 │  Batches rapid multi-part messages   │
 │  Timer resets on each new message    │
 └──────────────────┬───────────────────┘
                    │  (30 seconds of silence)
                    ▼
 ┌──────────────────────────────────────┐
 │  AI Processing Pipeline              │
 │                                      │
 │  1. Drain & combine all queued msgs  │
 │  2. Get / create OpenAI thread_id    │
 │  3. POST combined text  →  /chat     │
 │  4. Break response into 490-char     │
 │     chunks (SMS limit)               │
 │  5. Send each chunk via Twilio API   │
 │  6. Emit Socket.IO event to UI       │
 │  7. Commit all records to DB         │
 └──────────────────────────────────────┘
          │
          ▼
 AI reply delivered to customer's phone
 Dashboard updates in real time
```

---

## 📁 Project Structure

```
extreme-game-truck/
│
├── app.py                        # Flask application factory, ORM models, entry point
├── start.sh                      # Build: Vite → cache-bust assets → start Flask
├── vite.config.js                # Dev server (port 3000, proxies /api → :5000)
├── package.json                  # React, Vite, TanStack Query, Socket.IO
├── pyproject.toml                # Python dependencies
│
├── backend/                      # Flask Blueprints (domain-driven)
│   ├── auth.py                   # /api/auth  — login, register, logout
│   ├── user.py                   # /api/user  — profile management
│   ├── settings.py               # /api/settings — Twilio credentials
│   ├── dashboard.py              # /api/dashboard — aggregated stats
│   ├── sms.py                    # /api/sms  — webhook, queue, AI flow
│   ├── egt_widget_message.py     # /api/egt_widget_message — widget channel
│   ├── logs.py                   # /api/logs — structured log retrieval
│   └── logger_utils.py           # Shared logging helpers
│
├── src/                          # React frontend source
│   ├── App.jsx                   # Router, QueryClientProvider, auth guard
│   ├── pages/
│   │   ├── Login/                # Authentication
│   │   ├── Signup/               # Registration
│   │   ├── Dashboard/            # Stats overview
│   │   ├── Responses/            # Live SMS conversations
│   │   └── Settings/             # Twilio configuration
│   └── components/
│       └── Header/               # Fixed 50px navigation bar
│
├── dist/                         # Vite production build (auto-generated)
├── DEVELOPER_GUIDE.md            # Full architecture & engineering docs
└── README.md                     # This file
```

---

## 🛠️ Tech Stack

### Backend
| Technology | Version | Purpose |
|---|---|---|
| Python | 3.x | Runtime |
| Flask | 3.1 | HTTP web framework |
| Flask-SQLAlchemy | latest | ORM & connection pooling |
| Flask-SocketIO | latest | WebSocket server |
| Flask-CORS | latest | Cross-origin resource sharing |
| PyJWT | latest | JWT token creation & validation |
| Werkzeug | latest | Password hashing (pbkdf2:sha256) |
| Requests | latest | HTTP client for Twilio + AI APIs |

### Frontend
| Technology | Version | Purpose |
|---|---|---|
| React | 18.2 | UI component framework |
| Vite | 5.0 | Build tool & dev server |
| React Router DOM | 7 | Client-side routing |
| TanStack Query | 5 | Server state, caching & auto-polling |
| Socket.IO Client | 4.8 | Real-time WebSocket updates |

### Infrastructure & Services
| Service | Purpose |
|---|---|
| PostgreSQL via Neon | Primary database with serverless connection pooler |
| Twilio | Inbound & outbound SMS gateway |
| OpenAI (external service) | AI conversation thread & response generation |
| Replit Autoscale | Hosting and deployment target |

---

## 🗄️ Database Schema

```sql
-- User accounts
user (id UUID, full_name, email UNIQUE, company_name, password_hash, is_verified, created_at)

-- Per-user Twilio credentials
user_settings (id, user_id FK, account_sid, account_token, sms_number, is_number_verified)

-- Customer records
contacts (id, user_id FK, phone_number, name, thread_id, created_at, updated_at)
--   phone_number: E.164 for SMS  |  'widget_<suffix>' for web widget contacts
--   thread_id: OpenAI thread — persisted per contact for continuous AI memory

-- Full message history
messages (id, contact_id FK, message_text, message_type, ai_response, created_at)
--   message_type: 'incoming' | 'outgoing'

-- Structured audit log
backend_logs (id, contact_id, user_id, log_level, log_category, action,
              description, phone_number, thread_id, request_data, response_data,
              error_details, duration_ms, ip_address, user_agent, created_at)
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.x
- Node.js 18+
- PostgreSQL database (Neon recommended)
- Twilio account with a purchased phone number

### 1. Clone the Repository

```bash
git clone https://github.com/abdullahek/Extreme-GameTruck-Webapp.git
cd Extreme-GameTruck-Webapp
```

### 2. Install Dependencies

```bash
# Python
pip install flask flask-sqlalchemy flask-cors flask-socketio pyjwt requests psycopg2-binary werkzeug

# Node
npm install
```

### 3. Set Environment Variables

```bash
export DATABASE_URL="postgresql://user:password@host:port/dbname"
# OR set individual Postgres variables:
export PGUSER=...
export PGPASSWORD=...
export PGHOST=...
export PGPORT=5432
export PGDATABASE=...
```

> **Twilio credentials** (Account SID, Auth Token, phone number) are configured **per user** inside the app's Settings page — no environment variable needed.

### 4. Run in Development

```bash
# Terminal 1 — Flask API
python app.py               # runs on :5000

# Terminal 2 — React dev server
npm run dev                 # runs on :3000, proxies /api → :5000
```

Open **http://localhost:3000**, register an account, and configure your Twilio credentials in Settings.

### 5. Build for Production

```bash
bash start.sh
# 1. npm run build   — compiles React to dist/
# 2. Cache-busts asset filenames with Unix timestamp
# 3. python app.py   — Flask serves dist/ + API on same port
```

---

## 📡 API Reference

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/api/auth/login` | No | Log in, receive JWT |
| `POST` | `/api/auth/register` | No | Create new account |
| `POST` | `/api/auth/logout` | No | Record logout event |
| `GET` | `/api/dashboard/stats` | JWT | Total contacts, messages, top contacts |
| `GET` | `/api/messages` | JWT | All conversations with full history |
| `GET` | `/api/contacts` | JWT | All contacts for current user |
| `POST` | `/api/sms/send` | JWT | Send a manual SMS |
| `POST/GET` | `/api/sms/webhook` | Public | Twilio inbound SMS webhook |
| `POST` | `/api/egt_widget_message` | Public | Web widget message handler |
| `GET` | `/api/logs` | JWT | Filtered audit log retrieval |
| `GET` | `/api/logs/stats` | JWT | Log stats by category & level |
| `GET` | `/api/health/db` | Public | Database health check |

### Query Parameters for `/api/logs`
```
?contact_id=<int>
&category=SMS|AI_RESPONSE|WEBHOOK|DATABASE|AUTH
&level=INFO|ERROR|WARNING|DEBUG
&phone_number=<str>
&days=<int>          (default: 7)
&limit=<int>         (default: 100)
```

---

## ⚙️ Twilio Webhook Setup

In your Twilio console, set the inbound webhook for your phone number to:

```
URL:    https://your-deployment.replit.app/api/sms/webhook
Method: HTTP POST
```

---

## 🧠 AI Integration

The platform uses an external OpenAI-powered assistant service:

```
Base: https://extreme-game-truck-graelonbrown.replit.app

POST /thread   →  Creates new conversation thread  (timeout: 15s)
POST /chat     →  Sends message, returns AI reply   (timeout: 30s)
```

**Thread persistence:** Every contact has exactly one `thread_id` stored in the database. The AI retains full conversation history across all sessions with that customer.

**Retry strategy for new threads:**
```
Attempt 1: immediate
Attempt 2: +2s
Attempt 3: +4s
Attempt 4: +8s
Attempt 5: +16s  →  if all fail, logs CRITICAL and skips AI reply
```

---

## 🚢 Deployment

Deployed on **Replit Autoscale** (stateless, horizontally scalable):

| Setting | Value |
|---|---|
| Build command | `npm run build` |
| Run command | `python3 app.py` |
| Port | `$PORT` (env var) with fallback to `5000` |

```python
# Port auto-detection in app.py
port = int(os.environ.get('PORT', 5000))
app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
```

> ⚠️ **Scaling note:** The message queue lives in process memory. For multi-instance deployments, replace with **Redis + Celery**.

---

## 📊 Logging & Observability

All events are captured in `backend_logs` with full context:

| Category | Events |
|---|---|
| `SMS` | Inbound receipt, outbound delivery |
| `AI_RESPONSE` | Thread creation, chat requests/responses, failures |
| `WEBHOOK` | Twilio webhook calls and validation |
| `DATABASE` | Contact creation, thread ID updates |
| `AUTH` | Login and logout events |

Each log entry records: level, category, action label, description, contact/user/phone/thread association, request & response payloads, error details, duration in milliseconds, IP address, and user-agent.

---

## 📈 Performance

| Stage | Latency |
|---|---|
| Twilio webhook → DB save | < 100 ms |
| Message queue batching window | 30 s |
| AI thread creation (new contact) | 1 – 5 s |
| AI response generation | 5 – 30 s |
| SMS chunk delivery (per chunk) | 1 – 5 s + 2s delay |
| **Total end-to-end (typical)** | **~40 – 70 s** |

The 30-second queue window is configurable in `backend/sms.py` — reducing it to 5–10 seconds significantly improves response time while still batching most rapid-fire messages.

---

## 📄 Documentation

Full architecture documentation, detailed API reference, engineering decisions, and database schema:

**[📘 DEVELOPER_GUIDE.md](./DEVELOPER_GUIDE.md)**

---

## 🎨 Design System

- **Background:** Pure black `#000000`
- **Primary accent:** Dark red `#cc0000` / `#ff0000`
- **Header:** Fixed 50px single-row — logo left, logout right
- **Buttons:** Pill-shaped, `border: 1px solid #cc0000`, `background: #2a0000`
- **Loader:** 3-dot pulsing wave (0ms / 200ms / 400ms stagger)
- **Theme:** Professional gaming aesthetic — compact, high-contrast, minimal

---

<div align="center">

## 👨‍💻 Author

**Abdullah**  
[github.com/abdullahek](https://github.com/abdullahek)

---

**Extreme Game Truck** — Bringing the Ultimate Gaming Experience to Your Doorstep 🎮🚚

*Flask · React · Twilio · OpenAI · PostgreSQL · Socket.IO*

</div>
