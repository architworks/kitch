// Real PostgreSQL/PLpgSQL regression tests; no Supabase connection or app dependency.
// Install @electric-sql/pglite@0.3.14 in a disposable directory, then run:
// KITCH_TEST_PGLITE_MODULE=/absolute/path/node_modules/@electric-sql/pglite/dist/index.js \
//   node --test test/household_membership_sql.test.mjs
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import { pathToFileURL } from 'node:url';

// Without a PGlite installation the tests are reported as skipped, not failed.
const modulePath = process.env.KITCH_TEST_PGLITE_MODULE;
const PGlite = modulePath ? (await import(pathToFileURL(modulePath).href)).PGlite : null;
const skip = PGlite ? false : 'set KITCH_TEST_PGLITE_MODULE to a disposable PGlite installation';
const database = new URL('../backend/database/', import.meta.url);
const patchName = '20261022_revoke_invite_on_member_removal.sql';

async function setup(t, mode) {
  const db = new PGlite();
  t.after(() => db.close());
  await db.exec('CREATE ROLE anon; CREATE ROLE authenticated; CREATE ROLE service_role BYPASSRLS;');
  // Only the unrelated cron scheduler/extension installation is omitted. Tables,
  // constraints, RLS, grants and function bodies execute from the real schema.
  let schema = await readFile(new URL('supabase_schema.sql', database), 'utf8');
  schema = schema.replace('CREATE EXTENSION IF NOT EXISTS "pgcrypto";', '')
    .split('CREATE EXTENSION IF NOT EXISTS pg_cron;')[0];
  await db.exec(schema);
  if (mode === 'upgrade') {
    await db.exec(await readFile(new URL('migrations/20261021_member_removal_and_unique_names.sql', database), 'utf8'));
    await db.exec(await readFile(new URL(`migrations/${patchName}`, database), 'utf8'));
  }
  await db.exec('SET ROLE service_role');
  const owner = await rpc(db, 'ensure_google_household', ['owner', 'owner@example.test', 'Alex', 'UTC', false]);
  await invite(db, owner.household_id, 'old-invite');
  return { db, owner };
}

async function rpc(db, name, args) {
  const result = await db.query(`SELECT public.${name}(${args.map((_, i) => `$${i + 1}`).join(',')}) AS value`, args);
  return result.rows[0].value;
}
async function invite(db, household, token) {
  await db.query("UPDATE households SET invite_token_hash=$1, invite_expires_at=now()+interval '7 days' WHERE id=$2", [token, household]);
}
const join = (db, subject, token = 'old-invite', profile = null, name = 'Alex', email = `${subject}@example.test`) =>
  rpc(db, 'join_household_with_invite', [subject, email, name, token, profile]);
const remove = (db, profile, subject = 'owner') => rpc(db, 'remove_household_member', [subject, profile]);
async function tokenFor(db, household) {
  return (await db.query('SELECT invite_token_hash FROM households WHERE id=$1', [household])).rows[0].invite_token_hash;
}

for (const mode of ['upgrade', 'fresh']) {
  test(`${mode}: removal revokes the old link, rejects both replay forms, permits a fresh invitation`, { skip }, async t => {
    const { db, owner } = await setup(t, mode);
    const member = await join(db, 'member');
    const spare = (await db.query("INSERT INTO profiles(household_id,full_name) VALUES ($1,'Unclaimed') RETURNING id", [owner.household_id])).rows[0].id;
    await db.query("INSERT INTO macro_diary(profile_id,meal_name,meal_type,calories) VALUES ($1,'Test meal','lunch',123)", [member.profile_id]);
    await remove(db, member.profile_id);
    assert.equal(await rpc(db, 'household_account_context', ['member']), null);
    assert.equal((await db.query('SELECT count(*)::int AS n FROM macro_diary WHERE profile_id=$1', [member.profile_id])).rows[0].n, 0);
    assert.equal(await tokenFor(db, owner.household_id), null);
    // Same predicate as public invite preview: the old link no longer previews.
    assert.equal((await db.query("SELECT id FROM households WHERE invite_token_hash='old-invite' AND invite_expires_at>now()")).rows.length, 0);
    await assert.rejects(join(db, 'member'), /invite_invalid/);
    await assert.rejects(join(db, 'member', 'old-invite', spare), /invite_invalid/);
    await invite(db, owner.household_id, 'fresh-invite');
    const rejoined = await join(db, 'member', 'fresh-invite', spare);
    assert.equal(rejoined.profile_id, spare);
    assert.equal(rejoined.role, 'member');
  });

  test(`${mode}: unclaimed removal preserves invitation; denied removals have no side effects`, { skip }, async t => {
    const { db, owner } = await setup(t, mode);
    const member = await join(db, 'member');
    const foreign = await rpc(db, 'ensure_google_household', ['foreign', 'foreign@example.test', 'Alex', 'UTC', false]);
    await assert.rejects(remove(db, owner.profile_id), /cannot_remove_self/);
    await assert.rejects(remove(db, owner.profile_id, 'member'), /owner_required/);
    await assert.rejects(remove(db, foreign.profile_id), /member_not_found/);
    assert.equal(await tokenFor(db, owner.household_id), 'old-invite');
    const spare = (await db.query("INSERT INTO profiles(household_id,full_name) VALUES ($1,'Unclaimed') RETURNING id", [owner.household_id])).rows[0].id;
    const result = await remove(db, spare);
    assert.equal(result.had_account, false);
    assert.equal(await tokenFor(db, owner.household_id), 'old-invite');
    assert.equal((await join(db, 'new-member')).household_id, owner.household_id);
    assert.equal((await rpc(db, 'household_account_context', ['member'])).profile_id, member.profile_id);
  });

  test(`${mode}: former owner removal retains shared pantry and clears personal nutrition`, { skip }, async t => {
    const { db, owner } = await setup(t, mode);
    const member = await join(db, 'member');
    await db.query("INSERT INTO pantry_stock(profile_id,ingredient_name,amount) VALUES ($1,'Shared oats',1)", [owner.profile_id]);
    await db.query("INSERT INTO macro_diary(profile_id,meal_name,meal_type,calories) VALUES ($1,'Test meal','lunch',123)", [owner.profile_id]);
    await rpc(db, 'transfer_household_ownership', ['owner', member.profile_id]);
    const result = await remove(db, owner.profile_id, 'member');
    assert.equal(result.profile_removed, false);
    assert.equal(await tokenFor(db, owner.household_id), null);
    assert.equal((await db.query('SELECT count(*)::int AS n FROM pantry_stock WHERE profile_id=$1', [owner.profile_id])).rows[0].n, 1);
    assert.equal((await db.query('SELECT count(*)::int AS n FROM macro_diary WHERE profile_id=$1', [owner.profile_id])).rows[0].n, 0);
    await assert.rejects(remove(db, owner.profile_id, 'member'), /household_anchor/);
  });

  test(`${mode}: former owner can leave voluntarily without touching shared data`, { skip }, async t => {
    const { db, owner } = await setup(t, mode);
    const member = await join(db, 'member');
    await db.query("INSERT INTO pantry_stock(profile_id,ingredient_name,amount) VALUES ($1,'Shared oats',1)", [owner.profile_id]);
    await db.query("INSERT INTO macro_diary(profile_id,meal_name,meal_type,calories) VALUES ($1,'Test meal','lunch',123)", [owner.profile_id]);
    await rpc(db, 'transfer_household_ownership', ['owner', member.profile_id]);
    assert.equal(await rpc(db, 'delete_household_account', ['owner']), true);
    assert.equal(await rpc(db, 'household_account_context', ['owner']), null);
    assert.equal((await db.query('SELECT count(*)::int AS n FROM pantry_stock WHERE profile_id=$1', [owner.profile_id])).rows[0].n, 1);
    assert.equal((await db.query('SELECT count(*)::int AS n FROM macro_diary WHERE profile_id=$1', [owner.profile_id])).rows[0].n, 0);
    assert.equal((await rpc(db, 'household_account_context', ['member'])).role, 'owner');
  });

  test(`${mode}: duplicate joins receive distinct names and nutrition remains profile-scoped after rename`, { skip }, async t => {
    const { db, owner } = await setup(t, mode);
    const first = await join(db, 'first', 'old-invite', null, 'Alex', 'sam@one.test');
    const second = await join(db, 'second', 'old-invite', null, 'Alex', 'sam@two.test');
    assert.equal(first.members.find(m => m.id === first.profile_id).name, 'Alex (sam)');
    assert.equal(second.members.find(m => m.id === second.profile_id).name, 'Alex (sam 2)');
    assert.notEqual(first.profile_id, second.profile_id);
    await assert.rejects(db.query('UPDATE profiles SET full_name=$1 WHERE id=$2', ['  aLeX  ', second.profile_id]), /profiles_household_name_unique/);
    await db.query("INSERT INTO macro_diary(profile_id,meal_name,meal_type,calories) VALUES ($1,'First meal','lunch',111),($2,'Second meal','dinner',222)", [first.profile_id, second.profile_id]);
    await db.query("UPDATE profiles SET full_name='Renamed' WHERE id=$1", [second.profile_id]);
    assert.deepEqual((await db.query('SELECT calories FROM macro_diary WHERE profile_id=$1', [first.profile_id])).rows, [{calories:111}]);
    assert.deepEqual((await db.query('SELECT calories FROM macro_diary WHERE profile_id=$1', [second.profile_id])).rows, [{calories:222}]);
    const other = await rpc(db, 'ensure_google_household', ['other', 'other@example.test', 'Alex', 'UTC', false]);
    assert.notEqual(other.household_id, owner.household_id);
  });

  test(`${mode}: setup de-duplicates ordinary names; distinct Unicode names retain separate profiles`, { skip }, async t => {
    const { db, owner } = await setup(t, mode);
    const result = await rpc(db, 'complete_household_setup', ['owner', 'Alex', ['alex', ' Sam ', 'sAM', 'Straße', 'Strasse'], 4]);
    assert.deepEqual(result.members.map(m => m.name), ['Alex', 'Sam', 'Straße', 'Strasse']);
    assert.equal(new Set(result.members.map(m => m.id)).size, 4);
    const sam = result.members.find(m => m.name === 'Sam');
    const claimed = await join(db, 'sam', 'old-invite', sam.id);
    assert.equal(claimed.profile_id, sam.id);
    assert.equal(claimed.household_id, owner.household_id);
    await assert.rejects(join(db, 'second-sam', 'old-invite', sam.id), /profile_unavailable/);
  });

  test(`${mode}: public roles cannot invoke member removal or joining`, { skip }, async t => {
    const { db, owner } = await setup(t, mode);
    for (const role of ['anon', 'authenticated']) {
      await db.exec(`RESET ROLE; SET ROLE ${role}`);
      await assert.rejects(remove(db, owner.profile_id), /permission denied for function remove_household_member/);
      await assert.rejects(join(db, 'visitor'), /permission denied for function join_household_with_invite/);
    }
  });
}
