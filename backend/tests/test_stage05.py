"""Additional integration preparation checks; all transport remains simulated."""
import asyncio
import json
import os
from pathlib import Path
import pytest
import httpx
from backend.app import agent,automation,db
from backend.app.validation import BudgetProvider
from .test_api import configured_ticket,durable_sender,call,toolset


def test_cancelled_paid_attempt_stops_pilot(monkeypatch):
    async def cancelled(*args):raise asyncio.CancelledError()
    monkeypatch.setattr(agent.Provider,'respond',cancelled)
    provider=BudgetProvider(4,1,1,1)
    with pytest.raises(asyncio.CancelledError):asyncio.run(provider.respond([],[]))
    assert provider.stopped=='provider_cancelled_cost_uncertain'
    assert provider.spent>0 and provider.calls==1
    with pytest.raises(ValueError,match='pilot_stopped'):asyncio.run(provider.respond([],[]))


@pytest.mark.parametrize('status',[401,429,500,503])
def test_responses_http_failure_classified_without_retry(client,monkeypatch,status):
    monkeypatch.setenv('FOODFLOW_ALLOW_ONLINE_LLM','true')
    monkeypatch.setenv('OPENAI_API_KEY','synthetic-stage05-canary')
    monkeypatch.setenv('OPENAI_MODEL','offline-fixture-model')
    requests=[]
    original=httpx.AsyncClient
    def handler(request):
        requests.append(request)
        return httpx.Response(status,json={'error':{'message':'synthetic-stage05-canary'}})
    monkeypatch.setattr(agent.httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    body,tools=toolset()
    message,mode,reason=asyncio.run(agent.respond(body,tools,agent.Provider()))
    assert len(requests)==1 and mode=='demo' and reason=='provider_http_'+str(status)
    assert 'ORD-1001' in message
    assert 'synthetic-stage05-canary' not in json.dumps(db.dump_events())+message


def test_responses_transport_timeout_stops_budget(client,monkeypatch):
    monkeypatch.setenv('FOODFLOW_ALLOW_ONLINE_LLM','true')
    monkeypatch.setenv('OPENAI_API_KEY','synthetic-stage05-canary')
    monkeypatch.setenv('OPENAI_MODEL','offline-fixture-model')
    calls=[];original=httpx.AsyncClient
    def handler(request):calls.append(1);raise httpx.ReadTimeout('synthetic',request=request)
    monkeypatch.setattr(agent.httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    provider=BudgetProvider(4,1,1,1);body,tools=toolset()
    _,mode,reason=asyncio.run(agent.respond(body,tools,provider))
    assert mode=='demo' and reason=='provider_timeout' and len(calls)==1
    assert provider.stopped=='provider_error_cost_uncertain' and provider.spent>0


def test_missing_usage_stops_without_retry(monkeypatch):
    async def no_usage(*args):return call()
    monkeypatch.setattr(agent.Provider,'respond',no_usage)
    provider=BudgetProvider(4,1,1,1)
    with pytest.raises(ValueError,match='usage_unavailable'):asyncio.run(provider.respond([],[]))
    assert provider.stopped=='usage_unavailable' and provider.calls==1


def test_snapshot_only_selected_fields_not_live_proof(client,monkeypatch):
    from scripts.collect_n8n_evidence import snapshot
    configured_ticket(client,monkeypatch)
    asyncio.run(automation.deliver_once(durable_sender,0))
    with db.connect() as con:
        event_id=con.execute('SELECT event_id FROM outbox').fetchone()[0]
        token=con.execute('SELECT token FROM actions').fetchone()[0]
    result=snapshot(os.environ['FOODFLOW_DB_PATH'],event_id,'synthetic-execution','test-version')
    assert result['local_delivery_status']=='PASSED' and result['ack_matches_persisted_inbox']
    assert result['n8n_live']=='NOT_EXECUTED' and not result['runtime_reference_verified']
    assert token not in json.dumps(result) and 'test-inbox-secret' not in json.dumps(result)
    assert 'payload' not in result and 'lease_token' not in json.dumps(result)


def test_snapshot_missing_database_does_not_create(tmp_path):
    from scripts.collect_n8n_evidence import snapshot
    path=tmp_path/'missing.sqlite3'
    with pytest.raises(ValueError,match='database_missing'):snapshot(path,'synthetic-event')
    assert not path.exists()


def test_offline_launcher_does_not_inherit_consent():
    from scripts.run_local import offline_environment
    env={'OPENAI_API_KEY':'synthetic-canary','FOODFLOW_ALLOW_ONLINE_LLM':'true','FOODFLOW_WORKER':'true',
         'N8N_WEBHOOK_URL':'http://127.0.0.1:5678','FOODFLOW_INBOX_SECRET':'synthetic-private'}
    result=offline_environment(env,'synthetic.sqlite3')
    assert result['FOODFLOW_ALLOW_ONLINE_LLM']==result['FOODFLOW_WORKER']=='false'
    assert not any(k.startswith(('OPENAI_','N8N_')) for k in result)
    assert 'FOODFLOW_INBOX_SECRET' not in result and env['FOODFLOW_WORKER']=='true'


def test_worker_is_opt_in_even_when_url_exists(client,monkeypatch):
    from fastapi.testclient import TestClient
    from backend.app.main import app
    monkeypatch.delenv('FOODFLOW_WORKER',raising=False)
    monkeypatch.setenv('N8N_WEBHOOK_URL','http://127.0.0.1:5678/synthetic')
    calls=[]
    async def forbidden(*args):calls.append(1)
    monkeypatch.setattr(automation,'worker',forbidden)
    with TestClient(app) as another:
        assert another.get('/health').status_code==200
    assert calls==[]


def test_workflow_static_checks_do_not_approve_runtime():
    from scripts.integration_preflight import workflow_checks
    path=Path(__file__).resolve().parents[2]/'n8n/escalation_workflow.json'
    data=json.loads(path.read_text(encoding='utf-8'))
    assert all(workflow_checks(data).values())
    data['nodes'][1]['credentials']=data['nodes'][0]['credentials']
    assert not workflow_checks(data)['distinct_credential_references']


def test_variants_preserve_durable_inbox_and_are_inactive():
    from scripts.prepare_n8n_variants import variants
    path=Path(__file__).resolve().parents[2]/'n8n/escalation_workflow.json'
    data=json.loads(path.read_text(encoding='utf-8'));original=json.dumps(data)
    items=variants(data)
    for name,item in items.items():
        assert item['active'] is False and len(item['nodes'])==3
        assert item['nodes'][0]==data['nodes'][0] and item['nodes'][1]==data['nodes'][1]
        assert item['nodes'][2]['parameters']['options']['responseCode']==(504 if name.startswith('N05') else 200)
    assert json.dumps(data)==original


def test_worker_cli_refuses_without_authorization(tmp_path,monkeypatch):
    from scripts.n8n_worker_once import main
    monkeypatch.setenv('FOODFLOW_ALLOW_LIVE_N8N','true')
    monkeypatch.setenv('FOODFLOW_AUTHORIZATION_REF','synthetic-approval')
    assert main(['--database',str(tmp_path/'missing.db')])==2
    assert not (tmp_path/'missing.db').exists()


def test_pilot_is_separate_and_complete(monkeypatch,tmp_path):
    from scripts.evaluate import run,load_cases
    assert len(load_cases())==35
    assert [c['id'] for c in load_cases(True)]==[f'L{i:02}' for i in range(1,9)]
    async def forbidden(*args):raise AssertionError('No online provider allowed')
    monkeypatch.setattr(agent.Provider,'respond',forbidden)
    assert run('demo',tmp_path,pilot=True)['passed']==8
    assert run('fake',tmp_path,pilot=True)['passed']==8
    assert run('online',tmp_path,pilot=True)['skipped']==8
