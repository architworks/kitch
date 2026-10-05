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

Never use automated tests to place a production order. Checkout remains
available only through the explicit reviewed UI flow.
