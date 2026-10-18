// Real PostgreSQL/PLpgSQL tests for the shared AI usage caps; no Supabase connection.
// Install @electric-sql/pglite@0.3.14 in a disposable directory, then run:
// KITCH_TEST_PGLITE_MODULE=/absolute/path/node_modules/@electric-sql/pglite/dist/index.js \
//   node --test test/ai_quota_sql.test.mjs
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import { pathToFileURL } from 'node:url';

const modulePath = process.env.KITCH_TEST_PGLITE_MODULE;
const PGlite = modulePath ? (await import(pathToFileURL(modulePath).href)).PGlite : null;
const skip = PGlite ? false : 'set KITCH_TEST_PGLITE_MODULE to a disposable PGlite installation';
const database = new URL('../backend/database/', import.meta.url);

// pg_cron is not available in PGlite; only the scheduler setup is left out.
const withoutCron = sql => sql
  .replace(/CREATE EXTENSION IF NOT EXISTS pg_cron;[\s\S]*?END \$\$;/g, '');

async function setup(t, mode) {
  const db = new PGlite();
  t.after(() => db.close());
  await db.exec('CREATE ROLE anon; CREATE ROLE authenticated; CREATE ROLE service_role BYPASSRLS;');
  let schema = await readFile(new URL('supabase_schema.sql', database), 'utf8');
  schema = schema.replace('CREATE EXTENSION IF NOT EXISTS "pgcrypto";', '')
    .split('CREATE EXTENSION IF NOT EXISTS pg_cron;')[0];
  await db.exec(schema);
  if (mode === 'upgrade') {
    const migration = await readFile(new URL('migrations/20261023_ai_usage_quota.sql', database), 'utf8');
    await db.exec(withoutCron(migration).replace("NOTIFY pgrst, 'reload schema';", ''));
  }
  await db.exec('SET ROLE service_role');
  return db;
}

const consume = async (db, buckets, limits, windows) => (await db.query(
  'SELECT public.consume_ai_quota($1::text[], $2::int[], $3::int[]) AS value', [buckets, limits, windows],
)).rows[0].value;
const count = async (db, bucket) => (await db.query(
  'SELECT COALESCE(sum(request_count), 0)::int AS n FROM ai_usage_windows WHERE bucket = $1', [bucket],
)).rows[0].n;

for (const mode of ['fresh', 'upgrade']) {
  test(`${mode}: counts up to the limit, then refuses without using quota`, { skip }, async t => {
    const db = await setup(t, mode);
    for (let i = 0; i < 3; i++) assert.deepEqual(await consume(db, ['account:a'], [3], [600]), { allowed: true });
    const refused = await consume(db, ['account:a'], [3], [600]);
    assert.equal(refused.allowed, false);
    assert.ok(refused.retry_after >= 1 && refused.retry_after <= 600);
    assert.equal(await count(db, 'account:a'), 3);
  });

  test(`${mode}: one full bucket refuses the request for every bucket`, { skip }, async t => {
    const db = await setup(t, mode);
    const buckets = ['account:a', 'household:h', 'ip:x'];
    assert.equal((await consume(db, buckets, [10, 1, 10], [600, 600, 600])).allowed, true);
    assert.equal((await consume(db, buckets, [10, 1, 10], [600, 600, 600])).allowed, false);
    // The refused request left no trace in the buckets that still had room.
    assert.equal(await count(db, 'account:a'), 1);
    assert.equal(await count(db, 'ip:x'), 1);
    // A different account in another household on the same IP is unaffected by h.
    assert.equal((await consume(db, ['account:b', 'household:g', 'ip:x'], [10, 1, 10], [600, 600, 600])).allowed, true);
  });

  test(`${mode}: the same bucket keeps separate 10-minute and daily windows`, { skip }, async t => {
    const db = await setup(t, mode);
    assert.equal((await consume(db, ['account:a', 'account:a'], [5, 1], [600, 86400])).allowed, true);
    const refused = await consume(db, ['account:a', 'account:a'], [5, 1], [600, 86400]);
    assert.equal(refused.allowed, false);
    assert.ok(refused.retry_after > 0 && refused.retry_after <= 86400);
  });

  test(`${mode}: mismatched or empty arguments are rejected`, { skip }, async t => {
    const db = await setup(t, mode);
    await assert.rejects(consume(db, ['account:a'], [1, 2], [600]), /quota_arguments_invalid/);
    await assert.rejects(consume(db, [], [], []), /quota_arguments_invalid/);
  });

  test(`${mode}: counters are private to the backend`, { skip }, async t => {
    const db = await setup(t, mode);
    const rls = (await db.query("SELECT relrowsecurity FROM pg_class WHERE relname = 'ai_usage_windows'")).rows[0];
    assert.equal(rls.relrowsecurity, true);
    for (const role of ['anon', 'authenticated']) {
      const grants = (await db.query(
        "SELECT has_table_privilege($1, 'public.ai_usage_windows', 'SELECT') AS t, has_function_privilege($1, 'public.consume_ai_quota(text[],integer[],integer[])', 'EXECUTE') AS f",
        [role],
      )).rows[0];
      assert.deepEqual(grants, { t: false, f: false });
    }
  });
}
