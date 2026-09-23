"""DD Home Assistant connector: local HA WebSocket -> outbound VPS WebSocket."""
import asyncio
import json
import logging
import os
import secrets
from pathlib import Path
import ssl
import time
from urllib.parse import urlparse

import aiohttp

LOG = logging.getLogger("dd_ha_connector")
MAX_MESSAGE = 262144
CONTROLS = {
    "light": {"turn_on", "turn_off", "toggle"},
    "switch": {"turn_on", "turn_off", "toggle"},
    "fan": {"turn_on", "turn_off", "toggle", "set_percentage", "set_preset_mode"},
    "climate": {"turn_on", "turn_off", "set_temperature", "set_hvac_mode", "set_fan_mode", "set_preset_mode"},
    "cover": {"open_cover", "close_cover", "stop_cover", "set_cover_position"},
    "media_player": {"turn_on", "turn_off", "media_play", "media_pause", "media_stop", "play_media", "volume_set", "volume_up", "volume_down", "volume_mute", "select_source"},
    "lock": {"lock", "unlock"},
    "scene": {"turn_on"},
    "script": {"turn_on"},
}
PARAMETERS = {"brightness", "brightness_pct", "rgb_color", "color_temp_kelvin", "transition",
              "percentage", "preset_mode", "temperature", "target_temp_high", "target_temp_low",
              "hvac_mode", "fan_mode", "position", "volume_level", "is_volume_muted", "source",
              "media_content_id", "media_content_type", "enqueue"}

STATE_ATTRIBUTES = {
    "media_player": {"source", "source_list", "volume_level", "is_volume_muted",
                     "media_title", "media_artist", "media_content_type", "supported_features"},
}


def settings():
    relay = os.environ["DD_RELAY_URL"]
    ha = os.environ.get("HA_URL", "http://supervisor/core")
    if urlparse(relay).scheme != "wss":
        raise ValueError("DD_RELAY_URL must use wss")
    if urlparse(ha).scheme not in {"http", "https"}:
        raise ValueError("HA_URL must use http or https")
    token = os.environ.get("HA_TOKEN") or os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        raise ValueError("HA_TOKEN or SUPERVISOR_TOKEN is required")
    return relay, ha.rstrip("/"), token


def public_state(item):
    """Only share explicitly selected entity IDs and minimal state attributes."""
    attrs = item.get("attributes") or {}
    domain = item["entity_id"].split(".", 1)[0]
    selected = {key: attrs[key] for key in STATE_ATTRIBUTES.get(domain, ())
                if key in attrs and isinstance(attrs[key], (str, int, float, bool, list, type(None)))}
    return {"entity_id": item["entity_id"], "state": item.get("state"),
            "name": attrs.get("friendly_name"), "unit": attrs.get("unit_of_measurement"),
            **({"attributes": selected} if selected else {})}


def validate_command(command, shared):
    if set(command) != {"type", "id", "target_id", "action", "expires_at", "parameters"} or command["type"] != "command":
        raise ValueError("invalid command")
    entity = command["target_id"]
    if not isinstance(entity, str) or entity not in shared or "." not in entity:
        raise ValueError("entity not shared")
    domain, _ = entity.split(".", 1)
    if domain not in CONTROLS:
        raise ValueError("unsupported domain")
    service = command["action"]
    if not isinstance(service, str) or service not in CONTROLS[domain]:
        raise ValueError("invalid service")
    params = command["parameters"]
    if not isinstance(params, dict) or len(json.dumps(params)) > 4096 or not set(params) <= PARAMETERS:
        raise ValueError("invalid parameters")
    if service == "play_media" and not all(isinstance(params.get(key), str) and params[key]
                                           for key in ("media_content_id", "media_content_type")):
        raise ValueError("media content required")
    if not isinstance(command["id"], str) or not 1 <= len(command["id"]) <= 128:
        raise ValueError("invalid id")
    if not isinstance(command["expires_at"], (int, float)) or not time.time() < command["expires_at"] <= time.time() + 60:
        raise ValueError("expired command")
    return domain, service, entity, params


def sanitize_states(states):
    if not isinstance(states,list):raise ValueError('invalid_ha_response')
    result=[]
    for item in states:
        if not isinstance(item,dict):continue
        eid=item.get('entity_id')
        if not isinstance(eid,str) or '.' not in eid or len(eid)>255:continue
        if not isinstance(item.get('attributes',{}),dict):continue
        if not isinstance(item.get('state'),str):continue
        result.append(item)
    return result


async def ha_states(session, ha, token):
    async with session.get(ha + "/api/states", headers={"Authorization": "Bearer " + token}, timeout=aiohttp.ClientTimeout(total=15)) as response:
        response.raise_for_status()
        return sanitize_states(await response.json())


async def call_ha(session, ha, token, domain, service, entity, parameters):
    async with session.post(ha + f"/api/services/{domain}/{service}",
                            headers={"Authorization": "Bearer " + token},
                            json={"entity_id": entity, **parameters}, timeout=aiohttp.ClientTimeout(total=15)) as response:
        response.raise_for_status()
        await response.read()


async def run():
    from aiohttp import web
    from ha_ui import Sharing, create_app, ha_ws
    relay, ha, token = settings()
    credentials_path = Path(os.environ.get("DD_LINK_FILE", "/data/link.json"))
    sharing = Sharing(os.environ.get("DD_SELECTION_FILE", "/data/shared_entities.json"),
        {x.strip() for x in os.environ.get("DD_SHARED_ENTITIES", "").split(",") if x.strip()})
    ssl_context = ssl.create_default_context()
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        runner=web.AppRunner(create_app(sharing,session,ha,token),access_log=None)
        await runner.setup()
        await web.TCPSite(runner,'0.0.0.0',8099).start()
        async def snapshots(ws):
            import hashlib
            previous=None;previous_selection=None;platforms={};registry_at=0
            while not ws.closed:
                sharing.changed.clear()
                config_revision=sharing.revision
                states=None
                if time.monotonic()-registry_at>60:
                    try:
                        entries,=await ha_ws(session,ha,token,['config/entity_registry/list'])
                        platforms={e['entity_id']:e.get('platform') for e in entries if isinstance(e,dict) and isinstance(e.get('entity_id'),str)}
                    except Exception:
                        platforms={}
                        LOG.warning('HA platform metadata unavailable')
                    registry_at=time.monotonic()
                try:
                    states=await ha_states(session,ha,token)
                except (aiohttp.ClientError,asyncio.TimeoutError,ValueError) as exc:
                    LOG.warning('HA state unavailable: %s',type(exc).__name__)
                if sharing.revision!=config_revision:continue
                if states is not None and sharing.mode=='all':sharing.all_seen.update(x['entity_id'] for x in states)
                selected=set(sharing.allowed)
                revision=hashlib.sha256(json.dumps(sorted(selected),separators=(',',':')).encode()).hexdigest()
                key=(sharing.mode,revision)
                if key!=previous_selection:
                    await ws.send_json({'type':'selection','revision':revision,'entity_ids':sorted(selected),'mode':sharing.mode})
                    previous_selection=key
                if states is not None:
                    snapshot=[public_state(x) for x in states if x.get('entity_id') in selected]
                    for item in snapshot:
                        platform=platforms.get(item['entity_id'])
                        if isinstance(platform,str) and len(platform)<=80:item['platform']=platform
                    if (revision,snapshot)!=previous:
                        await ws.send_json({'type':'snapshot','entities':snapshot,'selection_revision':revision})
                        previous=(revision,snapshot)
                try:await asyncio.wait_for(sharing.changed.wait(),timeout=5)
                except asyncio.TimeoutError:pass
        try:
            while True:
                polling=None
                try:
                    async with session.ws_connect(relay,ssl=ssl_context,heartbeat=25,max_msg_size=MAX_MESSAGE) as ws:
                        sharing.ws=ws;sharing.paired=False
                        if credentials_path.exists():
                            credentials=json.loads(credentials_path.read_text())
                            await ws.send_json({'type':'hello','link_id':credentials['link_id'],'link_secret':credentials['link_secret'],'endpoint_type':'ha','protocol':1})
                        else:
                            code=secrets.token_hex(6).upper();sharing.advertised(code)
                            await ws.send_json({'type':'advertise','pair_code':code,'endpoint_type':'ha','protocol':1})
                        hello=await ws.receive_json(timeout=15)
                        if hello.get('type')=='pending':hello=await ws.receive_json(timeout=300)
                        if hello.get('type')!='ready':raise RuntimeError('relay rejected pairing')
                        if 'link_secret' in hello:
                            credentials_path.parent.mkdir(parents=True,exist_ok=True)
                            import tempfile
                            fd,tmp=tempfile.mkstemp(prefix='.link-',dir=credentials_path.parent)
                            try:
                                with os.fdopen(fd,'w') as file:
                                    json.dump({'link_id':hello['link_id'],'link_secret':hello['link_secret']},file)
                                    file.flush();os.fsync(file.fileno())
                                os.replace(tmp,credentials_path)
                            finally:
                                if os.path.exists(tmp):os.unlink(tmp)
                        sharing.paired=True;sharing.code='';sharing.code_expires=0
                        LOG.info('Connected to DD relay')
                        polling=asyncio.create_task(snapshots(ws))
                        async for message in ws:
                            if message.type!=aiohttp.WSMsgType.TEXT:break
                            command=json.loads(message.data)
                            if command.get('type')=='pair_pending':
                                if sharing.pair_ack and not sharing.pair_ack.done():sharing.pair_ack.set_result(True)
                                continue
                            if command.get('type')!='command':continue
                            from command_execution import execute_logged
                            receipt=await execute_logged(command,sharing,session,ha,token,validate_command,call_ha)
                            await ws.send_json(receipt)
                            sharing.command_log.record(command.get('id'),'receipt_sent')
                            sharing.changed.set()
                except (aiohttp.ClientError,asyncio.TimeoutError,RuntimeError) as exc:
                    LOG.warning('Relay unavailable: %s',type(exc).__name__)
                finally:
                    sharing.ws=None;sharing.paired=False
                    if polling:
                        polling.cancel();await asyncio.gather(polling,return_exceptions=True)
                await asyncio.sleep(5)
        finally:
            for task in tuple(sharing.readback_tasks):task.cancel()
            await asyncio.gather(*tuple(sharing.readback_tasks),return_exceptions=True)
            await runner.cleanup()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
