import asyncio,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import AsyncMock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'dd-connector'))
import ha_ui
from command_execution import execute_logged
from aiohttp.test_utils import TestClient,TestServer

class Response:
 async def __aenter__(self):return self
 async def __aexit__(self,*args):pass
 def raise_for_status(self):pass
 async def json(self):return {'state':'on'}
class Session:
 def get(self,*a,**kw):return Response()

class Tests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.s=ha_ui.Sharing(Path(self.tmp.name)/'sharing.json',{'switch.test'})
 async def asyncTearDown(self):
  tasks=tuple(self.s.readback_tasks)
  for t in tasks:t.cancel()
  await asyncio.gather(*tasks,return_exceptions=True);self.tmp.cleanup()
 def validate(self,c,allowed):
  if c['target_id'] not in allowed:raise ValueError('not_shared')
  return 'switch','turn_on',c['target_id'],{}
 def command(self,target='switch.test'):
  return dict(id='test-id',target_id=target)
 async def test_receipt_and_readback(self):
  call=AsyncMock()
  r=await execute_logged(self.command(),self.s,Session(),'http://ha','SECRET',self.validate,call)
  self.assertEqual(r['status'],'accepted_unverified');call.assert_awaited_once()
  await asyncio.gather(*tuple(self.s.readback_tasks))
  stages=[r['stage'] for r in self.s.command_log.listing()['items']]
  self.assertIn('ha_accepted',stages);self.assertIn('state_confirmed',stages)
  self.assertNotIn('SECRET',str(self.s.command_log.listing()))
 async def test_denied_not_sent(self):
  call=AsyncMock();r=await execute_logged(self.command('switch.other'),self.s,Session(),'http://ha','secret',self.validate,call)
  self.assertEqual(r['status'],'failed');call.assert_not_called()
 async def test_ha_failure_not_confirmed(self):
  call=AsyncMock(side_effect=RuntimeError('secret URL must not leak'))
  r=await execute_logged(self.command(),self.s,Session(),'http://ha','secret',self.validate,call)
  self.assertEqual(r['status'],'failed');self.assertFalse(self.s.readback_tasks)
  self.assertNotIn('must not leak',str(self.s.command_log.listing()))
 async def test_readback_concurrency_bound(self):
  blockers=[asyncio.create_task(asyncio.sleep(30)) for _ in range(8)];self.s.readback_tasks.update(blockers)
  await execute_logged(self.command(),self.s,Session(),'http://ha','secret',self.validate,AsyncMock())
  self.assertEqual(len(self.s.readback_tasks),8)
  self.assertEqual(self.s.command_log.listing()['items'][0]['reason'],'readback_busy')
 async def test_admin_guard_and_safe_listing(self):
  app=ha_ui.create_app(self.s,Session(),'http://ha','secret',ingress_peer='127.0.0.1')
  async with TestClient(TestServer(app)) as client:
   with patch.object(ha_ui,'is_admin',AsyncMock(return_value=False)):
    r=await client.get('/api/commands');self.assertEqual(r.status,403)
   with patch.object(ha_ui,'is_admin',AsyncMock(return_value=True)):
    r=await client.get('/api/commands');self.assertEqual(r.status,200)
    self.assertEqual(r.headers['Cache-Control'],'no-store');self.assertEqual((await r.json())['count'],0)
 async def test_ingress_guard(self):
  app=ha_ui.create_app(self.s,Session(),'http://ha','secret')
  async with TestClient(TestServer(app)) as client:
   with patch.object(ha_ui,'is_admin',AsyncMock(return_value=True)):
    r=await client.get('/api/commands');self.assertEqual(r.status,403)

if __name__=='__main__':unittest.main()
