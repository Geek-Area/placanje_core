# Workbench

This is a small React/TypeScript workbench for:

- implementation documentation
- live backend testing
- manual end-to-end flow validation

## Run

```bash
npm install
npm run dev
```

Default local URL:

```text
http://localhost:5173
```

## What it does

- signs up or signs in with Supabase Auth in the browser
- sends the resulting JWT to the backend
- documents the frontend contract for Pay slips and merchant POS flows
- lets you test merchant signup
- lets you create POS sub-accounts
- lets you create POS transactions
- lets you send a fake signed bank webhook
- lets you test public and consumer Pay slips flows
- optionally lets you test subscriptions

The UI has two tabs:

- `Documentation`
- `Testing`

## Before you use it

Make sure the backend `.env` is filled with:

- `DATABASE_URL`
- `SUPABASE_URL`
- `BANK_WEBHOOK_SECRET`

`SUPABASE_JWT_SECRET` is only needed if you are testing against a local or legacy Supabase setup that still signs access tokens with `HS256`.

And in the tester UI itself fill:

- backend URL
- Supabase URL
- Supabase publishable key
- bank webhook secret
