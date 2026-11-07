-- Split: shared expenses for two people.
-- Run this once in the Supabase SQL editor (or as a migration).
--
-- Security model: the tables have RLS enabled and NO policies, so the public
-- anon key cannot read or write them directly. The page only talks to the
-- database through the functions below, and every function checks the shared
-- PIN first. The PIN is stored as a bcrypt hash.

create extension if not exists pgcrypto with schema extensions;

create table if not exists public.split_settings (
  id        int primary key default 1 check (id = 1),
  name_a    text not null default 'Sam',
  name_b    text not null default 'Partner',
  pin_hash  text            -- null until the first PIN is chosen in the app
);
insert into public.split_settings (id) values (1) on conflict do nothing;

create table if not exists public.split_entries (
  id          uuid primary key default gen_random_uuid(),
  created_at  timestamptz not null default now(),
  spent_on    date not null default current_date,
  description text not null,
  amount      numeric(12,2) not null check (amount > 0),
  paid_by     text not null check (paid_by in ('a','b')),
  share_a     numeric(12,2) not null check (share_a >= 0),  -- what person A consumed
  share_b     numeric(12,2) not null check (share_b >= 0),  -- what person B consumed
  split_mode  text not null check (split_mode in ('equal','full','exact','percent','settle')),
  check (share_a + share_b = amount)
);

alter table public.split_settings enable row level security;
alter table public.split_entries  enable row level security;
revoke all on public.split_settings, public.split_entries from anon, authenticated;

-- Checks the PIN. On the very first call (no PIN set yet) the given PIN becomes the PIN.
create or replace function public.split_auth(p_pin text)
returns void language plpgsql security definer set search_path = public, extensions as $$
declare h text;
begin
  select pin_hash into h from split_settings where id = 1 for update;
  if h is null then
    if length(coalesce(p_pin,'')) < 6 then
      raise exception 'PIN must be at least 6 characters';
    end if;
    update split_settings set pin_hash = crypt(p_pin, gen_salt('bf')) where id = 1;
  elsif h <> crypt(coalesce(p_pin,''), h) then
    perform pg_sleep(1);  -- slow down guessing
    raise exception 'Wrong PIN';
  end if;
end $$;

create or replace function public.split_list(p_pin text)
returns json language plpgsql security definer set search_path = public as $$
begin
  perform split_auth(p_pin);
  return json_build_object(
    'settings', (select json_build_object('name_a', name_a, 'name_b', name_b) from split_settings where id = 1),
    'entries',  coalesce((select json_agg(e order by e.spent_on desc, e.created_at desc) from split_entries e), '[]'::json)
  );
end $$;

-- Insert (p_id null) or update an entry.
create or replace function public.split_save(
  p_pin text, p_id uuid, p_spent_on date, p_description text, p_amount numeric,
  p_paid_by text, p_share_a numeric, p_share_b numeric, p_split_mode text)
returns uuid language plpgsql security definer set search_path = public as $$
declare new_id uuid;
begin
  perform split_auth(p_pin);
  if p_id is null then
    insert into split_entries (spent_on, description, amount, paid_by, share_a, share_b, split_mode)
    values (p_spent_on, trim(p_description), p_amount, p_paid_by, p_share_a, p_share_b, p_split_mode)
    returning id into new_id;
  else
    update split_entries set spent_on = p_spent_on, description = trim(p_description), amount = p_amount,
      paid_by = p_paid_by, share_a = p_share_a, share_b = p_share_b, split_mode = p_split_mode
    where id = p_id returning id into new_id;
  end if;
  return new_id;
end $$;

create or replace function public.split_delete(p_pin text, p_id uuid)
returns void language plpgsql security definer set search_path = public as $$
begin
  perform split_auth(p_pin);
  delete from split_entries where id = p_id;
end $$;

create or replace function public.split_settings_save(p_pin text, p_name_a text, p_name_b text, p_new_pin text)
returns void language plpgsql security definer set search_path = public, extensions as $$
begin
  perform split_auth(p_pin);
  update split_settings set name_a = trim(p_name_a), name_b = trim(p_name_b) where id = 1;
  if coalesce(p_new_pin, '') <> '' then
    if length(p_new_pin) < 6 then raise exception 'PIN must be at least 6 characters'; end if;
    update split_settings set pin_hash = crypt(p_new_pin, gen_salt('bf')) where id = 1;
  end if;
end $$;

revoke all on function public.split_auth(text) from public, anon, authenticated;
grant execute on function public.split_list(text) to anon;
grant execute on function public.split_save(text, uuid, date, text, numeric, text, numeric, numeric, text) to anon;
grant execute on function public.split_delete(text, uuid) to anon;
grant execute on function public.split_settings_save(text, text, text, text) to anon;
