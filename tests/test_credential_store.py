import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'dd-connector'))
from credential_store import migrate_legacy, read_credentials, write_credentials
from transport_profile import profile

class CredentialTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root=Path(self.directory.name)
        self.options={'transport':'local','local_core_url':'https://192.168.1.2:11507','local_core_sha256':'ab'*32}
        self.first=profile(self.options,self.root)
        self.second=profile({**self.options,'local_core_sha256':'cd'*32},self.root)
        self.secret={'link_id':'test-id','link_secret':'test-only-secret'}
    def test_different_core_never_receives_previous_credentials(self):
        write_credentials(self.first,self.secret)
        self.assertIsNone(read_credentials(self.second))
        self.assertEqual(read_credentials(self.first),self.secret)
    def test_copied_file_wrong_audience_rejected(self):
        write_credentials(self.first,self.secret)
        self.second.credentials_path.write_bytes(self.first.credentials_path.read_bytes())
        with self.assertRaisesRegex(ValueError,'audience'):read_credentials(self.second)
    def test_same_certificate_dns_ip_change_retains_link(self):
        write_credentials(self.first,self.secret)
        by_ip=profile({**self.options,'local_core_url':'','local_core_ip':'192.168.1.2'},self.root)
        self.assertEqual(read_credentials(by_ip),self.secret)
    def test_restart_retains_link_and_private_permissions(self):
        write_credentials(self.first,self.secret)
        self.assertEqual(read_credentials(profile(self.options,self.root)),self.secret)
        self.assertEqual(os.stat(self.first.credentials_path).st_mode & 0o777,0o600)
    def test_legacy_migrated_once_before_core_change(self):
        legacy=self.root/'local-link.json';legacy.write_text(json.dumps(self.secret))
        migrate_legacy(self.first)
        self.assertFalse(legacy.exists())
        migrate_legacy(self.second)
        self.assertIsNone(read_credentials(self.second))
        self.assertEqual(read_credentials(self.first),self.secret)
    def test_cloud_keeps_existing_format_and_separate_file(self):
        cloud=profile({'relay_url':'wss://example.com/relay'},self.root)
        write_credentials(cloud,self.secret)
        self.assertEqual(read_credentials(cloud),self.secret)
        self.assertIsNone(read_credentials(self.first))
    def test_invalid_secret_never_persisted(self):
        with self.assertRaises(ValueError):write_credentials(self.first,{'link_id':'','link_secret':'x'})
        self.assertFalse(self.first.credentials_path.exists())
    def test_legacy_wrong_audience_not_migrated(self):
        (self.root/'local-link.json').write_text(json.dumps({**self.secret,'core_sha256':'cd'*32}))
        with self.assertRaises(ValueError):migrate_legacy(self.first)
        self.assertFalse(self.first.credentials_path.exists())
