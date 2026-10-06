# Configure Swiggy Instamart

Kitch connects to Swiggy's real Instamart `/im` MCP server. It does not ship a
simulated catalogue, address book, cart or payment response.

## Localhost

The local environment example enables:

```dotenv
SWIGGY_INSTAMART_ENABLED=true
SWIGGY_INSTAMART_ENV=local
SWIGGY_INSTAMART_MCP_URL=https://mcp.swiggy.com/im
SWIGGY_OAUTH_BASE_URL=https://mcp.swiggy.com
SWIGGY_OAUTH_REDIRECT_URI=http://localhost:8000/api/grocery/providers/swiggy_instamart/oauth/callback
FRONTEND_URL=http://localhost:3000
```

Connect triggers Dynamic Client Registration and OAuth 2.1 PKCE. The user
enters their phone and OTP only on Swiggy. Kitch stores the encrypted access
token in the selected database. When a token expires without a refresh token,
the UI requires reconnection.

SQLite installations create their provider-encryption key under `.kitch/`.
Hosted deployments must set `PROVIDER_CREDENTIAL_ENCRYPTION_KEY` explicitly.

## Hosted callbacks

Swiggy requires an exact approved HTTPS callback for production. Complete
Swiggy's production onboarding before enabling the production gate:

```dotenv
SWIGGY_INSTAMART_ENV=production
SWIGGY_OAUTH_REDIRECT_URI=https://YOUR_BACKEND/api/grocery/providers/swiggy_instamart/oauth/callback
SWIGGY_INSTAMART_PRODUCTION_APPROVED=true
PROVIDER_CREDENTIAL_ENCRYPTION_KEY=YOUR_FERNET_KEY
```

For the Vercel deployment in this repository, the exact callback includes the
backend function prefix:

`https://kitch-meal-planner.vercel.app/backend/api/grocery/providers/swiggy_instamart/oauth/callback`

`FRONTEND_URL` is optional when the frontend and backend share an origin, as
they do in the Vercel deployment. Kitch then uses a relative post-callback
redirect, so an omitted variable cannot accidentally send the hosted browser
to localhost. Set it only when the frontend intentionally uses another origin.

The callback is accepted only with the same authenticated Kitch household
session that started the flow. OAuth state, the encrypted token, provider cart,
review and checkout authority are all scoped to that household's owner profile.

Disconnect performs best-effort Swiggy logout and deletes Kitch's encrypted
connection and provider review. Expired OAuth-flow records are purged after 24
hours; inactive checkout reviews and long-expired connections default to 30
days. The configurable windows and privacy boundary are documented in
`security_and_privacy.md`.

Never use automated tests to place a production order. Checkout remains
available only through the explicit reviewed UI flow.
