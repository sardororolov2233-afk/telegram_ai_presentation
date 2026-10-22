import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {randomUUID} from 'node:crypto';
import {PGlite} from '@electric-sql/pglite';

const db = new PGlite();
let checks = 0;
const verify = (actual, expected) => {assert.deepEqual(actual, expected); checks++;};
const query = async (sql, values = []) => (await db.query(sql, values)).rows;
const rpc = async (name, ...values) => (await query(`select ${name}(${values.map((_, i) => '$' + (i + 1)).join(',')}) as result`, values))[0].result;
const register = (id, ref = null) => rpc('commerce_register', id, 'Student', null, null, ref);
const status = id => rpc('commerce_status', id);
const reserve = (id, service, key = randomUUID()) => rpc('commerce_reserve', id, service, key);
const finish = (id, key, success) => rpc('commerce_finish', id, key, success);
const rejected = async (promise, code) => {await assert.rejects(promise, error => error.message.includes(code)); checks++;};
async function invite(ref, friend) {await register(friend, ref); return rpc('commerce_confirm_referral', friend);}

try {
  await db.exec('create role anon;create role authenticated;create role service_role bypassrls;');
  await db.exec(await readFile(new URL('../supabase/migrations/20261017_commerce.sql', import.meta.url), 'utf8'));
  const migration = await readFile(new URL('../supabase/migrations/20261022_referral_only.sql', import.meta.url), 'utf8');
  // Real upgrade: preserve five-referral rewards, unawarded friends and pending refunds.
  await register(1);
  for (let id = 2; id <= 7; id++) await invite(1, id);
  const legacyCourse = await reserve(1, 'course');
  await query('update users set balance=90000 where telegram_id=1');
  await rpc('commerce_subscribe', 1);
  await db.exec(migration);
  verify((await status(1)).referral_credits, 6); // five unused presentation rewards + sixth friend
  verify((await status(1)).balance, 65000); // money remains historical; no conversion to credits
  verify((await status(1)).subscription_active, false);
  await finish(1, legacyCourse.id, false);
  await finish(1, legacyCourse.id, false);
  verify((await status(1)).referral_credits, 8);
  await db.exec(migration);
  verify((await status(1)).referral_credits, 8); // never duplicate upgrade credits

  await register(100);
  await register(101); await register(101, 100);
  verify((await rpc('commerce_confirm_referral', 101)).awarded, false);
  await register(102, 102);
  verify((await rpc('commerce_confirm_referral', 102)).awarded, false);
  await register(103, 999999);
  verify((await rpc('commerce_confirm_referral', 103)).awarded, false);
  await register(200, 100);
  await register(201);
  await register(200, 201); // attribution cannot be changed
  verify((await status(100)).referral_credits, 0);
  verify((await rpc('commerce_confirm_referral', 200)).credits_awarded, 1);
  await Promise.all(Array.from({length: 10}, () => rpc('commerce_confirm_referral', 200)));
  verify((await status(100)).referral_credits, 1);
  verify((await status(201)).referral_credits, 0);
  await rejected(reserve(100, 'course'), 'insufficient_referral_credits');
  verify((await status(100)).referral_credits, 1);
  await invite(100, 202);
  verify((await status(100)).course_credits, 1);
  const course = await reserve(100, 'course');
  verify(course.credit_units, 2); verify(course.amount, 0);
  verify((await status(100)).referral_credits, 0);
  verify((await reserve(100, 'course', course.id)).created, false);
  await rejected(reserve(100, 'design', course.id), 'request_conflict');
  await rejected(reserve(201, 'course', course.id), 'request_conflict');
  await finish(100, course.id, false); await finish(100, course.id, false);
  verify((await status(100)).referral_credits, 2);
  for (const service of ['presentation', 'design']) {
    const charge = await reserve(100, service);
    verify(charge.credit_units, 1);
    await finish(100, charge.id, true);
    await finish(100, charge.id, false); // delivered work cannot be refunded by a later replay
  }
  verify((await status(100)).referral_credits, 0);
  await query('update users set balance=1000000 where telegram_id=100');
  for (const service of ['presentation', 'design', 'course']) await rejected(reserve(100, service), 'insufficient_referral_credits');
  await rejected(rpc('commerce_subscribe', 100), 'subscriptions_disabled');
  const payment = (await query("insert into payments(user_id,amount,purpose) values(100,25000,'subscription') returning id"))[0];
  await rejected(rpc('commerce_approve_payment', String(payment.id)), 'payments_disabled');
  verify((await status(100)).balance, 1000000);
  for (const service of ['referat', 'article', 'obyektivka']) {
    const charge = await reserve(100, service);
    verify(charge.source, 'free'); verify(charge.amount, 0); verify(charge.credit_units, 0);
    await finish(100, charge.id, true);
  }
  verify((await status(100)).referral_credits, 0);
  verify((await status(100)).balance, 1000000);

  await invite(100, 203);
  const attempts = await Promise.allSettled([reserve(100, 'design'), reserve(100, 'presentation')]);
  verify(attempts.filter(result => result.status === 'fulfilled').length, 1);
  verify((await status(100)).referral_credits, 0);
  const accepted = attempts.find(result => result.status === 'fulfilled').value;
  await query("update commerce_charges set lease_until=now()-interval '1 minute' where id=$1", [accepted.id]);
  await rpc('commerce_recover_expired'); await rpc('commerce_recover_expired');
  verify((await status(100)).referral_credits, 1);

  const jobId = randomUUID(), worker = randomUUID();
  const payload = {topic: 'History', user_images: [], image_hashes: []};
  await rpc('commerce_enqueue', 100, 'presentation', jobId, payload);
  await rpc('commerce_enqueue', 100, 'presentation', jobId, payload);
  verify((await status(100)).referral_credits, 0);
  await rejected(rpc('commerce_enqueue', 100, 'presentation', jobId, {...payload, topic: 'Other'}), 'request_conflict');
  await rpc('commerce_claim_job', worker);
  await query("update commerce_jobs set lease_until=now()-interval '1 minute' where id=$1", [jobId]);
  const nextWorker = randomUUID();
  verify((await rpc('commerce_claim_job', nextWorker)).attempts, 2);
  verify(await rpc('commerce_finish_job', jobId, worker, false, null, 'stale worker'), false);
  await rpc('commerce_finish_job', jobId, nextWorker, false, null, 'AI unavailable');
  await rpc('commerce_finish_job', jobId, nextWorker, false, null, 'replay');
  verify((await status(100)).referral_credits, 1);
  await db.exec(migration);
  verify((await status(100)).referral_credits, 1);
  await db.exec('set role anon');
  await rejected(rpc('commerce_confirm_referral', 200), 'permission denied');
  await rejected(rpc('commerce_reserve', 100, 'design', randomUUID()), 'permission denied');
  await rejected(query('update commerce_accounts set referral_credits=999 where user_id=100'), 'permission denied');
  await db.exec('reset role;set role authenticated');
  await rejected(rpc('commerce_policy'), 'permission denied');
  await db.exec('reset role');
  console.log(`PASS: ${checks} referral-only PostgreSQL assertions; legacy upgrade and repeated migration verified.`);
} finally {await db.close();}
