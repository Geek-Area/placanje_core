create table if not exists public.pending_invites (
  id uuid primary key default gen_random_uuid(),
  email citext not null,
  merchant_account_id uuid not null references public.merchant_accounts(id) on delete cascade,
  role public.membership_role not null,
  token text not null unique,
  invited_by_merchant_user_id uuid references public.merchant_users(id) on delete set null,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  accepted_at timestamptz
);

create index if not exists idx_pending_invites_token
  on public.pending_invites (token);

create index if not exists idx_pending_invites_email
  on public.pending_invites (email);

create index if not exists idx_pending_invites_expires_at
  on public.pending_invites (expires_at);

alter table public.pending_invites enable row level security;
