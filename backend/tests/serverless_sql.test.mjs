import assert from 'node:assert/strict';
import { PGlite } from '@electric-sql/pglite';
import { readFile } from 'node:fs/promises';
import { randomUUID } from 'node:crypto';

const db = new PGlite();
await db.exec('create role anon; create role authenticated; create role service_role bypassrls;');
for (const file of ['20261017_commerce.sql', '20261018_serverless.sql', '20261022_referral_only.sql']) {
  await db.exec(await readFile(new URL('../supabase/migrations/' + file, import.meta.url), 'utf8'));
}
const rpc = async (name, values, signature) => (await db.query(
  `select ${name}(${values.map((_, i) => '$' + (i + 1) + (signature?.[i] ? '::' + signature[i] : '')).join(',')}) as result`, values)).rows[0].result;
const registered = async id => rpc('commerce_register', [id, 'Test', null, null, null]);
await registered(2000);
const first = await rpc('orzu_bot_begin_update', [2000, 'update:100']);
assert.deepEqual(first.session, {});
assert.equal((await rpc('orzu_bot_begin_update', [2000, 'update:100'])).busy, true);
assert.equal((await rpc('orzu_bot_begin_update', [2000, 'update:101'])).busy, true);
assert.equal(await rpc('orzu_bot_finish_update', [2000, 'wrong-key', '{}', true]), false);
assert.equal(await rpc('orzu_bot_finish_update', [2000, 'update:100', '{"step":"payment_receipt"}', true]), true);
assert.equal((await rpc('orzu_bot_begin_update', [2000, 'update:100'])).duplicate, true);
assert.equal((await rpc('orzu_bot_begin_update', [2000, 'update:101'])).session.step, 'payment_receipt');
await rpc('orzu_bot_finish_update', [2000, 'update:101', '{}', false]);
assert.equal((await rpc('orzu_bot_begin_update', [2000, 'update:101'])).session.step, 'payment_receipt');
await db.exec("update orzu_bot_sessions set lock_until = now() - interval '1 minute' where user_id = 2000");
assert.equal((await rpc('orzu_bot_begin_update', [2000, 'update:102'])).busy, undefined);
await rpc('orzu_bot_finish_update', [2000, 'update:102', '{}', true]);

// Every confirmation awards one shared credit; a course consumes two once.
for (let i = 2001; i <= 2005; i++) {
  await rpc('commerce_register', [i, 'Friend', null, null, 2000]);
  await rpc('commerce_confirm_referral', [i]);
}
const courseId = randomUUID(), payload = { tema: 'History', plan: 'Plan', send_to_telegram: true };
const course = await rpc('commerce_enqueue', [2000, 'course', courseId, payload]);
assert.equal(course.amount, 0); assert.equal(course.source, 'referral');
assert.equal((await rpc('commerce_enqueue', [2000, 'course', courseId, payload])).created, false);
await assert.rejects(rpc('commerce_enqueue', [2000, 'course', courseId, { ...payload, tema: 'Changed' }]), /request_conflict/);
assert.equal((await db.query('select count(*)::int as total from commerce_jobs')).rows[0].total, 1);
const worker = randomUUID();
await rpc('commerce_claim_job', [worker]);
assert.equal(await rpc('commerce_finish_job', [courseId, worker, false, null, 'AI failure']), true);
assert.equal((await rpc('commerce_status', [2000])).course_credits, 2);

await db.query('update users set balance = 8000 where telegram_id = $1', [2000]);
const refId = randomUUID();
await rpc('commerce_enqueue', [2000, 'referat', refId, payload]);
assert.equal(Number((await rpc('commerce_status', [2000])).balance), 8000);
assert.equal((await rpc('commerce_status', [2000])).referral_credits, 5);
await rpc('commerce_claim_job', [worker]);
await rpc('commerce_finish_job', [refId, worker, false, null, 'AI failure']);
assert.equal(Number((await rpc('commerce_status', [2000])).balance), 8000);
await rpc('commerce_finish_job', [refId, worker, false, null, 'Retry']);
assert.equal(Number((await rpc('commerce_status', [2000])).balance), 8000);

// Reapplying the additive migration preserves all paid/referral data.
await db.exec(await readFile(new URL('../supabase/migrations/20261018_serverless.sql', import.meta.url), 'utf8'));
assert.equal((await rpc('commerce_status', [2000])).course_credits, 2);
await db.exec('set role anon');
await assert.rejects(rpc('orzu_bot_begin_update', [2000, 'forged']), /permission denied/);
await assert.rejects(db.query('select * from orzu_bot_sessions'), /permission denied/);
await db.exec('reset role');
await db.close();
console.log('Serverless SQL: leases, redelivery, queued course/refund, referat/refund and permissions passed.');
