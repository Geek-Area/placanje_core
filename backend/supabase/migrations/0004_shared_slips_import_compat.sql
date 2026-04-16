alter table public.shared_slips
  add column if not exists form_type text,
  add column if not exists user_id text;

comment on column public.shared_slips.form_type is
  'Legacy import-only field preserved for CSV compatibility.';

comment on column public.shared_slips.user_id is
  'Legacy import-only field preserved for CSV compatibility.';
