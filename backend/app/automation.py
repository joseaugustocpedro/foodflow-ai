"""Leased durable outbox and authenticated, idempotent local inbox."""
import asyncio
import json
import os
import secrets
import time
import uuid
from urllib.parse import urlparse
import httpx
from fastapi import HTTPException
from . import db
from .schemas import HandoffPayload, Ack


def local_url(url):
    p = urlparse(url)
    if p.scheme != 'http' or p.hostname not in ('127.0.0.1','::1') or p.username or p.password or p.fragment or p.port == 0:
        raise ValueError('Only literal loopback HTTP URLs are supported')
    return url


def preflight():
    url = os.getenv('N8N_WEBHOOK_URL','')
    first,second = os.getenv('N8N_WEBHOOK_SECRET',''),os.getenv('FOODFLOW_INBOX_SECRET','')
    reason = None
    if not url:
        return {'state':'not_configured','ready':False,'reason':'url_absent'}
    try:
        local_url(url)
    except ValueError:
        reason='url_not_allowed'
    if not first or not second:
        reason=reason or 'credentials_missing'
    elif secrets.compare_digest(first,second):
        reason=reason or 'credentials_must_differ'
    elif any(v.startswith('DEMO-') or len(v)<12 for v in (first,second)):
        reason=reason or 'credentials_inadequate'
    return {'state':'configuration_blocked' if reason else 'configured_unverified','ready':reason is None,
            'reason':reason or 'ready_to_attempt'}


def transition(state):
    value=json.dumps(state,sort_keys=True)
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        prior=con.execute("SELECT value FROM runtime_state WHERE name='automation'").fetchone()
        if not prior or prior[0]!=value:
            con.execute("INSERT OR REPLACE INTO runtime_state VALUES('automation',?)",(value,))
            db.event('automation_configuration',{'run_id':os.getenv('FOODFLOW_RUN_ID','interactive')},con,outcome=state['reason'])


def origin_context(con,ticket_id):
    row=con.execute('SELECT e.* FROM tickets t JOIN events e ON t.request_id=e.request_id WHERE t.ticket_id=? AND e.name=?',
                    (ticket_id,'chat_received')).fetchone()
    ctx=dict(row) if row else {}
    terminal=con.execute("SELECT effective_mode FROM events WHERE request_id=? AND name='chat_completed'",(ctx.get('request_id'),)).fetchone()
    if terminal:
        ctx['effective_mode']=terminal[0]
    return ctx


def receive(payload, secret):
    if preflight()['state']=='configuration_blocked':
        raise HTTPException(503,'Configuração da automação bloqueada')
    expected = os.getenv('FOODFLOW_INBOX_SECRET','')
    if not expected or not secrets.compare_digest(expected,secret or ''):
        raise HTTPException(403,'Serviço não autorizado')
    data = HandoffPayload.model_validate(payload).model_dump()
    canonical = json.dumps(data,sort_keys=True)
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        outbox = con.execute('SELECT payload FROM outbox WHERE event_id=? AND ticket_id=?', (data['event_id'],data['ticket_id'])).fetchone()
        if not outbox or json.loads(outbox[0]) != data:
            raise HTTPException(409,'Evento não corresponde ao registro local')
        con.execute('INSERT OR IGNORE INTO inbox VALUES(?,?,?,?,?)',
                    (data['event_id'],data['ticket_id'],canonical,str(uuid.uuid4()),db.now()))
        row = con.execute('SELECT * FROM inbox WHERE event_id=?',(data['event_id'],)).fetchone()
        if row['payload'] != canonical:
            raise HTTPException(409,'Evento conflitante')
    return {'received':True,'event_id':data['event_id'],'ticket_id':data['ticket_id'],
            'record_id':row['record_id'],'received_at':row['received_at']}


async def send_http(url,payload,secret):
    async with httpx.AsyncClient(timeout=3,follow_redirects=False,trust_env=False) as client:
        response = await client.post(url,json=payload,headers={'X-FoodFlow-Webhook':secret})
        if response.status_code != 200 or len(response.content)>16384:
            raise ValueError('invalid_response')
        return response.json()


async def deliver_once(sender=None, clock=None):
    config=preflight()
    transition(config)
    if not config['ready']:
        return False
    url = os.getenv('N8N_WEBHOOK_URL','')
    if not url:
        return False
    local_url(url)
    secret = os.getenv('N8N_WEBHOOK_SECRET','')
    if not secret:
        return False
    stamp = time.time() if clock is None else clock
    lease = str(uuid.uuid4())
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        row = con.execute("""SELECT * FROM outbox WHERE
          (state IN ('pending','not_configured') AND next_at<=?) OR
          (state='sending' AND lease_until<=?) ORDER BY next_at LIMIT 1""", (stamp,stamp)).fetchone()
        if not row:
            return False
        row = dict(row)
        ctx=origin_context(con,row['ticket_id'])
        # A process crash during the final attempt must terminate, not attempt forever.
        if row['attempts']>=3:
            con.execute("UPDATE outbox SET state='failed',error='lease_expired' WHERE event_id=?", (row['event_id'],))
            db.event('handoff_failed',ctx,con,ticket_id=row['ticket_id'],operation_id=row['event_id'],attempt_id=row['lease_token'],outcome='lease_expired')
            return True
        con.execute("UPDATE outbox SET state='sending',attempts=attempts+1,lease_until=?,lease_token=? WHERE event_id=?", (stamp+15,lease,row['event_id']))
        db.event('handoff_attempted',ctx,con,ticket_id=row['ticket_id'],operation_id=row['event_id'],attempt_id=lease)
    payload = HandoffPayload.model_validate_json(row['payload']).model_dump()
    error, ack = None, None
    try:
        result = await asyncio.wait_for((sender or send_http)(url,payload,secret),timeout=3)
        ack = Ack.model_validate(result).model_dump()
        if ack['event_id']!=row['event_id'] or ack['ticket_id']!=row['ticket_id']:
            raise ValueError('ack_mismatch')
        # This architecture uses our local inbox; require durable receipt, not just 200.
        with db.connect() as con:
            saved = con.execute('SELECT * FROM inbox WHERE event_id=?', (row['event_id'],)).fetchone()
        if not saved or saved['record_id']!=ack['record_id'] or saved['received_at']!=ack['received_at']:
            raise ValueError('ack_not_persisted')
    except Exception:
        error, ack = 'delivery_unconfirmed', None
    with db.connect() as con:
        attempt = row['attempts']+1
        state = 'confirmed' if ack else 'failed' if attempt>=3 else 'pending'
        changed = con.execute('''UPDATE outbox SET state=?,error=?,ack=?,next_at=?,lease_until=0
            WHERE event_id=? AND lease_token=?''',
            (state,error,json.dumps(ack) if ack else None,stamp+(2 if attempt==1 else 10),row['event_id'],lease)).rowcount
        if changed:
            db.event('handoff_acknowledged' if ack else 'handoff_failed',ctx,con,ticket_id=row['ticket_id'],outcome=state,operation_id=row['event_id'],attempt_id=lease)
    return True


def retry(ticket_id):
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        updated = con.execute("UPDATE outbox SET state='pending',attempts=0,next_at=0,error=NULL,retry_cycles=retry_cycles+1 WHERE ticket_id=? AND state='failed' AND retry_cycles<2", (ticket_id,)).rowcount
        if not updated:
            raise HTTPException(409,'Reenvio disponível somente após falha; máximo de dois ciclos manuais')
        row=con.execute('SELECT event_id FROM outbox WHERE ticket_id=?',(ticket_id,)).fetchone()
        db.event('handoff_retry_requested',origin_context(con,ticket_id),con,ticket_id=ticket_id,operation_id=row[0])
    return {'status':'pending'}


async def worker(stop):
    while not stop.is_set():
        try:
            await deliver_once()
            with db.connect() as con:
                con.execute("INSERT OR REPLACE INTO runtime_state VALUES('worker','ok')")
        except Exception:
            try:
                with db.connect() as con:
                    previous=con.execute("SELECT value FROM runtime_state WHERE name='worker'").fetchone()
                    if not previous or previous[0]!='failed':
                        db.event('automation_worker',{'run_id':os.getenv('FOODFLOW_RUN_ID','interactive')},con,outcome='worker_failure')
                    con.execute("INSERT OR REPLACE INTO runtime_state VALUES('worker','failed')")
            except Exception:
                # Database may itself be down. Health reports degraded; no raw error logging.
                pass
        try:
            await asyncio.wait_for(stop.wait(),timeout=.5)
        except TimeoutError:
            pass
