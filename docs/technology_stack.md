# Production Technology Stack & Deployment Blueprint: PlateWise AI

> [!NOTE]
> This document outlines the **Production Technology Stack** for PlateWise AI. In accordance with project requirements, we prioritize **industry-standard free tiers** for hosting, databases, and APIs. We structure the app using a decoupled frontend/backend framework to natively support the Python-based Google Antigravity SDK.

---

## 1. High-Level Architectural Flow

To ensure high performance while leveraging Vercel's hosting features and the Python-only Google Antigravity SDK, we propose a **Split Architecture**:

```mermaid
graph LR
    subgraph Vercel Free Tier
        NextJS[Next.js React Frontend]
    end
    
    subgraph Render / Railway Free Container
        FastAPI[FastAPI Python Backend]
        SDK[Google Antigravity SDK]
        FastAPI <--> SDK
    end
    
    subgraph Database Layer
        Supabase[(Supabase PostgreSQL)]
    end
    
    subgraph External APIs
        Gemini[Google AI Studio Gemini API]
        Blinkit[Blinkit Playwright MCP Server]
        WhatsApp[Twilio WhatsApp Gateway]
    end

    NextJS <-->|REST API / SSE| FastAPI
    FastAPI <-->|SQL Queries| Supabase
    SDK <-->|Multimodal LLM Calls| Gemini
    SDK -->|Pluggable Adapter| Blinkit
    WhatsApp <-->|Webhooks| FastAPI
```

---

## 2. Component Tech Stack & Service Selection

### 🖥️ 1. Frontend & Client Dashboard
*   **Technology**: **Next.js (React) + TypeScript + Vanilla CSS / Glassmorphic UI**.
*   **Why**: Best-in-class framework for Vercel deployment. Provides fast static rendering, built-in routing, serverless API proxies, and optimized bundle sizes.
*   **Hosting**: **Vercel (Hobby Free Tier)**.
    *   *Includes*: Global CDN, SSL certificates, serverless API functions, and Git-integrated deployments.

### ⚙️ 2. Python Agentic Backend
*   **Technology**: **FastAPI + Python 3.11+ + Google Antigravity SDK**.
*   **Why**: The Antigravity SDK is a native Python library (`google-antigravity`). FastAPI is an extremely lightweight, high-performance web framework designed for asynchronous execution, making it the perfect gateway to run Antigravity's async loops.
*   **Hosting**: **Render (Free Web Services)** or **Railway (Developer Plan)**.
    *   *Why*: Vercel serverless functions have a 10–15s timeout on free plans, which is too short for complex agentic loops or vision scans. A lightweight, hosted container on Render or Railway allows the Python process to remain persistent, handling long-lived chat streams, vision file parsing, and MCP operations.

### 💾 3. Persistent Database & Backend-as-a-Service
*   **Technology**: **Supabase (PostgreSQL)**.
*   **Why**: 
    *   **Generous Free Tier**: Includes 500MB database, 1GB file storage, and up to 50,000 active monthly users.
    *   **Postgres Power**: Perfect for relational structures (joining recipes, calendars, pantry inventory lists, and user profiles).
    *   **Built-in Auth**: Standardizes multi-user profile authentication (so Dynamite, Housemate A, and Housemate B can log in securely).

### 🧠 4. Multimodal Generative AI
*   **Technology**: **Google AI Studio (Gemini 2.0 Flash / Gemini 2.5 Flash)**.
*   **Why**:
    *   **Generous Free Tier**: Highly competitive rate limits on the free tier (up to 15 RPM / 1 million tokens/min).
    *   **Gemini Multimodal Native**: Gemini is built from the ground up to handle visual files. Image bytes from fridge snaps and plate logs are logged directly via the Antigravity SDK's native file handler.

### 🛒 5. Grocery Provisioning & Delivery (MCP)
*   **Technology**: **Blinkit Model Context Protocol (MCP) Server** (`hereisSwapnil/blinkit-mcp`).
*   **Mechanism**:
    *   The Blinkit MCP server runs a local **Playwright** browser engine under the hood. 
    *   When the user approves an MCP cart tool call (`export_to_delivery`), the Blinkit Adapter maps the platform-agnostic Intermediary Grocery List items to Blinkit catalog matches, invokes the MCP tool, and automates product searches and cart placement.
    *   UPI payment is finalized manually by the user on the Blinkit application.

### 💬 6. Conversational Chat Channels
*   **WhatsApp API Gateway**: **Twilio (Free sandbox/trial)**.
    *   Routes messages from WhatsApp to our FastAPI `/api/webhook/whatsapp` endpoint.
*   **Telegram Gateway**: **Telegram Bot API (100% Free)**.
    *   Simple, lightweight conversational webhook interfacing directly with our python service.

---

## 3. Production Environment Secret Management

All service integrations are connected securely using standard environment variables:

| Variable Name | Provider Source | Role in System |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | Google AI Studio (Free) | Powers the Antigravity Agent and Subagent reasoning |
| `SUPABASE_DB_URL` | Supabase Settings (Free) | Relational connection string for the database |
| `SUPABASE_ANON_KEY` | Supabase API Keys (Free) | Authenticates frontend database fetches |
| `TELEGRAM_BOT_TOKEN` | BotFather (Free) | Auth token for conversational Telegram bot |
| `TWILIO_AUTH_TOKEN` | Twilio Console (Trial) | Validates incoming WhatsApp webhook signatures |

---

## 4. Why This Configuration Works Best

*   **100% Cost-Free Prototyping**: You can develop, host, and test the entire system without inputting a credit card.
*   **Complete Separation of Concerns**: Next.js is focused on rendering interactive visual charts, planners, and lists, while the FastAPI service focuses on running the Antigravity agentic loops.
*   **Robust Data Integrity**: Relational constraints in PostgreSQL prevent mismatched calendar items or incorrect pantry deductions during concurrent swaps.
