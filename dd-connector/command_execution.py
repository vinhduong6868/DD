"""Receipt-compatible command diagnostics; readback never delays a command receipt."""
import asyncio
import time

EXPECTED={'turn_on':'on','turn_off':'off','media_play':'playing','media_pause':'paused',
          'open_cover':'open','close_cover':'closed'}

async def execute_logged(command,sharing,session,ha,token,validate,call):
    journal=sharing.command_log
    cid=command.get('id');start=time.monotonic()
    journal.record(cid,'received')
    receipt={'type':'receipt','id':cid,'status':'rejected'}
    entity=action=''
    try:
        domain,action,entity,parameters=validate(command,sharing.allowed)
        journal.record(cid,'validated',entity_id=entity,action=action)
        await call(session,ha,token,domain,action,entity,parameters)
        receipt['status']='accepted_unverified'
        journal.record(cid,'ha_accepted',entity_id=entity,action=action,elapsed_ms=(time.monotonic()-start)*1000)
        if action in EXPECTED:
            if len(sharing.readback_tasks)<8:
                task=asyncio.create_task(readback(sharing,session,ha,token,cid,entity,action,start))
                sharing.readback_tasks.add(task);task.add_done_callback(sharing.readback_tasks.discard)
            else:journal.record(cid,'state_unverified',entity_id=entity,action=action,reason='readback_busy')
    except Exception as exc:
        receipt['status']='failed'
        journal.record(cid,'failed',entity_id=entity,action=action,
          elapsed_ms=(time.monotonic()-start)*1000,error_type=type(exc).__name__,
          http_status=getattr(exc,'status',None),reason='validation_or_ha_error')
    return receipt

async def readback(sharing,session,ha,token,cid,entity,action,start):
    journal=sharing.command_log
    try:
        async with asyncio.timeout(8):
            for attempt in range(3):
                if attempt:await asyncio.sleep(1)
                if entity not in sharing.allowed:
                    journal.record(cid,'state_unverified',entity_id=entity,action=action,reason='sharing_removed');return
                async with session.get(ha+'/api/states/'+entity,headers={'Authorization':'Bearer '+token}) as response:
                    response.raise_for_status();body=await response.json()
                if body.get('state')==EXPECTED[action]:
                    journal.record(cid,'state_confirmed',entity_id=entity,action=action,
                      elapsed_ms=(time.monotonic()-start)*1000,reason='ha_state_matches');return
        journal.record(cid,'state_unverified',entity_id=entity,action=action,reason='state_not_confirmed')
    except Exception as exc:
        journal.record(cid,'state_unverified',entity_id=entity,action=action,
          error_type=type(exc).__name__,http_status=getattr(exc,'status',None),reason='readback_error')
