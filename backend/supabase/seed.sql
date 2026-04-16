insert into public.merchant_accounts (
  id,
  parent_account_id,
  account_type,
  slug,
  display_name,
  legal_entity_name,
  legal_entity_id,
  payee_account_number,
  payee_name,
  payee_address,
  payee_city
)
values
  (
    '10000000-0000-0000-0000-000000000001',
    null,
    'organization',
    'demo-org',
    'Demo Org',
    'Demo Org d.o.o.',
    '123456789',
    '340000000000000001',
    'Demo Org d.o.o.',
    'Bulevar Oslobodjenja 1',
    'Nis'
  ),
  (
    '10000000-0000-0000-0000-000000000002',
    '10000000-0000-0000-0000-000000000001',
    'pos',
    'demo-org-pos-01',
    'Demo Org POS 01',
    null,
    null,
    '340000000000000001',
    'Demo Org POS 01',
    'Bulevar Oslobodjenja 1',
    'Nis'
)
on conflict (id) do nothing;

insert into public.consumer_users (id, email, display_name)
select id, email, coalesce(raw_user_meta_data->>'display_name', 'Dev Consumer')
from auth.users
where id = '00000000-0000-0000-0000-000000000001'
on conflict (id) do nothing;

insert into public.merchant_users (id, email, display_name)
select id, email, coalesce(raw_user_meta_data->>'display_name', 'Dev Merchant Owner')
from auth.users
where id = '00000000-0000-0000-0000-000000000010'
on conflict (id) do nothing;

insert into public.merchant_memberships (
  id,
  merchant_user_id,
  merchant_account_id,
  role,
  scope
)
select
  '20000000-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000010',
  '10000000-0000-0000-0000-000000000001',
  'owner',
  'account_and_descendants'
where exists (
  select 1
  from public.merchant_users
  where id = '00000000-0000-0000-0000-000000000010'
)
on conflict (merchant_user_id, merchant_account_id) do nothing;
