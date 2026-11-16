"""Audit regressions: run first against unchanged Etapa 02 product code."""
import asyncio
from backend.app import agent,automation,db
from backend.tests.test_api import Fake,call,DONE,toolset,configured_ticket,durable_sender
from backend.tests.conftest import AUTH,chat

def test_f01_model_cannot_select_other_owned_order(client):
    body,tools=toolset()
    message,mode,reason=asyncio.run(agent.respond(body,tools,Fake([call(args={'order_id':'ORD-1003'}),DONE])))
    assert tools.order is None or tools.order['id']=='ORD-1001'
    assert mode=='demo' and reason

def test_f02_proposal_then_wrong_lookup_cannot_diverge(client):
    body,tools=toolset()
    body.message='ORD-1002'
    fake=Fake([call('create_ticket',{'order_id':'ORD-1002','reason':'late_delivery'}),call(args={'order_id':'ORD-1001'}),DONE])
    asyncio.run(agent.respond(body,tools,fake))
    assert tools.pending is None or tools.order['id']==tools.pending['order_id']

def test_f02_timeout_discards_incompatible_proposal(client):
    body,tools=toolset()
    fake=Fake([call('create_ticket',{'order_id':'ORD-1003','reason':'refund'}),TimeoutError()])
    asyncio.run(agent.respond(body,tools,fake))
    assert tools.pending is None or tools.pending['order_id']=='ORD-1001'

def test_f07_boundary_window_does_not_count_negative_tools(client):
    ctx={'request_id':'boundary','run_id':'interactive','effective_mode':'demo'}
    db.event('tool_started',ctx,tool='lookup_order')
    db.event('tool_completed',ctx,tool='lookup_order',outcome='success',duration_ms=2)
    with db.connect() as c:
        c.execute("UPDATE events SET created_at='2026-11-11T00:00:00+00:00' WHERE name='tool_started'")
        c.execute("UPDATE events SET created_at='2026-11-11T00:00:02+00:00' WHERE name='tool_completed'")
    m=client.get('/api/v1/metrics',params={'since':'2026-11-11T00:00:01Z','until':'2026-11-11T00:00:03Z'}).json()
    assert m['tool_pending']==0

def test_f08_direct_block_has_own_channel_without_new_chat(client):
    client.get('/api/v1/orders/ORD-1004',params=AUTH)
    m=client.get('/api/v1/metrics').json()
    assert m.get('blocked_by_channel',{}).get('direct_order')==1
    assert m['total_interactions']==0

def test_f09_invalid_length_is_safe_4xx(client):
    try:
        r=client.post('/api/v1/chat',content=b'{}',headers={'content-length':'invalid'})
    except Exception:
        assert False,'Malformed Content-Length must not raise server exception'
    assert 400<=r.status_code<500 and r.json()['request_id']

def test_f05_equal_secrets_block_delivery(client,monkeypatch):
    tid=configured_ticket(client,monkeypatch)
    monkeypatch.setenv('N8N_WEBHOOK_SECRET','test-inbox-secret')
    asyncio.run(automation.deliver_once(durable_sender,0))
    assert client.get('/api/v1/tickets/'+tid,params=AUTH).json()['automation_state']!='confirmed'

import json
from datetime import datetime
import pytest
from backend.app.services import Tools
from backend.app.schemas import ChatRequest
from backend.tests.conftest import proposal,confirmation
from backend.tests.test_api import counts

def test_f02_superseded_token_is_revoked_in_database(client):
    a=proposal(client)
    b=proposal(client)
    assert confirmation(client,a).status_code==409
    assert confirmation(client,b).status_code==200
    assert counts()==(1,1,0)

def test_f02_fallback_revokes_valid_partial_action(client):
    body=ChatRequest(**AUTH,session_id='revoke',message='ORD-1002',requested_mode='llm')
    chat(client,'ORD-1002',session='revoke')
    tools=Tools(body,{'request_id':'revoke','session_id':'revoke'})
    captured=[]
    class Capture(Fake):
        async def respond(self,items,definitions):
            if tools.pending:captured.append(dict(tools.pending))
            return await super().respond(items,definitions)
    fake=Capture([call('create_ticket',{'order_id':'ORD-1002','reason':'late_delivery'}),TimeoutError()])
    asyncio.run(agent.respond(body,tools,fake))
    assert captured and tools.pending['action_id']!=captured[0]['action_id']
    assert confirmation(client,captured[0],session='revoke').status_code==409
    assert counts()==(0,0,0)
    assert len(tools.results)<=6

def test_f01_context_and_ambiguity(client):
    assert chat(client,'ORD-1001 e ORD-1002').json()['order'] is None
    assert chat(client,'Onde está?').json()['order'] is None
    assert chat(client,'ORD-1001').json()['order']['id']=='ORD-1001'
    assert chat(client,'E a previsão?').json()['order']['id']=='ORD-1001'
    a=proposal(client)
    chat(client,'ORD-1003')
    assert confirmation(client,a).status_code==409

def test_f02_replay_confirmed_survives_context_and_expiration(client):
    a=proposal(client);tid=confirmation(client,a).json()['ticket_id']
    chat(client,'ORD-1001')
    with db.connect() as con:con.execute('UPDATE actions SET expires=0')
    assert confirmation(client,a).json()['ticket_id']==tid
    assert counts()==(1,1,0)

def test_f02_policy_source_matches_intent(client):
    body,tools=toolset()
    fake=Fake([call(),call('get_policy',{'topic':'refund'}),DONE])
    asyncio.run(agent.respond(body,tools,fake))
    assert tools.policy is None
    assert all(s['id']!='refund' for s in tools.used_sources())

def test_f07_cohort_asof_and_immutable_confirmation(client):
    a=proposal(client)
    before=db.dump_events();terminal=next(e for e in before if e['name']=='chat_completed')
    confirmation(client,a)
    after=db.dump_events()
    assert next(e for e in after if e['event_id']==terminal['event_id'])==terminal
    asof=terminal['created_at']
    old=client.get('/api/v1/metrics',params={'as_of':asof}).json()
    assert old['outcomes']['answered']==1 and old['outcomes']['escalated']==0
    assert client.get('/api/v1/metrics').json()['outcomes']['escalated']==1

def test_f07_distinct_tools_boundary_and_modes(client):
    from backend.app.metrics import aggregate
    ctx={'request_id':'cohort','run_id':'interactive','effective_mode':'demo'}
    for i in range(2):
        db.event('tool_started',ctx,tool='lookup_order',tool_call_id=f'tool-{i}')
        db.event('tool_completed',ctx,tool='lookup_order',tool_call_id=f'tool-{i}',outcome='success',duration_ms=2)
    with db.connect() as con:
        con.execute("UPDATE events SET created_at='2026-11-11T00:00:00+00:00' WHERE name='tool_started'")
        con.execute("UPDATE events SET created_at='2026-11-11T00:00:02+00:00' WHERE name='tool_completed'")
    start=datetime.fromisoformat('2026-11-11T00:00:00+00:00');end=datetime.fromisoformat('2026-11-11T00:00:01+00:00')
    m=aggregate(db.dump_events(),since=start,until=end,as_of=datetime.fromisoformat('2026-11-11T00:00:03+00:00'))
    assert m['tool_pending']==0 and m['tool_success']['denominator']==2
    assert aggregate(db.dump_events(),since=start,until=end,as_of=end)['tool_pending']==2
    assert aggregate(db.dump_events(),mode='llm')['tool_success']['value'] is None

@pytest.mark.parametrize('header',['-1','bad','1.5',''])
def test_f09_bad_lengths_with_request_id(client,header):
    r=client.post('/api/v1/chat',content=b'{}',headers={'content-length':header})
    assert r.status_code==400 and r.headers['x-request-id']==r.json()['request_id']

def test_f09_actual_chunked_bytes_limit(client):
    def chunks():yield b'a'*10000;yield b'b'*10000
    r=client.post('/api/v1/chat',content=chunks())
    assert r.status_code==413 and r.json()['request_id']
    r=client.post('/api/v1/chat',content=b'abc',headers={'content-length':'2'})
    assert r.status_code==400

@pytest.mark.parametrize('host',['[evil]','host.docker.internal','evil.test','[::1]:bad'])
def test_f09_host_allowlist_preserved(client,host):
    assert client.get('/health',headers={'host':host}).status_code==400

def test_f05_transition_and_lease_events(client,monkeypatch):
    tid=configured_ticket(client,monkeypatch)
    monkeypatch.setenv('N8N_WEBHOOK_SECRET','test-inbox-secret')
    for _ in range(4):asyncio.run(automation.deliver_once(durable_sender,0))
    assert len([e for e in db.dump_events() if e['name']=='automation_configuration'])==1
    h=client.get('/health').json()
    assert h['automation_preflight']['reason']=='credentials_must_differ'
    assert 'test-inbox-secret' not in json.dumps(h)
    monkeypatch.setenv('N8N_WEBHOOK_SECRET','test-webhook-secret')
    with db.connect() as con:con.execute("UPDATE outbox SET state='sending',attempts=3,lease_until=0")
    asyncio.run(automation.deliver_once(durable_sender,1))
    failure=next(e for e in db.dump_events() if e['outcome']=='lease_expired')
    assert failure['request_id'] and failure['operation_id']
    automation.retry(tid)
    assert next(e for e in db.dump_events() if e['name']=='handoff_retry_requested')['request_id']==failure['request_id']

@pytest.mark.parametrize('field,value,reason',[('N8N_WEBHOOK_SECRET','','credentials_missing'),('N8N_WEBHOOK_URL','https://evil.test','url_not_allowed'),('FOODFLOW_INBOX_SECRET','DEMO-CUST-001','credentials_inadequate')])
def test_f05_preflight_codes(client,monkeypatch,field,value,reason):
    configured_ticket(client,monkeypatch);monkeypatch.setenv(field,value)
    assert automation.preflight()['reason']==reason
    assert asyncio.run(automation.deliver_once(durable_sender,0)) is False

def test_f03_capabilities_and_metadata(client,monkeypatch):
    assert client.get('/health').json()['capabilities']['ready'] is False
    monkeypatch.setenv('FOODFLOW_ALLOW_ONLINE_LLM','true');monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    assert agent.capabilities()['reason']=='provider_not_configured'
    body,tools=toolset()
    one=call();one.update(id='resp-offline',model='test-model',usage={'input_tokens':10,'output_tokens':5,'private':'do not expose'},secret='canary')
    asyncio.run(agent.respond(body,tools,Fake([one,DONE])))
    assert tools.provider_metadata[0]['usage']=={'input_tokens':10,'output_tokens':5}
    assert 'canary' not in json.dumps(tools.provider_metadata)

def test_f04_summary_comparison_and_mismatch():
    from backend.app.evaluation import summarize,compare
    rows=[{'case_id':str(i),'status':s,'effective_mode':'llm','provider_executed':True} for i,s in enumerate(['passed','passed','failed','skipped','skipped'])]
    s=summarize(rows);assert s['planned']==5 and s['pass_rate']['value']==2/3
    manifest={k:'same' for k in ('hashes','code_sha256','prompt_sha256','schemas_sha256','runner_sha256','scoring_sha256','scenario_now')}
    a=manifest|{'mode':'demo'};b=manifest|{'mode':'online'}
    r=compare(a,b,rows,rows);assert r['paired']==3 and r['delta']==0 and len(r['excluded'])==2
    assert compare(a,b|{'scoring_sha256':'other'},rows,rows)['delta'] is None
    assert compare(a,b|{'mode':'fake'},rows,rows)['status']=='Não comparável'
    assert summarize([{'status':'skipped'}])['execution_status']=='Não executado'

def test_f04_online_cli_cannot_inherit_consent(monkeypatch,tmp_path):
    from scripts.evaluate import main
    monkeypatch.setenv('FOODFLOW_ALLOW_ONLINE_LLM','true');monkeypatch.setenv('OPENAI_API_KEY','synthetic-canary')
    monkeypatch.setenv('OPENAI_MODEL','test-model')
    with pytest.raises(SystemExit):main(['--mode','online','--output',str(tmp_path)])

def test_f04_default_runner_no_network(monkeypatch,tmp_path):
    from scripts.evaluate import run
    async def forbidden(*a,**kw):raise AssertionError('Network forbidden')
    monkeypatch.setattr(agent.Provider,'respond',forbidden)
    monkeypatch.setenv('FOODFLOW_ALLOW_ONLINE_LLM','true')
    assert run('demo',tmp_path,selected={'ORD_OK_01'})['passed']==1
    assert run('fake',tmp_path,selected={'ORD_OK_01'})['passed']==1
    assert run('online',tmp_path)['skipped']==35


def test_f05_max_manual_cycles_and_attempt_ids(client,monkeypatch):
    tid=configured_ticket(client,monkeypatch)
    async def failed(*args):raise TimeoutError()
    for cycle in range(3):
        for stamp in (0,2,12):asyncio.run(automation.deliver_once(failed,stamp))
        if cycle<2:automation.retry(tid)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:automation.retry(tid)
    assert error.value.status_code==409
    events=db.dump_events();starts=[e for e in events if e['name']=='handoff_attempted']
    ends=[e for e in events if e['name']=='handoff_failed']
    assert len(starts)==len(ends)==9
    assert len({e['attempt_id'] for e in starts})==9
    assert {e['attempt_id'] for e in starts}=={e['attempt_id'] for e in ends}


def test_f05_worker_failure_visible_deduplicated(client,monkeypatch):
    stop=asyncio.Event();calls=0
    async def broken():
        nonlocal calls
        calls+=1
        if calls==3:stop.set()
        raise RuntimeError('synthetic secret must not appear')
    monkeypatch.setattr(automation,'deliver_once',broken)
    asyncio.run(automation.worker(stop))
    assert client.get('/health').json()['worker_state']=='failed'
    assert len([e for e in db.dump_events() if e['name']=='automation_worker'])==1
    assert 'synthetic secret' not in json.dumps(db.dump_events())


def test_f04_budget_provider_limit_and_uncertain_cost(monkeypatch):
    from backend.app.validation import BudgetProvider
    calls=[]
    async def fake(*args):
        calls.append(1)
        return {'usage':{'input_tokens':100,'output_tokens':1},'output':[]}
    monkeypatch.setattr(agent.Provider,'respond',fake)
    p=BudgetProvider(1,1,1,1)
    asyncio.run(p.respond([],[]))
    with pytest.raises(ValueError):asyncio.run(p.respond([],[]))
    assert len(calls)==1 and p.stopped=='budget_or_request_limit'
    async def lost(*args):raise TimeoutError()
    monkeypatch.setattr(agent.Provider,'respond',lost)
    p=BudgetProvider(2,1,1,1)
    with pytest.raises(TimeoutError):asyncio.run(p.respond([],[]))
    assert p.spent>0 and p.calls==1 and p.stopped=='provider_error_cost_uncertain'


def test_f04_http_transport_guard():
    import httpx
    with pytest.raises(AssertionError,match='Network is forbidden'):
        httpx.Client(trust_env=False).get('http://127.0.0.1:1')


def test_f02_malformed_tool_counts_shared_attempt(client):
    body,tools=toolset();bad=call();bad['output'][0]['arguments']='{' 
    message,mode,reason=asyncio.run(agent.respond(body,tools,Fake([bad])))
    assert mode=='demo' and reason=='invalid_tool_schema'
    assert len(tools.results)==2 and tools.results[0]['outcome']=='failed'
    assert 'ORD-1001' in message
