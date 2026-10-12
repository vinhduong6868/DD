"""Admin-managed transport; sharing policy and HA token stay unchanged."""
import json,os,tempfile
from pathlib import Path
from transport_profile import profile
class TransportStore:
 def __init__(self,path,defaults):
  self.path=Path(path);self.options={**defaults,**(json.loads(self.path.read_text()) if self.path.exists() else {})}
 def selected(self):return profile(self.options,os.environ.get("DD_DATA_DIR","/data"))
 def public(self):return {k:self.options.get(k,'') for k in ('transport','local_core_url','local_core_sha256','local_core_ip')}
 def save(self,payload):
  if not isinstance(payload,dict) or set(payload)-{'transport','local_core_url','local_core_sha256','local_core_ip'}:raise ValueError('transport_fields_invalid')
  options={**self.options,**payload};profile(options)
  self.path.parent.mkdir(parents=True,exist_ok=True)
  fd,tmp=tempfile.mkstemp(prefix='.transport-',dir=self.path.parent)
  try:
   with os.fdopen(fd,'w') as f:json.dump({k:options.get(k,'') for k in ('transport','local_core_url','local_core_sha256','local_core_ip')},f);f.flush();os.fsync(f.fileno())
   os.replace(tmp,self.path)
  finally:
   if os.path.exists(tmp):os.unlink(tmp)
  self.options=options
