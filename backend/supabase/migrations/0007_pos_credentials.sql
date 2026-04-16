create table if not exists public.merchant_pos_credentials (
  id uuid primary key default gen_random_uuid(),
  merchant_account_id uuid not null unique references public.merchant_accounts(id) on delete cascade,
  username citext not null unique,
  password_hash text not null,
  password_salt text not null,
  active boolean not null default true,
  created_by_merchant_user_id uuid references public.merchant_users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  last_login_at timestamptz,
  constraint merchant_pos_credentials_username_length check (
    char_length(username::text) between 3 and 64
  )
);

create table if not exists public.merchant_pos_sessions (
  id uuid primary key default gen_random_uuid(),
  merchant_pos_credential_id uuid not null references public.merchant_pos_credentials(id) on delete cascade,
  session_token_hash text not null unique,
  created_at timestamptz not null default now(),
  last_used_at timestamptz,
  expires_at timestamptz not null,
  revoked_at timestamptz
);

create index if not exists idx_merchant_pos_sessions_expires_at
  on public.merchant_pos_sessions (expires_at);

create trigger trg_merchant_pos_credentials_updated_at
before update on public.merchant_pos_credentials
for each row
execute function public.set_updated_at();
