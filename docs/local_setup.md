# Run Kitch locally

Local Kitch uses SQLite for structured state and ADK's
`InMemoryMemoryService` for household memory. SQLite survives restarts; agent
memory does not. This path does not require Supabase, Google Cloud, or Memory
Bank.

## Prerequisites

- Git
- Python 3.12 or newer
- Node.js and npm
- A Gemini API key from Google AI Studio

## Setup

```bash
git clone <your-kitch-repository-url>
cd diet_planner
cp backend/.env.local.example backend/.env.local
```

Edit `backend/.env.local` and replace `GOOGLE_API_KEY`. Then run:

```bash
python3.12 scripts/kitch.py setup
python3.12 scripts/kitch.py start
```

On Windows use `py -3.12`. The setup command creates the virtual environment
and installs backend and frontend dependencies. The start command initializes
or migrates SQLite and starts FastAPI and Next.js.

Open `http://localhost:3000`. Enter every household-member name on first use.
The number of names becomes the household size, the first name is the default
active member, and the browser's system timezone is saved automatically.

The installation starts without meal plans, pantry stock, recipes, grocery
items, nutrition entries, provider connections, or orders.

## Local files

- `.kitch/kitch.sqlite3` contains structured state.
- `.kitch/provider-credentials.key` encrypts delegated provider tokens.
- `backend/.env.local` contains the Gemini key and local configuration.

These files are ignored by Git. Back up the database and provider key together
if a connected provider must remain usable after moving the installation.

## Swiggy Instamart

Open Groceries, choose Swiggy Instamart, and click Connect. Kitch dynamically
registers its localhost OAuth client. Swiggy handles the phone/OTP interaction.
The exact callback is:

`http://localhost:8000/api/grocery/providers/swiggy_instamart/oauth/callback`

Kitch uses the real Instamart catalogue, addresses, cart and payment data. No
local provider catalogue or cart fixture exists. See
[`swiggy_setup.md`](swiggy_setup.md) for hosted callbacks and token behavior.

## Health and troubleshooting

The start command checks ports 3000 and 8000 and waits for backend liveness.
After onboarding, readiness is available at:

```bash
curl http://localhost:8000/api/health/live
curl http://localhost:8000/api/health/ready
```

If startup is intentionally manual, run FastAPI from `backend/` on port 8000
and Next.js from `frontend/` on port 3000 with
`NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`.
