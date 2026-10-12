import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'dd-connector'))
from transport_store import TransportStore
class Tests(unittest.TestCase):
 def test_saved_local_survives_restart_with_empty_cloud_url(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'transport.json';defaults={'transport':'cloud','relay_url':''}
   store=TransportStore(path,defaults);store.save({'transport':'local','local_core_url':'https://192.168.1.2:11507','local_core_sha256':'ab'*32})
   self.assertEqual(TransportStore(path,defaults).selected().mode,'local')
 def test_invalid_save_keeps_previous_configuration(self):
  with tempfile.TemporaryDirectory() as d:
   store=TransportStore(Path(d)/'transport.json',{'relay_url':'wss://example.com'})
   with self.assertRaises(ValueError):store.save({'transport':'local','local_core_url':'https://8.8.8.8','local_core_sha256':'ab'*32})
   self.assertEqual(store.selected().mode,'cloud');self.assertFalse(store.path.exists())
 def test_no_credentials_in_transport_form(self):
  with tempfile.TemporaryDirectory() as d:
   store=TransportStore(Path(d)/'transport.json',{'relay_url':'wss://example.com'})
   with self.assertRaises(ValueError):store.save({'link_secret':'secret'})
