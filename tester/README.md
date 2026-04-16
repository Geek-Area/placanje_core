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

- owner login with Supabase Auth in the browser
- POS login with backend POS username/password
- implementation docs for Pay slips and merchant POS flows
- quick owner setup for main account, POS account, and POS login
- POS QR generation, transaction list, and stats
- public and consumer Pay slips testing
- detailed backend testing in the advanced tab

The UI has four tabs:

- `Admin setup`
- `POS terminal`
- `Documentation`
- `Advanced`

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

Owner login uses Supabase.

POS login does not use Supabase. It uses POS credentials created by the owner inside the workbench.
