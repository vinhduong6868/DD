import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"dd-connector"))
from command_log import CommandLog

class Tests(unittest.TestCase):
 def test_bounded(self):
  j=CommandLog(2)
  for i in range(3):j.record(str(i),'received')
  self.assertEqual([x['command_id'] for x in j.listing()['items']],['2','1'])
 def test_expiry(self):
  now=[1000];j=CommandLog(ttl=60,clock=lambda:now[0]);j.record('id','received');now[0]+=61
  self.assertEqual(j.listing()['count'],0)
 def test_no_exception_text_or_url(self):
  j=CommandLog();j.record('id','failed',reason='Bearer secret',error_type='http://user:password@host')
  self.assertNotIn('secret',str(j.listing()));self.assertNotIn('password',str(j.listing()))
 def test_copies(self):
  j=CommandLog();j.record('id','received');j.listing()['items'][0]['stage']='wrong'
  self.assertEqual(j.listing()['items'][0]['stage'],'received')
 def test_ack_not_confirmation(self):
  j=CommandLog();j.record('id','ha_accepted');self.assertEqual(j.listing()['items'][0]['stage'],'ha_accepted')
 def test_error_metadata(self):
  j=CommandLog();j.record('id','failed',http_status=503,error_type='ClientResponseError',elapsed_ms=50)
  self.assertEqual(j.listing()['items'][0]['http_status'],503)

if __name__=='__main__':unittest.main()
