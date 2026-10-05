"""Functional contract checks for Kitch's real local SQLite backend."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"


class SQLitePersistenceTests(unittest.TestCase):
    def run_isolated(self, source: str) -> str:
        with tempfile.TemporaryDirectory() as directory:
            env = os.environ.copy()
            env.update({
                "PYTHONPATH": str(BACKEND),
                "KITCH_DATABASE_BACKEND": "sqlite",
                "KITCH_SQLITE_PATH": str(Path(directory) / "kitch.db"),
                "KITCH_MEMORY_SERVICE": "in_memory",
                "GOOGLE_API_KEY": "test-key",
            })
            completed = subprocess.run(
                [sys.executable, "-c", textwrap.dedent(source)],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )
            return completed.stdout

    def test_empty_database_has_no_seeded_activity_and_bootstraps_named_members(self):
        output = self.run_isolated("""
            from app import supabase_client as db
            assert db.get_household_bootstrap() == {
                'initialized': False, 'members': [], 'timezone': None,
            }
            state = db.bootstrap_household(['Ada', 'Linus'], 'Asia/Kolkata')
            assert [member['name'] for member in state['members']] == ['Ada', 'Linus']
            assert db.canonical_user_name(None) == 'Ada'
            assert db.get_household_profile()['household_size'] == 2
            assert db.get_grocery_cart() == []
            assert db.get_pantry_stock() == []
            assert db.list_recipe_grocery_plans() == []
            assert [row['version'] for row in db.supabase.connect().execute(
                'SELECT version FROM schema_migrations ORDER BY version'
            ).fetchall()] == [1, 2]
            print('ok')
        """)
        self.assertIn("ok", output)

    def test_structured_state_survives_a_new_client_process(self):
        with tempfile.TemporaryDirectory() as directory:
            database = str(Path(directory) / "kitch.db")
            env = os.environ.copy()
            env.update({
                "PYTHONPATH": str(BACKEND),
                "KITCH_DATABASE_BACKEND": "sqlite",
                "KITCH_SQLITE_PATH": database,
                "KITCH_MEMORY_SERVICE": "in_memory",
                "GOOGLE_API_KEY": "test-key",
            })
            first = """
from app import supabase_client as db
db.bootstrap_household(['Ada'], 'UTC')
db.apply_native_grocery_cart_changes([{'action':'add','name':'eggs','amount':12,'unit':'piece'}])
"""
            second = """
from app import supabase_client as db
assert db.get_household_bootstrap()['initialized'] is True
assert db.get_grocery_cart()[0]['name'] == 'eggs'
print('persisted')
"""
            subprocess.run([sys.executable, "-c", first], cwd=ROOT, env=env, check=True)
            completed = subprocess.run(
                [sys.executable, "-c", second], cwd=ROOT, env=env,
                text=True, capture_output=True, check=True,
            )
            self.assertIn("persisted", completed.stdout)

    def test_oauth_state_is_single_use_and_checkout_lease_is_atomic(self):
        output = self.run_isolated("""
            from datetime import datetime, timedelta, timezone
            from app import supabase_client as db
            db.bootstrap_household(['Ada'], 'UTC')
            db.create_provider_oauth_flow({
                'provider':'swiggy_instamart', 'provider_environment':'local',
                'state_hash':'state', 'code_verifier_ciphertext':'cipher',
                'client_id':'client', 'redirect_uri':'http://localhost:8000/callback',
                'expires_at':(datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat(),
            })
            assert db.consume_provider_oauth_flow('state') is not None
            assert db.consume_provider_oauth_flow('state') is None
            operation = '00000000-0000-0000-0000-000000000123'
            assert db.claim_provider_checkout_operation(operation, 'swiggy_instamart', 'local')
            assert not db.claim_provider_checkout_operation(
                '00000000-0000-0000-0000-000000000456', 'swiggy_instamart', 'local'
            )
            assert db.release_provider_checkout_operation(operation, 'swiggy_instamart', 'local')
            print('safe')
        """)
        self.assertIn("safe", output)

    def test_local_provider_key_is_created_once_and_can_decrypt_after_reload(self):
        output = self.run_isolated("""
            import os
            from pathlib import Path
            import tempfile
            from app.providers import credential_crypto

            key_path = Path(tempfile.mkdtemp()) / 'provider.key'
            os.environ.pop('PROVIDER_CREDENTIAL_ENCRYPTION_KEY', None)
            os.environ['KITCH_LOCAL_PROVIDER_KEY_PATH'] = str(key_path)
            ciphertext = credential_crypto.encrypt_provider_secret('provider-token')
            original_key = key_path.read_bytes()
            assert credential_crypto.decrypt_provider_secret(ciphertext) == 'provider-token'
            assert key_path.read_bytes() == original_key
            assert credential_crypto.decrypt_provider_secret(ciphertext) == 'provider-token'
            print('stable-key')
        """)
        self.assertIn("stable-key", output)

    def test_failed_pantry_batch_rolls_back_rows_and_revision(self):
        output = self.run_isolated("""
            from app import supabase_client as db

            db.bootstrap_household(['Ada'], 'UTC')
            profile_id = db.get_household_profile_id()
            db.supabase.rpc('apply_pantry_inventory_change', {
                'p_profile_id': profile_id,
                'p_expected_revision': 0,
                'p_mode': 'patch',
                'p_items': [{'action':'add','name':'milk','amount':2,'unit':'litre'}],
            }).execute()
            try:
                db.supabase.rpc('apply_pantry_inventory_change', {
                    'p_profile_id': profile_id,
                    'p_expected_revision': 1,
                    'p_mode': 'patch',
                    'p_items': [
                        {'action':'set','name':'milk','amount':5,'unit':'litre'},
                        {'action':'remove','name':'not in pantry'},
                    ],
                }).execute()
                raise AssertionError('Expected the batch to fail')
            except ValueError:
                pass
            assert db.get_pantry_state()['revision'] == 1
            pantry = db.get_pantry_stock()
            assert len(pantry) == 1 and pantry[0]['name'] == 'milk'
            assert pantry[0]['amount'] == 2
            print('rolled-back')
        """)
        self.assertIn("rolled-back", output)

    def test_missing_local_key_is_not_recreated_over_encrypted_provider_state(self):
        output = self.run_isolated("""
            import os
            from datetime import datetime, timedelta, timezone
            from pathlib import Path
            import tempfile
            from app import supabase_client as db
            from app.providers import credential_crypto

            db.bootstrap_household(['Ada'], 'UTC')
            db.save_provider_connection('swiggy_instamart', 'local', {
                'access_token_ciphertext':'already-encrypted',
                'expires_at':(
                    datetime.now(timezone.utc) + timedelta(days=1)
                ).isoformat(),
            })
            os.environ.pop('PROVIDER_CREDENTIAL_ENCRYPTION_KEY', None)
            key_path = Path(tempfile.mkdtemp()) / 'missing.key'
            os.environ['KITCH_LOCAL_PROVIDER_KEY_PATH'] = str(key_path)
            try:
                credential_crypto.encrypt_provider_secret('new-token')
                raise AssertionError('Expected missing-key protection')
            except credential_crypto.ProviderCredentialConfigurationError:
                pass
            assert not key_path.exists()
            print('protected')
        """)
        self.assertIn("protected", output)


if __name__ == "__main__":
    unittest.main()
