import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { PGlite } from '@electric-sql/pglite';
import { randomUUID } from 'node:crypto';

const db = new PGlite();
let checks = 0;
const verify = (actual, expected) => { assert.deepEqual(actual, expected); checks++; };
async function query(sql, args=[]) { return (await db.query(sql,args)).rows; }
async function rpc(name,...values) {
  const placeholders=values.map((_,index)=>`$${index+1}`).join(',');
  return (await query(`select ${name}(${placeholders}) as result`,values))[0].result;
}
async function rejected(promise, code) { await assert.rejects(promise, error=>error.message.includes(code)); checks++; }
const register = (user,ref=null)=>rpc('commerce_register',user,'Test',null,null,ref);
const status = user=>rpc('commerce_status',user);
const reserve = (user,service,id=randomUUID())=>rpc('commerce_reserve',user,service,id);
const finish = (user,id,success)=>rpc('commerce_finish',user,id,success);
const setBalance = (user,amount)=>query('update users set balance=$1 where telegram_id=$2',[amount,user]);

try {
  await db.exec('create role anon; create role authenticated; create role service_role bypassrls;');
  const migration=await readFile(new URL('../supabase/migrations/20261017_commerce.sql',import.meta.url),'utf8');
  await db.exec(migration);
  await register(100);
  await register(101);
  await db.exec(migration); // Reapplying never resets existing customers or awards.
  await register(101,100);
  await rpc('commerce_confirm_referral',101);
  verify((await status(100)).confirmed_referrals,0);
  await register(200,200); // Self-referral is ignored.
  verify((await query('select referrer_id from commerce_accounts where user_id=200'))[0].referrer_id,null);
  await register(201,999999); // Unknown inviter is ignored.
  verify((await query('select referrer_id from commerce_accounts where user_id=201'))[0].referrer_id,null);
  for(let user=301;user<=305;user++) await register(user,100);
  verify((await status(100)).confirmed_referrals,0); // Joining alone is not confirmation.
  await register(301,101); // Attribution cannot be replaced by another /start link.
  for(let user=301;user<305;user++) await rpc('commerce_confirm_referral',user);
  verify((await status(100)).referral_presentations,0);
  verify((await status(100)).next_reward_in,1);
  const reward=await rpc('commerce_confirm_referral',305);
  verify(reward.awarded,true);
  verify((await status(100)).referral_presentations,5);
  verify((await status(100)).course_credits,1);
  await Promise.all(Array.from({length:10},()=>rpc('commerce_confirm_referral',305)));
  verify((await status(100)).referral_presentations,5);
  for(let user=306;user<=310;user++){await register(user,100);await rpc('commerce_confirm_referral',user);}
  verify((await status(100)).referral_presentations,10);
  verify((await status(100)).course_credits,2);
  verify((await status(100)).next_reward_in,5);
  const free=await reserve(100,'presentation');
  verify(free.source,'referral');
  const duplicate=await reserve(100,'presentation',free.id);
  verify(duplicate.created,false);
  verify((await status(100)).referral_presentations,9);
  await rejected(reserve(100,'course',free.id),'request_conflict');
  await finish(100,free.id,false);await finish(100,free.id,false);
  verify((await status(100)).referral_presentations,10);
  verify((await reserve(100,'presentation',free.id)).status,'refunded');
  for(let i=0;i<2;i++){let charge=await reserve(100,'course');await finish(100,charge.id,true);}
  verify((await status(100)).course_credits,0);
  await rejected(reserve(100,'course'),'insufficient_balance');
  await setBalance(100,50000);
  const course=await reserve(100,'course');verify(course.amount,30000);
  verify((await status(100)).balance,20000);
  await finish(100,course.id,false);verify((await status(100)).balance,50000);

  await register(500);await setBalance(500,100000);
  await rejected(reserve(500,'presentation'),'presentation_access_required');
  await rpc('commerce_subscribe',500);
  verify((await status(500)).balance,75000);
  verify((await status(500)).subscription_remaining,10);
  await rejected(rpc('commerce_subscribe',500),'subscription_active');
  for(let i=0;i<10;i++){let charge=await reserve(500,'presentation');verify(charge.source,'subscription');await finish(500,charge.id,true);}
  verify((await status(500)).subscription_remaining,0);
  const extra=await reserve(500,'presentation');verify(extra.amount,10000);
  verify((await status(500)).balance,65000);
  await finish(500,extra.id,false);await finish(500,extra.id,false);
  verify((await status(500)).balance,75000);
  await query("update commerce_accounts set subscription_end=now()-interval '1 second' where user_id=500");
  verify((await status(500)).subscription_active,false);
  await rejected(reserve(500,'presentation'),'presentation_access_required');
  await rpc('commerce_subscribe',500);
  verify((await status(500)).subscription_remaining,10);
  verify((await status(500)).balance,50000);
  // A stale old-month refund must not increment the new month's allowance.
  const old=await reserve(500,'presentation');
  await query("update commerce_accounts set subscription_start=now()+interval '1 day', subscription_used=2 where user_id=500");
  await finish(500,old.id,false);verify((await status(500)).subscription_remaining,8);
  await query("update commerce_grants set expires_at=now()-interval '1 second' where user_id=100 and service='presentation'");
  verify((await status(100)).referral_presentations,0);
  await rejected(reserve(100,'presentation'),'presentation_access_required');
  for(let user=311;user<=315;user++){await register(user,100);await rpc('commerce_confirm_referral',user);}
  verify((await status(100)).referral_presentations,5);
  verify((await status(100)).course_credits,1);

  await register(600);
  let payment=(await query("insert into payments(user_id,amount,receipt_hash) values(600,25000,'receipt1') returning id"))[0].id;
  await rpc('commerce_approve_payment',String(payment));
  verify((await status(600)).balance,25000); // No old 50% top-up bonus.
  verify(await rpc('commerce_approve_payment',String(payment)),null);
  verify((await status(600)).balance,25000);
  await rejected(query("insert into payments(user_id,amount,receipt_hash) values(600,25000,'receipt1')"),'duplicate key');
  payment=(await query("insert into payments(user_id,amount,purpose) values(600,25000,'subscription') returning id"))[0].id;
  await rpc('commerce_approve_payment',String(payment));
  verify((await status(600)).subscription_remaining,10);
  verify((await status(600)).balance,25000);
  // Two separately paid subscriptions in one month preserve the second as money.
  payment=(await query("insert into payments(user_id,amount,purpose) values(600,25000,'subscription') returning id"))[0].id;
  await rpc('commerce_approve_payment',String(payment));verify((await status(600)).balance,50000);
  payment=(await query("insert into payments(user_id,amount) values(600,10000) returning id"))[0].id;
  await rpc('commerce_reject_payment',String(payment));
  verify(await rpc('commerce_approve_payment',String(payment)),null);
  verify((await status(600)).balance,50000);
  await setBalance(600,7999);
  await rejected(reserve(600,'referat'),'insufficient_balance');
  verify((await status(600)).balance,7999);

  await register(700);await setBalance(700,20000);
  const jobId=randomUUID(), worker=randomUUID();
  const payload={topic:'History',language:'uz',user_images:[],image_hashes:[]};
  await rpc('commerce_enqueue',700,'article',jobId,payload);
  await rpc('commerce_enqueue',700,'article',jobId,payload);
  verify((await status(700)).balance,10000);
  verify((await query('select count(*)::int as n from commerce_jobs where id=$1',[jobId]))[0].n,1);
  await rejected(rpc('commerce_enqueue',700,'article',jobId,{...payload,topic:'Different'}),'request_conflict');
  verify((await status(700)).balance,10000);
  let job=await rpc('commerce_claim_job',worker);verify(job.id,jobId);
  verify(await rpc('commerce_claim_job',randomUUID()),null);
  verify(await rpc('commerce_finish_job',jobId,randomUUID(),true,{},null),false);
  await query("update commerce_charges set lease_until=now()-interval '1 minute' where id=$1",[jobId]);
  await rpc('commerce_recover_expired'); // A queued/running job must never be refunded by bot recovery.
  verify((await status(700)).balance,10000);
  await rpc('commerce_finish_job',jobId,worker,false,null,'AI unavailable');
  verify((await status(700)).balance,20000);
  await rpc('commerce_finish_job',jobId,worker,false,null,'Repeated error');
  verify((await status(700)).balance,20000);
  const orphan=await reserve(700,'referat');
  await query("update commerce_charges set lease_until=now()-interval '1 minute' where id=$1",[orphan.id]);
  await rpc('commerce_recover_expired');verify((await status(700)).balance,20000);
  const restart=randomUUID();await rpc('commerce_enqueue',700,'article',restart,payload);
  await rpc('commerce_claim_job',worker);
  await query("update commerce_jobs set lease_until=now()-interval '1 minute' where id=$1",[restart]);
  const secondWorker=randomUUID();job=await rpc('commerce_claim_job',secondWorker);
  verify(job.attempts,2);
  verify(await rpc('commerce_job_heartbeat',restart,worker),false);
  verify(await rpc('commerce_finish_job',restart,worker,true,{},null),false);
  await rpc('commerce_finish_job',restart,secondWorker,true,{telegram_sent:true},null);
  verify((await status(700)).balance,10000);
  verify((await query("select count(*)::int as n from statistics where user_id=700 and action_type='article'"))[0].n,1);

  await query("insert into statistics(user_id,action_type) values(700,'receipt_hash_legacyhash')");
  await db.exec(migration);
  payment=(await query("insert into payments(user_id,amount,receipt_hash) values(700,10000,'legacyhash') returning id"))[0].id;
  await rejected(rpc('commerce_approve_payment',String(payment)),'duplicate_receipt');
  verify((await status(700)).balance,10000);
  verify((await query('select status from payments where id=$1',[payment]))[0].status,'pending');

  await db.exec('set role anon');
  await rejected(rpc('commerce_status',100),'permission denied');
  await rejected(rpc('commerce_subscribe',100),'permission denied');
  await rejected(query('update users set balance=999999 where telegram_id=100'),'permission denied');
  await rejected(query("insert into payments(user_id,amount,status) values(100,1,'completed')"),'permission denied');
  await db.exec('reset role; set role authenticated');
  await rejected(rpc('commerce_confirm_referral',301),'permission denied');
  await db.exec('reset role');
  console.log(`PASS: ${checks} PostgreSQL commerce assertions (PGlite). Migration applied twice.`);
} finally { await db.close(); }
