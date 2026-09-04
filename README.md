# Razorpay Nexus Commerce — Agentic Commerce & AP2 Protocol

**Hackathon Track 1: AI Growth & Agentic Commerce**

---

## Pitch Video

**Video Link:** https://youtu.be/mOHPlKLqXZw

## Live Demo

**Live URL:** https://razorpay-nexus-commerce.vercel.app/

**Backend API Docs:** https://razorpay-nexus-backend.onrender.com/docs

---

## Overview

This project is the infrastructure layer that lets AI agents shop, negotiate, pay, and prove authenticity safely, without human clicks.

Today, AI agents can understand what you want to buy, but they cannot safely complete the purchase on your behalf. There is no guardrail stopping an AI from hallucinating a fake price, ordering 100 units instead of 1, shipping to an unverified address, or spending far beyond your intended limit. Every agentic commerce flow today still ends with a human clicking "Confirm Payment." That defeats the entire purpose of automation.

The core of this project is a 6-layer Policy Gate that stands between the AI agent and Razorpay. Every single order, regardless of whether it comes from a human chatting or an autonomous buyer bot, must pass through this gate before a single rupee moves. It checks stock availability, enforces a 5-unit quantity ceiling, caps orders at Rs. 10,000, and verifies that the delivery address matches the customer's saved profile, all in real time.

One of the most critical problems this project solves is AI price hallucination. When an LLM processes an order, it may understand a price that is slightly wrong or entirely fabricated. This system completely ignores whatever price the AI suggests and always fetches the ground-truth price directly from the catalog database before payment. The LLM can never corrupt the transaction amount.

The project also solves cross-merchant interoperability via an AP2 Protocol implementation that exposes two independent merchant catalogs with identical schemas, so an autonomous AI buyer agent can query both stores, compare prices, and negotiate in a single flow without any custom integration per merchant.

Finally, every completed order generates a cryptographic verifiable receipt, an HMAC-SHA256 signature computed over the canonical order fields. If anyone tampers with the stored price or quantity even by Rs. 1, the hash recomputed at verification time will instantly mismatch, triggering a security alert.

---

## Key Features

- **Conversational In-App Checkout** — Natural language shopping powered by NVIDIA NIM (Llama 3.1)
- **6-Layer Deterministic Policy Gate** — Price integrity, stock check, quantity ceiling, address whitelist, order value cap, and bounded discount negotiation
- **Autonomous AI Buyer Agent** — External bot that shops across two merchants, negotiates, signs an AP2 mandate, and pays with zero human input
- **AP2 (Agent Payments Protocol) Alignment** — Structured, signed purchase mandates for machine-to-machine commerce
- **HMAC-SHA256 Verifiable Receipts** — Cryptographic tamper detection on every order
- **Multi-Merchant Interoperability** — Two standardized catalogs: Apex Outfitters and Urban Trail Co.
- **Full Audit Trail** — Every action logged to MongoDB `audit_logs` collection in real time

---

## Demo Data Location

All seed and demo data is hardcoded directly in the backend and loaded into MongoDB Atlas (or the in-memory fallback) on first startup.

| Data | File Location |
|---|---|
| Merchant A products (Apex Outfitters, 8 items) | `backend/app/db.py` — `INITIAL_PRODUCTS_MERCHANT_A` |
| Merchant B products (Urban Trail Co., 4 items) | `backend/app/db.py` — `INITIAL_PRODUCTS_MERCHANT_B` |
| Pre-saved customer addresses (Rahul Sharma, 2 addresses) | `backend/app/db.py` — `SAVED_CUSTOMER_ADDRESSES` |
| Merchant policy rules (max quantity, discount caps, order limits) | `backend/app/config.py` — `MERCHANTS` dict |

The data is not fetched from any external source. It is seeded once into the database at startup and persists across sessions. To reset it to original values, call `POST /api/reset-demo`.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3, FastAPI, Uvicorn |
| AI / LLM | NVIDIA NIM — `meta/llama-3.1-8b-instruct` via OpenAI-compatible SDK |
| Database | MongoDB Atlas (cloud) with automatic in-memory fallback |
| Payments | Razorpay Python SDK (Test Mode) |
| Security | HMAC-SHA256 cryptographic receipt signing |
| Frontend | React 19, Vite 8, Tailwind CSS v4, Lucide Icons |
| Protocol | Google AP2 (Agent Payments Protocol) alignment |
| Deployment | Render (Docker) for backend, Vercel for frontend |

---

## Project Structure

```
Razorpay/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app, all API routes
│   │   ├── agent.py         # Conversational AI agent loop (NVIDIA NIM)
│   │   ├── policy_gate.py   # 6-layer safety policy engine
│   │   ├── payments.py      # Razorpay SDK integration
│   │   ├── receipts.py      # HMAC-SHA256 cryptographic receipts
│   │   ├── db.py            # MongoDB Atlas + in-memory DB + DEMO DATA
│   │   ├── config.py        # Env config + MERCHANT POLICY RULES
│   │   └── schemas.py       # Pydantic models
│   ├── ai_buyer_agent.py    # Standalone autonomous AI buyer script
│   ├── test_backend.py      # Full automated test suite
│   ├── run_backend.py       # Backend entry point (local dev)
│   ├── Dockerfile           # Production Docker image (used by Render)
│   ├── requirements.txt
│   └── .env.template        # Environment variable template
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # Full React UI (all 5 tabs)
│   │   └── index.css        # Global styles
│   ├── vercel.json          # Vercel routing and API proxy config
│   ├── package.json
│   └── vite.config.js       # Vite config with API proxy
├── docker-compose.yml
└── README.md
```

---

## Setup and Running

### Prerequisites

- Python 3.10+
- Node.js 18+
- Git

---

### Option 1 — Local Setup

#### Step 1: Clone the Repository

```bash
git clone https://github.com/IqraKhanZ/Razorpay---Nexus-Commerce.git
cd Razorpay---Nexus-Commerce
```

#### Step 2: Backend Setup

```bash
cd backend

# Create and activate virtual environment
python -m venv venv

# On Windows
.\venv\Scripts\activate

# On Mac/Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### Step 3: Configure Environment Variables

```bash
# Copy the template
cp .env.template .env

# Open .env and fill in your keys
```

> Note: If any key is left blank, the system automatically falls back to simulation mode. The app will still run and demonstrate all features without real API keys.

#### Step 4: Start the Backend

```bash
python run_backend.py
```

Backend runs at: `http://127.0.0.1:8000`
Interactive API docs at: `http://127.0.0.1:8000/docs`

#### Step 5: Frontend Setup

```bash
# In a new terminal, from project root
cd frontend
npm install
npm run dev
```

Frontend runs at: `http://localhost:5173`

---

#### Step 6: (Optional) Run Backend Tests

```bash
cd backend
python test_backend.py
```

Expected output:
```
Merchant A product found: Apex Torrent Waterproof Shell
Merchant B product found: Urban Shield Waterproof Raincoat
Valid Order: APPROVED
Out of Stock Check: REJECTED with reason 'out_of_stock'
Quantity Ceiling (>5) Check: REJECTED
Order Value Cap (>Rs.10k) Check: REJECTED
Bounded Negotiation: Counter-offered 15.0%
Unrecognized Address Check: REJECTED
Razorpay Order Created
Receipt Cryptographic Verification: AUTHENTIC
Tamper Detection Test: Successfully caught!

ALL BACKEND UNIT & POLICY GATE TESTS PASSED!
```

#### Step 7: (Optional) Run the Standalone AI Buyer Agent

```bash
cd backend
python ai_buyer_agent.py
```

This simulates a fully autonomous outside AI agent completing a purchase with zero human input.

---

### Option 2 — Docker Compose

```bash
# From project root
docker-compose up --build
```

Frontend: `http://localhost:5173`
Backend: `http://localhost:8000`

---

## Demo Scenarios

Open the live URL or `http://localhost:5173` and try these in the Conversational Checkout tab:

| Prompt | What Happens |
|---|---|
| "I want to buy the Apex Torrent Waterproof Shell in size M" | All 6 policy checks pass, Razorpay order created, HMAC receipt generated |
| "Can you check stock and buy the Apex Alpine Pro Shell in size L?" | Stock = 0, Policy Gate rejects, agent suggests Size M alternative |
| "Can I get a 10% discount on the Apex Torrent Shell?" | Discount approved within 15% cap, negotiated price returned |
| "I want to order 20 units of the Apex Torrent Jacket" | Rejected — exceeds 5-unit quantity ceiling |
| "Order the Apex Expedition 8000 Parka" | Rejected — Rs. 14,999 exceeds Rs. 10,000 automated order limit |

Then switch to the AI Buyer Agent tab and click Run Agent Demo to watch the autonomous purchase pipeline execute end-to-end.

---

## Environment Variables Reference

Create a `.env` file inside the `backend/` folder:

```env
# NVIDIA NIM API Key (powers the conversational LLM)
NVIDIA_API_KEY=nvapi-...

# Gemini API Key (optional fallback)
GEMINI_API_KEY=

# MongoDB Atlas Connection String
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/agentic_commerce

# Razorpay Test Mode Credentials
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=...

# HMAC Receipt Signing Secret (can be any strong string)
RECEIPT_SIGNING_KEY=your_secret_signing_key_here

# Server Configuration
PORT=8000
HOST=0.0.0.0
```

> The `.env` file is excluded from version control via `.gitignore`. Never commit real API keys.

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Health check and merchant list |
| GET | `/api/products/search` | Search catalog with filters |
| GET | `/api/products/{merchant_id}/{product_id}` | Get single product |
| POST | `/api/chat` | Conversational AI agent |
| POST | `/api/policy/validate` | Standalone policy gate check |
| POST | `/api/orders/mandate` | Execute AP2 buy mandate |
| GET | `/api/verify/{order_id}` | Cryptographic receipt verification |
| GET | `/api/logs` | Audit trail logs |
| POST | `/api/reset-demo` | Reset all inventory to seed state |

Full interactive documentation: https://razorpay-nexus-backend.onrender.com/docs

---

## Hackathon Track

**Track 1: AI Growth & Agentic Commerce**

This project demonstrates a production-grade architecture for autonomous agentic commerce by combining conversational checkout, a deterministic safety policy engine, the AP2 Agent Payments Protocol, live Razorpay payment processing, and cryptographic receipt verification — all in a single cohesive system.

---

*Built for the Razorpay Hackathon 2026*
