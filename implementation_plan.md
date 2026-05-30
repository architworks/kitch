# Technical Implementation Plan: Kitch (Production-Ready Pure Antigravity SDK)

This plan outlines the technical design, backend fixes, and database integration required to completely transition **Kitch** from hardcoded frontend/backend mock simulations into a fully functional, decoupled production-ready system. 

It addresses and resolves the Python backend agent crashes caused by SDK hallucinations, integrates a live **Supabase** database wrapper, connects real Gemini Multimodal Vision analysis, and wires up the Next.js frontend checkout flows directly to the Python API endpoints.

---

## 1. Technical Architecture & Component Breakdown

We will operate a fully decoupled Next.js frontend and Python FastAPI backend architecture. The agentic core runs strictly on the official `google-antigravity` primitives without LangChain wrappers, while the database layer is backed by a live Supabase instance with active integrations.

```mermaid
graph TD
    subgraph Next.js Frontend (Port 3000)
        WebDash[Web Dashboard]
        ChatArea[Chat & Camera Uploader]
    end
    
    subgraph Python Backend (Port 8000)
        API[FastAPI Gateway with lifespan lifecycle]
        SupabaseClient[Supabase Py Client]
        
        subgraph Google Antigravity SDK Agent
            Coord[Kitch Coordinator Agent]
            Tools[Database & Cart Tools]
            DecideHook[Tool Decide Hook]
            Coord -->|Utilizes| Tools
            Coord -->|Secured by| DecideHook
        end
    end
    
    subgraph Supabase Cloud Database
        DB[(PostgreSQL Tables)]
    end

    WebDash & ChatArea <-->|fetch() calls| API
    API <--> Coord
    Coord <--> SupabaseClient
    SupabaseClient <--> DB
```

---

## 2. User Review Required

> [!IMPORTANT]
> To enable database reading and writing for local testing without setting up complex OAuth authentication tokens first, we will configure Row Level Security (RLS) on the Supabase PostgreSQL tables to allow anonymous operations during local runs, or use the `SUPABASE_KEY` (anon key) with public permissive policies.

---

## 3. Proposed Changes

We will systematically modify the files to implement this robust change.

### Backend Configurations

#### [MODIFY] [core.py](file:///Users/dynamiterdx/Documents/Personal%20Projects/diet_planner/backend/app/agent/core.py)
*   Remove hallucinated `Subagent` imports and `register_subagents` calls.
*   Update `coordinator_agent` to be constructed strictly with `LocalAgentConfig`.
*   Pass the identity, agent tools, policies, and hooks directly through the config object.
*   Implement real database-backed tools: `add_to_pantry`, `log_macros`, `get_pantry_stock`, and `get_macro_diary` connecting the agent's actions to Supabase.

#### [MODIFY] [hooks.py](file:///Users/dynamiterdx/Documents/Personal%20Projects/diet_planner/backend/app/agent/hooks.py)
*   Import correct lifecycle classes and decorators (`pre_tool_call_decide`, `HookResult`) from `google.antigravity.hooks` and `google.antigravity.types`.
*   Refactor the checkout deciding hook function to be `async` and return `HookResult`.

#### [MODIFY] [config.py](file:///Users/dynamiterdx/Documents/Personal%20Projects/diet_planner/backend/app/agent/config.py)
*   Remove hallucinated `Policies` class.
*   Implement policies using `google.antigravity.hooks.policy.allow` and `ask_user`.

#### [NEW] [supabase_client.py](file:///Users/dynamiterdx/Documents/Personal%20Projects/diet_planner/backend/app/supabase_client.py)
*   Initialize the live Supabase python client using `SUPABASE_URL` and `SUPABASE_KEY` from `.env`.
*   Provide robust CRUD functions to select and insert into `pantry_stock` and `macro_diary` tables.

#### [MODIFY] [main.py](file:///Users/dynamiterdx/Documents/Personal%20Projects/diet_planner/backend/app/main.py)
*   Implement a lifespan handler to enter and exit the `coordinator_agent` context manager on FastAPI startup and shutdown.
*   Refactor the `/api/upload-photo` endpoint to construct a real `google.antigravity.types.Image` using the uploaded file bytes.
*   Pass the image and text prompt as a multimodal list to the active agent: `await coordinator_agent.chat([prompt, Image(...)])`.
*   Parse Vision returns and insert the extracted items into the Supabase database.

### Frontend Configurations

#### [MODIFY] [page.js](file:///Users/dynamiterdx/Documents/Personal%20Projects/diet_planner/frontend/src/app/page.js)
*   Remove all lingering "simulation" and "sandbox camera" textual references.
*   Update the Blinkit MCP modal checkout button to make a real `fetch("http://localhost:8000/api/grocery/export")` API request, providing a fully integrated decoupled path.
*   Synchronize initial state loading (Pantry Stock and Macro Journal) directly from backend API endpoints backed by Supabase.

---

## 4. Verification Plan

### Automated/Developer Tests
1.  **Boot Backend**: Execute `uvicorn` and verify that the lifespan context starts up successfully without any Python imports or agent initialization failures.
2.  **Multimodal Upload test**: Trigger the `/api/upload-photo` endpoint using a test image file and verify that Gemini 3.5 Flash successfully receives the bytes, segments it, and responds.
3.  **Supabase Sync test**: Perform a chat message asking to "add 3 eggs to the pantry", verify that the agent calls the `add_to_pantry` tool, and check the live Supabase dashboard to verify a new row has been written.

### Manual Verification
1.  Open the dashboard at `http://localhost:3000`.
2.  Perform a real file upload in the camera uploader (Scan Fridge/Scan Plate).
3.  Verify that the dashboard inventory state and macro charts update in real-time, pulling directly from your live database.
