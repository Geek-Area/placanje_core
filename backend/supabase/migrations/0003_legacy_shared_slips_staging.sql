create table if not exists public.shared_slips (
  id text primary key,
  slug text,
  data jsonb,
  payload jsonb,
  qr_string text,
  payer_name text,
  payer_address text,
  payer_city text,
  payee_name text,
  payee_address text,
  payee_city text,
  account_number text,
  payee_account_number text,
  amount text,
  currency text,
  payment_code text,
  reference_model text,
  reference_number text,
  payment_description text,
  created_at timestamptz,
  updated_at timestamptz,
  expires_at timestamptz,
  raw_row jsonb,
  imported_at timestamptz not null default now()
);

comment on table public.shared_slips is
  'Legacy CSV staging table for imported shared_slips rows from the pre-core prototype. Do not use as the live product contract.';

create index if not exists idx_shared_slips_slug
  on public.shared_slips (slug);

create index if not exists idx_shared_slips_expires_at
  on public.shared_slips (expires_at);
