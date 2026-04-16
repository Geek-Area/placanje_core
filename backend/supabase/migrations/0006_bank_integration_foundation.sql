alter table public.merchant_accounts
  add column if not exists mcc varchar(4);

alter table public.transactions
  add column if not exists bank_provider text,
  add column if not exists bank_credit_transfer_identificator text,
  add column if not exists bank_status_code text,
  add column if not exists bank_status_description text,
  add column if not exists bank_status_checked_at timestamptz;

create unique index if not exists idx_transactions_bank_credit_transfer_identificator
  on public.transactions (bank_provider, bank_credit_transfer_identificator)
  where bank_credit_transfer_identificator is not null;

alter table public.pending_invites
  add column if not exists revoked_at timestamptz;

create table if not exists public.merchant_bank_profiles (
  id uuid primary key default gen_random_uuid(),
  merchant_account_id uuid not null unique references public.merchant_accounts(id) on delete cascade,
  provider text not null,
  bank_user_id text not null,
  terminal_identificator varchar(8) not null,
  active boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint merchant_bank_profiles_tid_length check (char_length(terminal_identificator) = 8)
);

create table if not exists public.bank_session_tokens (
  id uuid primary key default gen_random_uuid(),
  merchant_bank_profile_id uuid not null unique references public.merchant_bank_profiles(id) on delete cascade,
  session_token text not null,
  expires_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create sequence if not exists public.bank_credit_transfer_counter_seq;

create index if not exists idx_merchant_bank_profiles_account
  on public.merchant_bank_profiles (merchant_account_id);

create index if not exists idx_bank_session_tokens_expires_at
  on public.bank_session_tokens (expires_at);

alter table public.merchant_bank_profiles enable row level security;
alter table public.bank_session_tokens enable row level security;

create policy "merchant bank profiles visible to members"
  on public.merchant_bank_profiles
  for select
  to authenticated
  using (
    merchant_account_id in (
      select account_id from public.visible_merchant_accounts(auth.uid())
    )
  );

create trigger merchant_bank_profiles_set_updated_at
before update on public.merchant_bank_profiles
for each row
execute function public.set_updated_at();

create trigger bank_session_tokens_set_updated_at
before update on public.bank_session_tokens
for each row
execute function public.set_updated_at();
