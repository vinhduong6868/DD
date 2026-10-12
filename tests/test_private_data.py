import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'dd-connector'))
from private_data import migrate_private_data
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.source=Path(self.tmp.name)/'data';self.source.mkdir();self.dest=Path(self.tmp.name)/'config'
 def test_only_private_connector_state_transferred(self):
  for name in ('transport.json','shared_entities.json','link.json','options.json','supervisor_token'):(self.source/name).write_text('{}')
  migrate_private_data(self.source,self.dest)
  self.assertEqual({p.name for p in self.dest.iterdir()},{'transport.json','shared_entities.json','link.json'})
 def test_restart_does_not_overwrite_new_state(self):
  (self.source/'transport.json').write_text('old');migrate_private_data(self.source,self.dest)
  (self.dest/'transport.json').write_text('new');migrate_private_data(self.source,self.dest)
  self.assertEqual((self.dest/'transport.json').read_text(),'new')
 def test_legacy_not_resurrected_after_migration(self):
  (self.source/'local-link.json').write_text('old');self.dest.mkdir()
  (self.dest/'local-link.migrated.json').write_text('bound')
  migrate_private_data(self.source,self.dest)
  self.assertFalse((self.dest/'local-link.json').exists())
 def test_symbolic_link_rejected(self):
  (self.source/'link.json').symlink_to('/etc/passwd')
  with self.assertRaises(ValueError):migrate_private_data(self.source,self.dest)
 def test_bound_credentials_permission(self):
  name='local-link-'+'ab'*32+'.json';(self.source/name).write_text('{}')
  migrate_private_data(self.source,self.dest)
  self.assertEqual((self.dest/name).stat().st_mode & 0o777,0o600)
