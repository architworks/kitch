# Connect Vercel to Google Cloud with Workload Identity Federation

This is the hosted, keyless authentication path for Vertex Memory Bank. Local
SQLite and in-memory installations do not need it.

1. Create a Google Cloud Workload Identity Pool and an OIDC provider.
2. Use the Vercel team issuer displayed by Vercel's OIDC settings.
3. Set the audience to the matching Vercel team/project audience.
4. Map `google.subject` to `assertion.sub` and restrict access to the intended
   Vercel project and environment claims.
5. Grant that federated principal `roles/iam.workloadIdentityUser` on the Kitch
   service account.
6. Grant the service account Agent Platform User access to the Kitch project.
7. Configure Vercel:

```dotenv
KITCH_MEMORY_SERVICE=vertex
KITCH_MEMORY_BANK_ID=YOUR_REASONING_ENGINE_ID
GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID
GOOGLE_CLOUD_LOCATION=global
GCP_PROJECT_NUMBER=YOUR_NUMERIC_PROJECT_NUMBER
GCP_SERVICE_ACCOUNT_EMAIL=kitch-service-account@YOUR_PROJECT_ID.iam.gserviceaccount.com
GCP_WORKLOAD_IDENTITY_POOL_ID=YOUR_POOL_ID
GCP_WORKLOAD_IDENTITY_POOL_PROVIDER_ID=YOUR_PROVIDER_ID
```

Do not upload a service-account JSON key. Redeploy and verify that the memory
component of `/api/health/ready` reports ready.
