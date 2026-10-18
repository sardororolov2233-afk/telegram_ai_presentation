-- Apply AFTER 20261017_commerce.sql, once to the shared Supabase project.
-- Keeps existing balances, rewards, receipts and completed jobs untouched.
begin;

create table if not exists public.orzu_bot_sessions (
    user_id bigint primary key,
    session jsonb not null default '{}',
    lock_key text,
    lock_until timestamptz,
    updated_at timestamptz not null default now()
);
create table if not exists public.orzu_bot_updates (
    update_key text primary key,
    user_id bigint not null,
    completed boolean not null default false,
    updated_at timestamptz not null default now()
);
create index if not exists orzu_bot_updates_user_idx on public.orzu_bot_updates(user_id, updated_at);
alter table public.orzu_bot_sessions enable row level security;
alter table public.orzu_bot_updates enable row level security;
revoke all on public.orzu_bot_sessions, public.orzu_bot_updates from anon, authenticated;
grant all on public.orzu_bot_sessions, public.orzu_bot_updates to service_role;

create or replace function public.orzu_bot_begin_update(p_user_id bigint, p_update_key text)
returns jsonb language plpgsql security definer set search_path = public as $$
declare s orzu_bot_sessions%rowtype;
begin
    if p_user_id <= 0 or length(p_update_key) not between 1 and 150 then raise exception 'invalid_user'; end if;
    insert into orzu_bot_sessions(user_id) values(p_user_id) on conflict do nothing;
    select * into s from orzu_bot_sessions where user_id = p_user_id for update;
    if exists(select 1 from orzu_bot_updates where update_key = p_update_key and completed) then
        return jsonb_build_object('duplicate', true);
    end if;
    if s.lock_until > now() then return jsonb_build_object('busy', true); end if;
    insert into orzu_bot_updates(update_key, user_id) values(p_update_key, p_user_id)
        on conflict(update_key) do update set updated_at = now();
    update orzu_bot_sessions set lock_key = p_update_key, lock_until = now() + interval '10 minutes'
        where user_id = p_user_id;
    delete from orzu_bot_updates where user_id = p_user_id and completed and updated_at < now() - interval '7 days';
    return jsonb_build_object('session', case when s.updated_at < now() - interval '2 days' then '{}'::jsonb else s.session end);
end $$;

create or replace function public.orzu_bot_finish_update(
    p_user_id bigint, p_update_key text, p_session jsonb, p_success boolean
) returns boolean language plpgsql security definer set search_path = public as $$
begin
    update orzu_bot_sessions set session = case when p_success then p_session else session end,
        lock_key = null, lock_until = null, updated_at = now()
        where user_id = p_user_id and lock_key = p_update_key;
    if not found then return false; end if;
    if p_success then
        update orzu_bot_updates set completed = true, updated_at = now() where update_key = p_update_key;
    else
        delete from orzu_bot_updates where update_key = p_update_key and not completed;
    end if;
    return true;
end $$;

create or replace function public.commerce_enqueue(p_user_id bigint, p_service text, p_request_id uuid, p_payload jsonb)
returns jsonb language plpgsql security definer set search_path = public as $$
declare v_charge jsonb;
begin
    if p_service not in ('presentation', 'article', 'course', 'referat') then raise exception 'invalid_service'; end if;
    v_charge := commerce_reserve(p_user_id, p_service, p_request_id);
    if (v_charge->>'created')::boolean then
        insert into commerce_jobs(id, user_id, service, payload) values(p_request_id, p_user_id, p_service, p_payload);
    elsif not exists(select 1 from commerce_jobs where id = p_request_id and
        (payload - 'user_images') = (p_payload - 'user_images')) then
        raise exception 'request_conflict';
    end if;
    return v_charge;
end $$;

revoke all on function public.orzu_bot_begin_update(bigint, text) from public, anon, authenticated;
revoke all on function public.orzu_bot_finish_update(bigint, text, jsonb, boolean) from public, anon, authenticated;
grant execute on function public.orzu_bot_begin_update(bigint, text) to service_role;
grant execute on function public.orzu_bot_finish_update(bigint, text, jsonb, boolean) to service_role;
revoke all on function public.commerce_enqueue(bigint, text, uuid, jsonb) from public, anon, authenticated;
grant execute on function public.commerce_enqueue(bigint, text, uuid, jsonb) to service_role;

create or replace function public.orzu_bot_stats()
returns jsonb language sql security definer set search_path = public as $$
    select jsonb_build_object(
        'users', (select count(*) from users),
        'monthly_users', (select count(*) from users where created_at >= date_trunc('month', now())),
        'pending_payments', (select count(*) from payments where status = 'pending'),
        'monthly_revenue', (select coalesce(sum(amount), 0) from payments where status = 'completed' and created_at >= date_trunc('month', now())),
        'revenue', (select coalesce(sum(amount), 0) from payments where status = 'completed'),
        'completed_jobs', (select count(*) from commerce_charges where status = 'completed')
    );
$$;
revoke all on function public.orzu_bot_stats() from public, anon, authenticated;
grant execute on function public.orzu_bot_stats() to service_role;
notify pgrst, 'reload schema';
commit;
