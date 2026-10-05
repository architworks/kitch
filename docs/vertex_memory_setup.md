# Configure Vertex AI Memory Bank

Vertex Memory Bank is optional and independent of SQLite or Supabase. Use it
when household memory must survive backend restarts. Local development may use
`InMemoryMemoryService` instead.

1. Select a Google Cloud project and enable Vertex AI and the APIs required by
   Agent Engine.
2. Create the Agent Engine resource used by Memory Bank and record its numeric
   reasoning-engine ID.
3. Grant the Kitch service account Agent Platform User access.
4. For local verification, install the Google Cloud CLI and run:

```bash
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

5. Configure the backend:

```dotenv
KITCH_MEMORY_SERVICE=vertex
KITCH_MEMORY_BANK_ID=YOUR_REASONING_ENGINE_ID
GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID
GOOGLE_CLOUD_LOCATION=global
```

Gemini inference can continue using `GOOGLE_API_KEY`; Memory Bank uses
Application Default Credentials. Restart the backend, inspect the memory
component of `/api/health/ready`, save a durable preference, restart again and
verify recall. A configured Vertex failure is explicit and never falls back to
in-memory memory.

For Vercel, continue with [`vercel_wif_setup.md`](vercel_wif_setup.md).
