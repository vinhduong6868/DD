import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'dd-connector'))
from transport_profile import profile

class Tests(unittest.TestCase):
    def test_cloud_existing_default(self):
        p = profile({'relay_url': 'wss://example.com/relay'})
        self.assertEqual(p.credentials_path.name, 'link.json')
    def test_local_separate_credentials(self):
        p = profile({'transport': 'local', 'local_core_url': 'https://192.168.68.63:11507', 'local_core_sha256': 'ab' * 32})
        self.assertEqual(p.url, 'wss://192.168.68.63:11507/dd-connector/local')
        self.assertEqual(p.credentials_path.name, 'local-link.json')
    def test_tls_pin_required(self):
        with self.assertRaises(ValueError):
            profile({'transport': 'local', 'local_core_url': 'https://192.168.1.2'})
    def test_invalid_addresses(self):
        for url in ['http://192.168.1.2', 'https://user:secret@192.168.1.2', 'https://192.168.1.2/path', 'https://192.168.1.2?key=x', 'https://127.0.0.1', 'https://0.0.0.0', 'https://8.8.8.8', 'https://224.0.0.1', 'https://169.254.1.2']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                profile({'transport': 'local', 'local_core_url': url, 'local_core_sha256': 'ab' * 32})
    def test_no_automatic_fallback(self):
        with self.assertRaises(ValueError):
            profile({'transport': 'auto', 'relay_url': 'wss://example.com'})
