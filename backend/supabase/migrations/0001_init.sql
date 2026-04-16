create extension if not exists pgcrypto;
create extension if not exists citext;

do $$
begin
  if not exists (select 1 from pg_type where typname = 'form_type') then
    create type public.form_type as enum ('regular', 'ips', 'subscription');
  end if;
  if not exists (select 1 from pg_type where typname = 'transaction_status') then
    create type public.transaction_status as enum (
      'draft',
      'awaiting_payment',
      'completed',
      'failed',
      'cancelled',
      'expired',
      'scheduled'
    );
  end if;
  if not exists (select 1 from pg_type where typname = 'account_type') then
    create type public.account_type as enum ('organization', 'pos');
  end if;
  if not exists (select 1 from pg_type where typname = 'membership_role') then
    create type public.membership_role as enum ('owner', 'admin', 'operator', 'viewer');
  end if;
  if not exists (select 1 from pg_type where typname = 'membership_scope') then
    create type public.membership_scope as enum ('account_only', 'account_and_descendants');
  end if;
end $$;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table if not exists public.consumer_users (
  id uuid primary key references auth.users(id) on delete cascade,
  email citext unique not null,
  display_name text,
  auth_provider text not null default 'email',
  preferences jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  last_login_at timestamptz
);

create table if not exists public.merchant_users (
  id uuid primary key references auth.users(id) on delete cascade,
  email citext unique not null,
  display_name text,
  auth_provider text not null default 'email',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  last_login_at timestamptz
);

create table if not exists public.merchant_accounts (
  id uuid primary key default gen_random_uuid(),
  parent_account_id uuid references public.merchant_accounts(id) on delete cascade,
  account_type public.account_type not null,
  slug citext unique not null,
  display_name text not null,
  legal_entity_name text,
  legal_entity_id text,
  payee_account_number varchar(18),
  payee_name text not null,
  payee_address text,
  payee_city text,
  default_payment_code char(3) not null default '289',
  default_currency char(3) not null default 'RSD',
  default_reference_model varchar(2),
  custom_fields_schema jsonb not null default '{}'::jsonb,
  subscription_tier text,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint merchant_accounts_account_number_length check (
    payee_account_number is null or char_length(payee_account_number) = 18
  )
);

create table if not exists public.merchant_memberships (
  id uuid primary key default gen_random_uuid(),
  merchant_user_id uuid not null references public.merchant_users(id) on delete cascade,
  merchant_account_id uuid not null references public.merchant_accounts(id) on delete cascade,
  role public.membership_role not null,
  scope public.membership_scope not null,
  created_at timestamptz not null default now(),
  revoked_at timestamptz,
  unique (merchant_user_id, merchant_account_id)
);

create table if not exists public.subscriptions (
  id uuid primary key default gen_random_uuid(),
  merchant_account_id uuid not null references public.merchant_accounts(id) on delete cascade,
  subscriber_consumer_user_id uuid references public.consumer_users(id) on delete set null,
  subscriber_email citext not null,
  subscriber_name text,
  template jsonb not null,
  cadence text not null,
  next_run_at timestamptz not null,
  last_run_at timestamptz,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  ended_at timestamptz
);

create table if not exists public.transactions (
  id uuid primary key default gen_random_uuid(),
  form_type public.form_type not null,
  status public.transaction_status not null default 'draft',
  payment_ref text not null unique,
  consumer_user_id uuid references public.consumer_users(id) on delete set null,
  merchant_account_id uuid references public.merchant_accounts(id) on delete set null,
  subscription_id uuid references public.subscriptions(id) on delete set null,
  payer_name text,
  payer_address text,
  payer_city text,
  payee_name text not null,
  payee_address text,
  payee_city text,
  payee_account_number varchar(18) not null,
  amount numeric(18,2) not null,
  currency char(3) not null default 'RSD',
  payment_code char(3) not null,
  reference_model varchar(2),
  reference_number text,
  payment_description text,
  ips_qr_payload text not null,
  bank_transaction_ref text,
  completed_at timestamptz,
  custom_fields jsonb not null default '{}'::jsonb,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint transactions_account_number_length check (char_length(payee_account_number) = 18),
  constraint transactions_amount_positive check (amount > 0)
);

create table if not exists public.share_links (
  id uuid primary key default gen_random_uuid(),
  transaction_id uuid not null references public.transactions(id) on delete cascade,
  slug text not null unique,
  qr_string text not null,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  accessed_count integer not null default 0,
  revoked_at timestamptz
);

create table if not exists public.idempotency_keys (
  id uuid primary key default gen_random_uuid(),
  idempotency_key text not null,
  request_scope text not null,
  actor_id uuid,
  response_fingerprint text,
  resource_id uuid,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null default (now() + interval '24 hours'),
  unique (idempotency_key, request_scope, actor_id)
);

create index if not exists idx_transactions_form_type_created_at
  on public.transactions (form_type, created_at desc);
create index if not exists idx_transactions_consumer_created_at
  on public.transactions (consumer_user_id, created_at desc);
create index if not exists idx_transactions_merchant_created_at
  on public.transactions (merchant_account_id, created_at desc);
create index if not exists idx_transactions_subscription_created_at
  on public.transactions (subscription_id, created_at desc);
create index if not exists idx_transactions_active_status
  on public.transactions (status)
  where status in ('awaiting_payment', 'scheduled');
create index if not exists idx_share_links_expires_at
  on public.share_links (expires_at);
create index if not exists idx_share_links_transaction_id
  on public.share_links (transaction_id);
create index if not exists idx_merchant_accounts_parent
  on public.merchant_accounts (parent_account_id);
create index if not exists idx_merchant_memberships_user
  on public.merchant_memberships (merchant_user_id);
create index if not exists idx_merchant_memberships_account_role
  on public.merchant_memberships (merchant_account_id, role);
create index if not exists idx_subscriptions_next_run
  on public.subscriptions (next_run_at)
  where active = true;
create index if not exists idx_idempotency_keys_expires_at
  on public.idempotency_keys (expires_at);

create or replace function public.visible_merchant_accounts(request_user_id uuid)
returns table(account_id uuid)
language sql
stable
security definer
set search_path = public
as $$
  with recursive visible as (
    select mm.merchant_account_id as account_id, mm.scope
    from public.merchant_memberships mm
    where mm.merchant_user_id = request_user_id
      and mm.revoked_at is null
    union all
    select child.id as account_id, visible.scope
    from public.merchant_accounts child
    join visible on child.parent_account_id = visible.account_id
    where visible.scope = 'account_and_descendants'
  )
  select distinct visible.account_id
  from visible;
$$;

alter table public.consumer_users enable row level security;
alter table public.merchant_users enable row level security;
alter table public.merchant_accounts enable row level security;
alter table public.merchant_memberships enable row level security;
alter table public.transactions enable row level security;
alter table public.share_links enable row level security;
alter table public.idempotency_keys enable row level security;
alter table public.subscriptions enable row level security;

create policy "consumer users manage self"
  on public.consumer_users
  for all
  to authenticated
  using (id = auth.uid())
  with check (id = auth.uid());

create policy "merchant users manage self"
  on public.merchant_users
  for all
  to authenticated
  using (id = auth.uid())
  with check (id = auth.uid());

create policy "merchant accounts visible to members"
  on public.merchant_accounts
  for select
  to authenticated
  using (id in (select account_id from public.visible_merchant_accounts(auth.uid())));

create policy "merchant memberships visible to relevant users"
  on public.merchant_memberships
  for select
  to authenticated
  using (
    merchant_user_id = auth.uid()
    or merchant_account_id in (
      select account_id from public.visible_merchant_accounts(auth.uid())
    )
  );

create policy "consumer transactions visible to owner"
  on public.transactions
  for select
  to authenticated
  using (consumer_user_id = auth.uid());

create policy "merchant transactions visible to members"
  on public.transactions
  for select
  to authenticated
  using (
    merchant_account_id in (
      select account_id from public.visible_merchant_accounts(auth.uid())
    )
  );

create policy "subscription rows visible to owner or merchant"
  on public.subscriptions
  for select
  to authenticated
  using (
    subscriber_consumer_user_id = auth.uid()
    or merchant_account_id in (
      select account_id from public.visible_merchant_accounts(auth.uid())
    )
  );

create policy "idempotency rows visible to actor"
  on public.idempotency_keys
  for select
  to authenticated
  using (actor_id = auth.uid());

create trigger consumer_users_set_updated_at
before update on public.consumer_users
for each row execute function public.set_updated_at();

create trigger merchant_users_set_updated_at
before update on public.merchant_users
for each row execute function public.set_updated_at();

create trigger merchant_accounts_set_updated_at
before update on public.merchant_accounts
for each row execute function public.set_updated_at();

create trigger transactions_set_updated_at
before update on public.transactions
for each row execute function public.set_updated_at();
