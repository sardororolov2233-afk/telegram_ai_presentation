-- Run after 20261017_commerce.sql in the shared Supabase project.
-- One confirmed new friend earns one permanent, shared credit.
begin;

lock table public.commerce_accounts, public.commerce_grants, public.commerce_charges in access exclusive mode;
alter table public.commerce_accounts add column if not exists referral_credits integer not null default 0
    check (referral_credits >= 0);
alter table public.commerce_charges add column if not exists credit_units integer not null default 0
    check (credit_units >= 0);
alter table public.commerce_charges drop constraint if exists commerce_charges_source_check;
alter table public.commerce_charges add constraint commerce_charges_source_check
    check (source in ('balance', 'subscription', 'referral', 'free'));

create table if not exists public.commerce_policy_migrations (
    name text primary key, applied_at timestamptz not null default now()
);
do $$ begin
    insert into commerce_policy_migrations(name) values('20261022_referral_only') on conflict do nothing;
    if found then
        -- Preserve unused, already-earned referral rewards. A coursework reward is worth two units.
        -- Confirmed friends below the old five-person threshold also get their unawarded units.
        update commerce_accounts a set referral_credits =
            coalesce((select sum(g.remaining * case g.service when 'course' then 2 else 1 end)
                from commerce_grants g where g.user_id = a.user_id
                and (g.expires_at is null or g.expires_at > now())), 0)::integer
            + greatest((select count(*)::integer from commerce_accounts r
                where r.referrer_id = a.user_id and r.referral_confirmed) - a.rewarded_batches * 5, 0);
        -- Pending old referral reservations refund into the new shared wallet, exactly once.
        update commerce_charges set credit_units = case service when 'course' then 2 else 1 end
            where source = 'referral' and status = 'reserved';
    end if;
end $$;

create or replace function public.commerce_policy()
returns jsonb language sql security definer set search_path = public as $$
    select jsonb_build_object('access_mode', 'referral_only', 'subscription_enabled', false,
        'payments_enabled', false, 'quota_costs', jsonb_build_object(
            'presentation', 1, 'design', 1, 'course', 2, 'referat', 0, 'article', 0, 'obyektivka', 0));
$$;

create or replace function public.commerce_confirm_referral(p_user_id bigint)
returns jsonb language plpgsql security definer set search_path = public as $$
declare v_ref bigint; v_count integer; v_credits integer;
begin
    select referrer_id into v_ref from commerce_accounts where user_id = p_user_id;
    if v_ref is null then return jsonb_build_object('awarded', false, 'credits_awarded', 0); end if;
    perform 1 from commerce_accounts where user_id = v_ref for update;
    update commerce_accounts set referral_confirmed = true
        where user_id = p_user_id and not referral_confirmed;
    if not found then return jsonb_build_object('awarded', false, 'credits_awarded', 0); end if;
    update commerce_accounts set referral_credits = referral_credits + 1
        where user_id = v_ref returning referral_credits into v_credits;
    select count(*)::integer into v_count from commerce_accounts
        where referrer_id = v_ref and referral_confirmed;
    return jsonb_build_object('awarded', true, 'credits_awarded', 1, 'referrer_id', v_ref,
        'confirmed', v_count, 'referral_credits', v_credits);
end $$;

create or replace function public.commerce_status(p_user_id bigint)
returns jsonb language plpgsql security definer set search_path = public as $$
declare a commerce_accounts%rowtype; v_refs integer;
begin
    select * into a from commerce_accounts where user_id = p_user_id;
    if not found then raise exception 'user_not_registered'; end if;
    select count(*)::integer into v_refs from commerce_accounts
        where referrer_id = p_user_id and referral_confirmed;
    return commerce_policy() || jsonb_build_object(
        'balance', (select coalesce(balance, 0) from users where telegram_id = p_user_id),
        'confirmed_referrals', v_refs, 'next_reward_in', 1, 'referral_credits', a.referral_credits,
        'referral_presentations', a.referral_credits, 'design_credits', a.referral_credits,
        'course_credits', a.referral_credits / 2,
        -- Compatibility fields describe no paid access; these are not separate credit pools.
        'subscription_active', false, 'subscription_end', null, 'subscription_remaining', 0,
        'presentation_period_active', false,
        'prices', jsonb_build_object('presentation', 0, 'design', 0, 'course', 0,
            'referat', 0, 'article', 0, 'obyektivka', 0));
end $$;

create or replace function public.commerce_subscribe(p_user_id bigint)
returns jsonb language plpgsql security definer set search_path = public as $$
begin
    raise exception 'subscriptions_disabled';
end $$;

create or replace function public.commerce_approve_payment(p_payment_id text)
returns jsonb language plpgsql security definer set search_path = public as $$
begin
    -- Preserve historical balances/receipts, but never sell new access through a stale client.
    raise exception 'payments_disabled';
end $$;

create or replace function public.commerce_reserve(p_user_id bigint, p_service text, p_request_id uuid)
returns jsonb language plpgsql security definer set search_path = public as $$
declare a commerce_accounts%rowtype; c commerce_charges%rowtype; v_units integer;
begin
    select * into a from commerce_accounts where user_id = p_user_id for update;
    if not found then raise exception 'user_not_registered'; end if;
    select * into c from commerce_charges where id = p_request_id;
    if found then
        if c.user_id <> p_user_id or c.service <> p_service then raise exception 'request_conflict'; end if;
        return to_jsonb(c) || jsonb_build_object('created', false);
    end if;
    v_units := case p_service when 'presentation' then 1 when 'design' then 1 when 'course' then 2
        when 'referat' then 0 when 'article' then 0 when 'obyektivka' then 0 else null end;
    if v_units is null then raise exception 'invalid_service'; end if;
    if a.referral_credits < v_units then raise exception 'insufficient_referral_credits'; end if;
    if v_units > 0 then
        update commerce_accounts set referral_credits = referral_credits - v_units where user_id = p_user_id;
    end if;
    insert into commerce_charges(id, user_id, service, source, amount, credit_units)
        values(p_request_id, p_user_id, p_service, case when v_units > 0 then 'referral' else 'free' end, 0, v_units)
        returning * into c;
    return to_jsonb(c) || jsonb_build_object('created', true);
end $$;

create or replace function public.commerce_finish(p_user_id bigint, p_request_id uuid, p_success boolean)
returns jsonb language plpgsql security definer set search_path = public as $$
declare c commerce_charges%rowtype;
begin
    perform 1 from commerce_accounts where user_id = p_user_id for update;
    select * into c from commerce_charges where id = p_request_id and user_id = p_user_id for update;
    if not found then raise exception 'charge_not_found'; end if;
    if c.status <> 'reserved' then return to_jsonb(c); end if;
    if not p_success then
        if c.source = 'referral' then
            update commerce_accounts set referral_credits = referral_credits + c.credit_units where user_id = p_user_id;
        elsif c.source = 'balance' then
            -- Refund only jobs reserved by the old policy; new jobs never debit money.
            update users set balance = coalesce(balance, 0) + c.amount where telegram_id = p_user_id;
        elsif c.source = 'subscription' then
            update commerce_accounts set subscription_used = greatest(subscription_used - 1, 0)
                where user_id = p_user_id and subscription_start = c.subscription_start;
        end if;
    else
        insert into statistics(user_id, action_type, amount)
            values(p_user_id, case when c.service = 'course' then 'course_work' else c.service end, c.amount);
    end if;
    update commerce_charges set status = case when p_success then 'completed' else 'refunded' end,
        updated_at = now() where id = p_request_id returning * into c;
    return to_jsonb(c);
end $$;

alter table public.commerce_policy_migrations enable row level security;
revoke all on table public.commerce_policy_migrations from public, anon, authenticated;
grant all on table public.commerce_policy_migrations to service_role;
do $$ declare f record; begin
    for f in select oid::regprocedure as signature from pg_proc
        where pronamespace = 'public'::regnamespace and proname like 'commerce_%'
    loop
        execute format('revoke all on function %s from public, anon, authenticated', f.signature);
        execute format('grant execute on function %s to service_role', f.signature);
    end loop;
end $$;
commit;
