"""Bounded process-local command journal. Never retain payloads, URLs or exception text."""
from collections import deque
from datetime import datetime, timezone
import re
import time

STAGES=frozenset(('received','validated','ha_accepted','state_confirmed','state_unverified','failed','receipt_sent'))
ATOM=re.compile(r'^[A-Za-z0-9_.:-]{1,128}$')

class CommandLog:
    def __init__(self,limit=200,ttl=86400,clock=time.time):
        self.rows=deque(maxlen=max(1,min(int(limit),500)))
        self.ttl=max(60,min(int(ttl),86400));self.clock=clock

    def record(self,command_id,stage,*,entity_id='',action='',elapsed_ms=None,http_status=None,error_type='',reason=''):
        if stage not in STAGES:raise ValueError('invalid_stage')
        def atom(value):return value if isinstance(value,str) and ATOM.fullmatch(value) else ''
        now=self.clock()
        row={'time':datetime.fromtimestamp(now,timezone.utc).isoformat(),'command_id':atom(command_id),
             'stage':stage,'entity_id':atom(entity_id),'action':atom(action)}
        if isinstance(elapsed_ms,(int,float)) and 0<=elapsed_ms<=86400000:row['elapsed_ms']=round(elapsed_ms)
        if isinstance(http_status,int) and 100<=http_status<=599:row['http_status']=http_status
        # Callers pass classification only; never str(exception) or command parameters.
        if atom(error_type):row['error_type']=error_type
        if atom(reason):row['reason']=reason
        self.rows.append((now,row));self._prune()

    def _prune(self):
        cutoff=self.clock()-self.ttl
        while self.rows and self.rows[0][0]<cutoff:self.rows.popleft()

    def listing(self):
        self._prune()
        return {'items':[dict(row) for _,row in reversed(self.rows)],'count':len(self.rows),
                'capacity':self.rows.maxlen,'retention_seconds':self.ttl,'storage':'memory_until_restart'}
