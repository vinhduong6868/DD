"""HA Ingress settings: local catalog, durable sharing choices, scoped pairing."""
import asyncio
import hashlib
import json
import os
import secrets
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import aiohttp
from aiohttp import web


def valid_ids(values):
    if not isinstance(values,list) or len(values)>2000 or any(not isinstance(x,str) or len(x)>255 or '.' not in x for x in values):
        raise ValueError('invalid_selection')
    if len(set(values))!=len(values):raise ValueError('duplicate_selection')
    return set(values)


class Sharing:
    def __init__(self,path,initial):
        self.path=Path(path)
        data=json.loads(self.path.read_text()) if self.path.exists() else {'entity_ids':sorted(initial),'mode':'selected'}
        self.ids=valid_ids(data['entity_ids']);self.mode=data.get('mode','selected')
        if self.mode not in ('selected','all'):raise ValueError('invalid_sharing_mode')
        from command_log import CommandLog
        self.command_log=CommandLog()
        self.readback_tasks=set()
        self.all_seen=set()
        self.changed=asyncio.Event()
        self.lock=asyncio.Lock()
        self.ws=None;self.paired=False;self.code='';self.code_expires=0;self.pair_ack=None

    @property
    def revision(self):return hashlib.sha256(json.dumps([self.mode,sorted(self.ids)],separators=(',',':')).encode()).hexdigest()

    @property
    def allowed(self):return self.ids|self.all_seen if self.mode=='all' else self.ids

    def save(self,ids,revision,mode='selected'):
        if revision!=self.revision:raise ValueError('selection_changed')
        if mode not in ('selected','all'):raise ValueError('invalid_sharing_mode')
        ids=valid_ids(ids)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        fd,path=tempfile.mkstemp(prefix='.sharing-',dir=self.path.parent)
        try:
            with os.fdopen(fd,'w') as file:
                json.dump({'entity_ids':sorted(ids),'mode':mode},file);file.flush();os.fsync(file.fileno())
            os.replace(path,self.path)
        finally:
            if os.path.exists(path):os.unlink(path)
        self.ids=ids;self.mode=mode;self.changed.set()

    def advertised(self,code):
        self.code=code;self.code_expires=time.time()+300

    async def pair(self):
        async with self.lock:
            if self.ws is None or self.ws.closed:raise web.HTTPServiceUnavailable(text='relay_offline')
            if not self.paired:
                if self.code_expires>time.time():return {'code':self.code,'expires_at':self.code_expires}
                raise web.HTTPServiceUnavailable(text='pairing_reconnecting')
            code=secrets.token_hex(6).upper()
            self.pair_ack=asyncio.get_running_loop().create_future()
            await self.ws.send_json({'type':'pair_again','pair_code':code})
            try:await asyncio.wait_for(self.pair_ack,timeout=10)
            except asyncio.TimeoutError:raise web.HTTPGatewayTimeout(text='pairing_unavailable') from None
            finally:self.pair_ack=None
            self.advertised(code)
            return {'code':self.code,'expires_at':self.code_expires}


async def ha_ws(session,ha,token,commands):
    parsed=urlsplit(ha)
    path='/core/websocket' if parsed.hostname=='supervisor' and parsed.path.rstrip('/')=='/core' else parsed.path.rstrip('/')+'/api/websocket'
    url=urlunsplit(('wss' if parsed.scheme=='https' else 'ws',parsed.netloc,path,'',''))
    async with session.ws_connect(url,headers={'Authorization':'Bearer '+token},timeout=aiohttp.ClientTimeout(total=15)) as ws:
        await ws.receive_json(timeout=10)
        await ws.send_json({'type':'auth','access_token':token})
        if (await ws.receive_json(timeout=10)).get('type')!='auth_ok':raise RuntimeError('ha_auth_failed')
        results=[]
        for i,command in enumerate(commands,1):
            await ws.send_json({'id':i,'type':command})
            result=await ws.receive_json(timeout=10)
            if result.get('id')!=i or result.get('success') is not True:raise RuntimeError('ha_catalog_failed')
            results.append(result['result'])
        return results


async def is_admin(session,ha,token,user_id):
    if not user_id:return False
    users,=await ha_ws(session,ha,token,['config/auth/list'])
    return any(u.get('id')==user_id and u.get('is_active') and (u.get('is_owner') or 'system-admin' in u.get('group_ids',[])) for u in users)


async def catalog(session,ha,token,sharing):
    async with session.get(ha+'/api/states',headers={'Authorization':'Bearer '+token},timeout=aiohttp.ClientTimeout(total=15)) as r:
        r.raise_for_status();states=await r.json()
    from connector import sanitize_states
    states=sanitize_states(states)
    entities,devices,areas=await ha_ws(session,ha,token,['config/entity_registry/list','config/device_registry/list','config/area_registry/list'])
    registry={e['entity_id']:e for e in entities if isinstance(e,dict) and isinstance(e.get('entity_id'),str)};hardware={d['id']:d for d in devices if isinstance(d,dict) and isinstance(d.get('id'),str)};rooms={a['area_id']:a.get('name','') for a in areas if isinstance(a,dict) and isinstance(a.get('area_id'),str)}
    states_by_id={s['entity_id']:s for s in states};groups={}
    for eid in sorted(set(registry)|set(states_by_id)|sharing.ids):
        entry=registry.get(eid,{});state=states_by_id.get(eid,{});attrs=state.get('attributes',{})
        device=hardware.get(entry.get('device_id'),{})
        group_id=entry.get('device_id') or 'entity:'+eid
        group=groups.setdefault(group_id,{'name':device.get('name_by_user') or device.get('name') or attrs.get('friendly_name') or eid,
            'area':rooms.get(entry.get('area_id') or device.get('area_id'),''),'entities':[]})
        group['entities'].append({'entity_id':eid,'name':entry.get('name') or attrs.get('friendly_name') or entry.get('original_name') or eid,
            'selected':sharing.mode=='all' or eid in sharing.ids,'available':eid in states_by_id and state.get('state') not in ('unavailable','unknown'),
            'technical':entry.get('entity_category') in ('diagnostic','config') or bool(entry.get('disabled_by'))})
    return sorted(groups.values(),key=lambda x:(x['area'],x['name'].casefold()))


def create_app(sharing,session,ha,token,ingress_peer='172.30.32.2'):
    csrf=secrets.token_urlsafe(32)
    @web.middleware
    async def guard(request,handler):
        if request.remote!=ingress_peer:raise web.HTTPForbidden(text='ingress_required')
        try:allowed=await is_admin(session,ha,token,request.headers.get('X-Remote-User-Id',''))
        except Exception:raise web.HTTPServiceUnavailable(text='ha_authorization_unavailable') from None
        if not allowed:raise web.HTTPForbidden(text='ha_admin_required')
        if request.method!='GET' and not secrets.compare_digest(request.headers.get('X-DD-CSRF',''),csrf):
            raise web.HTTPForbidden(text='csrf_required')
        response=await handler(request)
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        return response
    app=web.Application(middlewares=[guard],client_max_size=262144)
    async def index(request):return web.Response(text=Path(__file__).with_name('index.html').read_text(),content_type='text/html')
    async def listing(request):
        try:items=await catalog(session,ha,token,sharing)
        except Exception:raise web.HTTPServiceUnavailable(text='ha_catalog_unavailable') from None
        return web.json_response({'items':items,'revision':sharing.revision,'csrf':csrf,'mode':sharing.mode,
            'online':sharing.ws is not None and not sharing.ws.closed,'paired':sharing.paired,
            'code':sharing.code if sharing.code_expires>time.time() else '', 'expires_at':sharing.code_expires})
    async def save(request):
        data=await request.json()
        if not isinstance(data,dict) or set(data)!={'entity_ids','revision','mode'}:raise web.HTTPBadRequest()
        try:
            ids=valid_ids(data['entity_ids'])
            items=await catalog(session,ha,token,sharing)
            known={e['entity_id'] for group in items for e in group['entities']}
            if not ids<=known:raise ValueError('unknown_entity')
            sharing.save(data['entity_ids'],data['revision'],data['mode'])
        except ValueError as exc:raise web.HTTPConflict(text=str(exc)) from None
        return web.json_response({'ok':True,'revision':sharing.revision,'selected_count':len(sharing.ids)})
    async def command_log(request):return web.json_response(sharing.command_log.listing())
    app.router.add_get('/api/commands',command_log)
    async def pair(request):return web.json_response(await sharing.pair())
    app.router.add_get('/',index);app.router.add_get('/api/entities',listing)
    app.router.add_post('/api/selection',save);app.router.add_post('/api/pair',pair)
    return app
