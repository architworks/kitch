# Configure Supabase persistence

Use this path when Kitch's structured state should be hosted in Supabase rather
than local SQLite. Memory selection is independent.

1. Create a Supabase project.
2. For a new project, apply `backend/database/supabase_schema.sql` in the SQL
   editor. For an existing project, apply every unapplied file in
   `backend/database/migrations/` in filename order.
3. Configure a Google Auth Platform web client for Kitch. Add the exact hosted
   frontend as an authorized JavaScript origin. Direct credential mode does not
   use a Google redirect URI.
4. Configure the backend:

```dotenv
KITCH_DATABASE_BACKEND=supabase
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SECRET_KEY=sb_secret_...
GOOGLE_OAUTH_CLIENT_ID=<web-client-id>.apps.googleusercontent.com
KITCH_AUTH_SESSION_SECRET=<at-least-32-random-characters>
KITCH_ALLOWED_ORIGINS=https://your-kitch-frontend.example
```

Configure the same client ID in the frontend as
`NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID`.

Never expose the secret key to Next.js. Do not set `SUPABASE_KEY`; Kitch rejects
ambiguous, publishable, anon and malformed credentials. The temporary legacy
`SUPABASE_SERVICE_ROLE_KEY` remains supported but cannot be set together with
`SUPABASE_SECRET_KEY`.

The first verified Google sign-in creates one household and owner profile. For
an existing pre-authentication Kitch database, temporarily set
`KITCH_LEGACY_HOUSEHOLD_OWNER_EMAIL` to the intended owner's verified Google
email. Only that account may claim the single `legacy_claimable` household.
Remove the variable after `household_accounts` contains the mapping.

Household members remain rows in `profiles`; they do not sign in. Renaming a
member changes only `full_name`, preserving the profile ID and linked nutrition
and history records.

Start the backend and verify `/api/health/ready`. The unauthenticated response
contains only safe core status; sign in to see detailed component readiness. A
Supabase failure never causes a fallback to SQLite. Keep backend-only RLS/grants
enabled and apply migrations before deploying dependent code.

The browser never accesses Supabase directly. `households`,
`household_accounts`, and all application tables have backend-only grants; the
FastAPI request context supplies the authenticated household scope.
