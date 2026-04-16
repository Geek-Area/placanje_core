# Plaćanje-Core Backend

FastAPI backend for Plaćanje-Core.

## Implemented API Areas

- health endpoint
- public transaction creation and public share lookup
- consumer profile and consumer transaction history
- merchant signup, account listing, POS sub-account creation
- merchant invite token flow
- POS transaction creation
- fake bank webhook status updates
- optional subscription creation/pause/resume and local runner hooks

## Local Setup

1. Create `backend/.env` from [.env.example](.env.example).
2. Fill at minimum:
   - `DATABASE_URL`
   - `SUPABASE_URL`
   - `BANK_WEBHOOK_SECRET`
3. Install dependencies:

```bash
pip install -e ".[dev]"
```

4. Start the backend:

```bash
./run_dev.sh
```

## Production Runtime

Use:

```bash
./run_prod.sh
```

Important production env vars:

- `ENV=prod`
- `API_BASE_URL=https://your-api-domain`
- `CORS_ALLOWED_ORIGINS=https://your-frontend-domain,https://your-other-frontend-domain`
- `DATABASE_URL=...`
- `SUPABASE_URL=...`
- `BANK_WEBHOOK_SECRET=...`

Hosted Supabase projects normally use JWKS-based JWT verification, so `SUPABASE_URL` is the expected auth configuration path.

## Docker

Build:

```bash
docker build -t placanje-core-backend ./backend
```

Run:

```bash
docker run --rm -p 8000:8000 --env-file backend/.env placanje-core-backend
```

Health endpoint:

```text
GET /v1/health
```

## Background Jobs

Run due subscriptions:

```bash
python -m app.jobs run-due-subscriptions --limit 100
```

Expire stale POS drafts older than 30 minutes:

```bash
python -m app.jobs expire-pos-transactions --minutes 30
```

## Notes

- The tester app signs in with Supabase and sends the bearer JWT to this backend.
- Dev-only endpoints under `/v1/dev` are available only when `ENV != prod`.
- The fake bank webhook is for local and staging validation, not for the real bank integration contract.
