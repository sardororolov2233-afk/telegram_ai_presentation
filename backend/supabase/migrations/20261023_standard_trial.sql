-- Apply after 20261022_referral_only.sql, once to the shared database.
-- Three successful/reserved standard services per user, shared across referat/article/obyektivka.
begin;
lock table public.commerce_accounts, public.commerce_charges in access exclusive mode;
alter table public.commerce_accounts add column if not exists standard_free_used integer not null default 0
    check (standard_free_used between 0 and 3);
alter table public.commerce_charges add column if not exists standard_trial boolean not null default false;
do $$ begin
    insert into commerce_policy_migrations(name) values ('20261023_standard_trial') on conflict do nothing;
    if found then
        -- Completed historical standard jobs count toward the lifetime allowance; no reset on upgrade.
        update commerce_accounts a set standard_free_used = least(3, (select count(*)::integer
            from commerce_charges c where c.user_id = a.user_id and c.status = 'completed'
            and c.service in ('referat','article','obyektivka')));
        -- Honor already reserved free jobs. Only the remaining first slots belong to the trial.
        with ranked as (
            select c.id, c.user_id, row_number() over (partition by c.user_id order by c.created_at,c.id) n
            from commerce_charges c where c.status = 'reserved' and c.source = 'free'
            and c.service in ('referat','article','obyektivka')
        ) update commerce_charges c set standard_trial = true
          from ranked r, commerce_accounts a where c.id = r.id and a.user_id = r.user_id
          and r.n <= 3 - a.standard_free_used;
        update commerce_accounts a set standard_free_used = standard_free_used +
            (select count(*)::integer from commerce_charges c where c.user_id = a.user_id
             and c.standard_trial and c.status = 'reserved');
    end if;
end $$;
create or replace function public.commerce_policy()
returns jsonb language sql security definer set search_path = public as $$
    select jsonb_build_object('access_mode', 'referral_only', 'subscription_enabled', false,
        'payments_enabled', false, 'quota_costs', jsonb_build_object(
            'presentation', 1, 'design', 1, 'course', 2, 'referat', 1, 'article', 1, 'obyektivka', 1),
        'standard_free_limit', 3, 'standard_trial_enabled', true);
$$;

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
        'standard_free_used', a.standard_free_used, 'standard_free_remaining', greatest(3 - a.standard_free_used, 0),
        'confirmed_referrals', v_refs, 'next_reward_in', 1, 'referral_credits', a.referral_credits,
        'referral_presentations', a.referral_credits, 'design_credits', a.referral_credits,
        'course_credits', a.referral_credits / 2,
        -- Compatibility fields describe no paid access; these are not separate credit pools.
        'subscription_active', false, 'subscription_end', null, 'subscription_remaining', 0,
        'presentation_period_active', false,
        'prices', jsonb_build_object('presentation', 0, 'design', 0, 'course', 0,
            'referat', 0, 'article', 0, 'obyektivka', 0));
end $$;

create or replace function public.commerce_reserve(p_user_id bigint, p_service text, p_request_id uuid)
returns jsonb language plpgsql security definer set search_path = public as $$
declare a commerce_accounts%rowtype; c commerce_charges%rowtype; v_units integer; v_trial boolean := false;
begin
    select * into a from commerce_accounts where user_id = p_user_id for update;
    if not found then raise exception 'user_not_registered'; end if;
    select * into c from commerce_charges where id = p_request_id;
    if found then
        if c.user_id <> p_user_id or c.service <> p_service then raise exception 'request_conflict'; end if;
        return to_jsonb(c) || jsonb_build_object('created', false);
    end if;
    v_units := case p_service when 'presentation' then 1 when 'design' then 1 when 'course' then 2
        when 'referat' then 1 when 'article' then 1 when 'obyektivka' then 1 else null end;
    if v_units is null then raise exception 'invalid_service'; end if;
    if p_service in ('referat', 'article', 'obyektivka') and a.standard_free_used < 3 then
        v_trial := true; v_units := 0;
        update commerce_accounts set standard_free_used = standard_free_used + 1 where user_id = p_user_id;
    end if;
    if a.referral_credits < v_units then raise exception 'insufficient_referral_credits'; end if;
    if v_units > 0 then
        update commerce_accounts set referral_credits = referral_credits - v_units where user_id = p_user_id;
    end if;
    insert into commerce_charges(id, user_id, service, source, amount, credit_units, standard_trial)
        values(p_request_id, p_user_id, p_service, case when v_units > 0 then 'referral' else 'free' end, 0, v_units, v_trial)
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
        if c.standard_trial then
            update commerce_accounts set standard_free_used = greatest(standard_free_used - 1, 0) where user_id = p_user_id;
        end if;
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
revoke all on function public.commerce_policy() from public, anon, authenticated;
revoke all on function public.commerce_status(bigint) from public, anon, authenticated;
revoke all on function public.commerce_reserve(bigint,text,uuid) from public, anon, authenticated;
revoke all on function public.commerce_finish(bigint,uuid,boolean) from public, anon, authenticated;
grant execute on function public.commerce_policy(), public.commerce_status(bigint),
    public.commerce_reserve(bigint,text,uuid), public.commerce_finish(bigint,uuid,boolean) to service_role;
notify pgrst, 'reload schema';
commit;
