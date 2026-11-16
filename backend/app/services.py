import hashlib
import json
import os
import re
import secrets
import time
import uuid
from datetime import datetime
from fastapi import HTTPException
from . import db, demo
from .schemas import LookupArgs, PolicyArgs, ProposeArgs

SCENARIO_NOW = '2026-11-11T19:00:00-03:00'
STATUS_PT = {'received': 'recebido', 'preparing': 'em preparo', 'on_the_way': 'a caminho',
             'delivered': 'entregue', 'canceled': 'cancelado'}
TOOL_SCHEMAS = {'lookup_order': LookupArgs, 'get_policy': PolicyArgs,
                'create_ticket': ProposeArgs, 'handoff_to_human': ProposeArgs}


class ToolBudgetExceeded(ValueError):
    pass


class TargetMismatch(ValueError):
    pass


def revoke_actions(session_id, ctx, reason, con=None):
    def apply(connection):
        changed = connection.execute('''UPDATE actions SET valid=0,invalid_reason=?
            WHERE session_id=? AND valid=1 AND confirmed_ticket IS NULL''', (reason,session_id)).rowcount
        if changed:
            db.event('actions_revoked',ctx,connection,outcome=reason)
    if con is not None:
        apply(con)
    else:
        with db.connect() as connection:
            apply(connection)


def delayed(order):
    return bool(order['status'] == 'on_the_way' and order.get('eta') and
                datetime.fromisoformat(order['eta']) < datetime.fromisoformat(SCENARIO_NOW))


def bind_session(body):
    demo.verify_customer(body.customer_id, body.demo_token)
    with db.connect() as con:
        con.execute('INSERT OR IGNORE INTO sessions(id,customer_id) VALUES(?,?)', (body.session_id, body.customer_id))
        if con.execute('SELECT customer_id FROM sessions WHERE id=?', (body.session_id,)).fetchone()[0] != body.customer_id:
            raise HTTPException(403, 'Sessão pertence a outro contexto. Inicie nova conversa.')


def public_order(order):
    # Exclude free-form fixture fields from the model context.
    return {k: order[k] for k in ('id', 'status', 'updated_at', 'eta')} | {'is_delayed': delayed(order)}


class Tools:
    def __init__(self, body, ctx):
        self.body, self.ctx = body, ctx
        self.results, self.sources = [], []
        self.order = self.policy = self.pending = None
        self.provider_metadata = []
        self.resolve_target()

    def resolve_target(self):
        ids = list(dict.fromkeys(re.findall(r'\bORD-\d{4,8}\b',self.body.message.upper())))
        self.ambiguous = len(ids)>1
        self.target = ids[0] if len(ids)==1 else None
        if not ids:
            with db.connect() as con:
                row = con.execute('SELECT last_order_id FROM sessions WHERE id=? AND customer_id=?',
                                  (self.body.session_id,self.body.customer_id)).fetchone()
            self.target = row[0] if row else None

    def reconcile(self, reason):
        # Revocation is durable. Attempt history and its budget are never cleared.
        revoke_actions(self.body.session_id,self.ctx,reason)
        self.pending = self.policy = None
        if self.order and self.order['id'] != self.target:
            self.order = None

    def reason(self):
        text = self.body.message.lower()
        return ('refund' if 'reembolso' in text else 'cancel' if 'cancel' in text else
                'wrong_item' if any(x in text for x in ('errado','faltante','incorreto')) else
                'late_delivery' if self.order and self.order['is_delayed'] else 'assistance')

    def used_sources(self):
        sources = []
        if self.order:
            sources.append({'type':'order','id':self.order['id'],'version':'demo-2.0'})
        if self.policy and self.order and self.policy['topic']==self.reason():
            sources.append({'type':'policy','id':self.policy['topic'],'version':self.policy['version']})
        return sources

    def call(self, name, arguments):
        if len(self.results) >= 6:
            raise ToolBudgetExceeded('tool_budget')
        started = time.perf_counter()
        safe_name = name if name in TOOL_SCHEMAS else 'unknown'
        call_id = str(uuid.uuid4())
        db.event('tool_started', self.ctx, tool=safe_name,tool_call_id=call_id)
        outcome = 'failed'
        try:
            if name not in TOOL_SCHEMAS:
                raise ValueError('unknown_tool')
            args = TOOL_SCHEMAS[name].model_validate(arguments)
            if hasattr(args,'order_id') and (self.ambiguous or not self.target or args.order_id != self.target):
                raise TargetMismatch('target_mismatch')
            if name == 'get_policy':
                if args.topic != 'privacy' and (not self.order or args.topic != self.reason()):
                    raise TargetMismatch('policy_mismatch')
                p = demo.policies()
                result = {'topic': args.topic, 'text': p['topics'][args.topic], 'version': p['metadata']['version']}
                self.policy = result
                self.sources.append({'type': 'policy', 'id': args.topic, 'version': result['version']})
            else:
                order = demo.authorized_order(args.order_id, self.body.customer_id, self.body.demo_token)
                self.order = public_order(order)
                with db.connect() as con:
                    con.execute('UPDATE sessions SET last_order_id=? WHERE id=? AND customer_id=?',
                                (args.order_id,self.body.session_id,self.body.customer_id))
                self.sources.append({'type': 'order', 'id': args.order_id, 'version': 'demo-2.0'})
                if name == 'lookup_order':
                    result = self.order
                else:
                    if args.reason != self.reason():
                        raise TargetMismatch('reason_mismatch')
                    aid, token = str(uuid.uuid4()), secrets.token_urlsafe(32)
                    with db.connect() as con:
                        revoke_actions(self.body.session_id,self.ctx,'superseded_proposal',con)
                        con.execute('INSERT INTO actions(id,token,session_id,customer_id,order_id,reason,request_id,expires) VALUES(?,?,?,?,?,?,?,?)',
                                    (aid, token, self.body.session_id, self.body.customer_id,
                                     args.order_id, args.reason, self.ctx['request_id'], time.time()+600))
                    self.pending = {'action_id': aid, 'action_token': token, 'order_id': args.order_id,
                                    'reason': args.reason, 'expires_in_seconds': 600}
                    # Confirmation credentials never enter the model context.
                    result = {'confirmation_required': True, 'order_id': args.order_id, 'reason': args.reason}
            outcome = 'success'
            return result
        except TargetMismatch:
            self.reconcile('target_or_action_mismatch')
            raise
        except HTTPException as exc:
            outcome = 'denied' if exc.status_code == 403 else 'failed'
            raise
        finally:
            duration = round((time.perf_counter()-started)*1000, 3)
            self.results.append({'tool': safe_name, 'outcome': outcome, 'duration_ms': duration,'tool_call_id':call_id})
            db.event('tool_completed', self.ctx, tool=safe_name, outcome=outcome, duration_ms=duration,tool_call_id=call_id)


def confirm(action_id, body):
    bind_session(body)
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        a = con.execute('SELECT * FROM actions WHERE id=?', (action_id,)).fetchone()
        if not a or a['customer_id'] != body.customer_id or a['session_id'] != body.session_id or not secrets.compare_digest(a['token'], body.action_token):
            raise HTTPException(403, 'Ação não autorizada')
        fingerprint = hashlib.sha256(json.dumps([action_id,a['order_id'],a['reason'],body.session_id]).encode()).hexdigest()
        prior = con.execute('SELECT * FROM idempotency WHERE customer_id=? AND key=?', (body.customer_id,body.idempotency_key)).fetchone()
        if prior:
            if prior['fingerprint'] != fingerprint:
                raise HTTPException(409, 'Chave reutilizada com outra ação')
            return {'ticket_id':prior['ticket_id'], 'created':False, 'status':'open'}
        if not a['valid']:
            raise HTTPException(409,'Ação revogada. Solicite nova proposta.')
        if a['expires'] < time.time():
            raise HTTPException(410, 'Ação expirada. Solicite nova proposta.')
        demo.authorized_order(a['order_id'],body.customer_id,body.demo_token)
        ctx = dict(con.execute('SELECT * FROM events WHERE request_id=? AND name=?', (a['request_id'],'chat_received')).fetchone() or {})
        ctx = {k:ctx.get(k) for k in ('request_id','session_id','run_id','scenario_id','requested_mode','effective_mode')}
        ticket = con.execute("SELECT * FROM tickets WHERE customer_id=? AND order_id=? AND reason=? AND status='open'", (body.customer_id,a['order_id'],a['reason'])).fetchone()
        created = ticket is None
        tid = ticket['ticket_id'] if ticket else 'TCK-'+uuid.uuid4().hex[:16].upper()
        if created:
            stamp, eid = db.now(), str(uuid.uuid4())
            con.execute('INSERT INTO tickets(ticket_id,customer_id,order_id,reason,created_at,request_id) VALUES(?,?,?,?,?,?)',
                        (tid,body.customer_id,a['order_id'],a['reason'],stamp,a['request_id']))
            payload = {'schema_version':'1','event_id':eid,'ticket_id':tid,'order_id':a['order_id'],
                       'reason_code':a['reason'],'created_at':stamp,'source':'synthetic-demo'}
            state = 'pending' if os.getenv('N8N_WEBHOOK_URL') else 'not_configured'
            con.execute('INSERT INTO outbox(event_id,ticket_id,payload,state) VALUES(?,?,?,?)', (eid,tid,json.dumps(payload),state))
            db.event('ticket_created',ctx,con,ticket_id=tid)
            db.event('handoff_queued',ctx,con,ticket_id=tid,operation_id=eid)
        con.execute('INSERT INTO idempotency VALUES(?,?,?,?)', (body.customer_id,body.idempotency_key,fingerprint,tid))
        con.execute('UPDATE actions SET confirmed_ticket=? WHERE id=?',(tid,action_id))
        db.event('ticket_confirmed',ctx,con,ticket_id=tid,outcome='created' if created else 'reused')
    return {'ticket_id':tid, 'created':created, 'status':'open'}


def ticket_list(customer_id, demo_token, ticket_id=None):
    demo.verify_customer(customer_id,demo_token)
    with db.connect() as con:
        rows = con.execute('''SELECT t.*,o.state AS automation_state,o.event_id,o.attempts,o.next_at,o.error,o.retry_cycles
            FROM tickets t JOIN outbox o USING(ticket_id) WHERE t.customer_id=? ORDER BY t.created_at DESC''', (customer_id,)).fetchall()
    result = [dict(r) for r in rows]
    if ticket_id:
        selected = next((r for r in result if r['ticket_id']==ticket_id),None)
        if not selected:
            raise HTTPException(403,'Ticket não acessível')
        with db.connect() as con:
            selected['timeline'] = [dict(r) for r in con.execute(
                'SELECT name,outcome,created_at FROM events WHERE ticket_id=? ORDER BY created_at', (ticket_id,))]
        return selected
    return result
