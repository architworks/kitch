# Configure Supabase persistence

Use this path when Kitch's structured state should be hosted in Supabase rather
than local SQLite. Memory selection is independent.

1. Create a Supabase project.
2. For a new project, apply `backend/database/supabase_schema.sql` in the SQL
   editor. For an existing project, apply every unapplied file in
   `backend/database/migrations/` in filename order.
3. Create the household profiles required by the current single-household
   deployment and keep the owner profile consistent with the backend household
   configuration.
4. Configure the backend:

```dotenv
KITCH_DATABASE_BACKEND=supabase
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SECRET_KEY=sb_secret_...
```

Never expose the secret key to Next.js. Do not set `SUPABASE_KEY`; Kitch rejects
ambiguous, publishable, anon and malformed credentials. The temporary legacy
`SUPABASE_SERVICE_ROLE_KEY` remains supported but cannot be set together with
`SUPABASE_SECRET_KEY`.

Start the backend and verify `/api/health/ready`. It checks required tables,
elevated access and the household owner. A Supabase failure never causes a
fallback to SQLite. Keep backend-only RLS/grants enabled and apply migrations
before deploying dependent code.
