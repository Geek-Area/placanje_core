# Plaćanje-Core

Shared backend for the Plaćanje product ecosystem:

- `Plaćanje.RS` for public Pay slips and IPS QR creation
- `Instant.Plaćanje.RS` for merchant onboarding, POS accounts, and bank callback handling
- `Pretplate.RS` for optional recurring-payment logic

## Current Status

This repo is no longer architecture-only.

What is implemented and tested locally:

- Supabase JWT verification with hosted-project JWKS support
- Supabase-backed Postgres schema and migrations
- merchant signup and nested merchant/POS accounts
- public payment transaction creation and share links
- consumer profile and consumer transaction creation/listing
- POS transaction draft creation
- fake bank webhook endpoint and signature verification
- local documentation and testing workbench for manual end-to-end flow validation

What is still not production-complete:

- real bank integration instead of the fake webhook harness
- real email delivery for merchant invites/share flows
- production frontend apps using this backend directly
- full operational deployment and secret management in your chosen host

## Repo Layout

- [backend/README.md](backend/README.md) - FastAPI backend, migrations, and runtime instructions
- [tester/README.md](tester/README.md) - local React workbench for live API validation

## Local Development

Backend:

```bash
cd backend
python3 -m uvicorn app.main:app --reload
```

Documentation and testing workbench:

```bash
cd tester
npm install
npm run dev
```

## Deployment Direction

The backend now has a Docker-based deployment path and production startup script.

Use this repo for:

- staging the backend on a standard container host
- wiring real frontend apps to the hosted API
- validating webhook and merchant flows against a shared environment

Do not deploy the `tester/` app as your product frontend. It is an internal workbench for implementation docs and live validation.
