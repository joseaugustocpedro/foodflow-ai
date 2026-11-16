"""Executable opt-in gates. Never invoked by the default test suite."""
import os
import time
import uuid
import httpx
from backend.app.automation import local_url


def llm_gate(output):
    from scripts.evaluate import main
    required=['FOODFLOW_AUTHORIZATION_REF','FOODFLOW_PILOT_CASES','FOODFLOW_MAX_REQUESTS',
              'FOODFLOW_BUDGET_USD','FOODFLOW_INPUT_PRICE','FOODFLOW_OUTPUT_PRICE']
    assert all(os.getenv(k) for k in required),'Explicit authorization and limits required'
    assert main(['--mode','online','--confirm-online','--output',str(output),
                 '--authorization-ref',os.environ[required[0]],'--cases',os.environ[required[1]],
                 '--max-requests',os.environ[required[2]],'--budget',os.environ[required[3]],
                 '--input-price-per-million',os.environ[required[4]],
                 '--output-price-per-million',os.environ[required[5]]])==0
    import json
    rows=[json.loads(line) for file in output.glob('*/results.jsonl') for line in file.read_text(encoding='utf-8').splitlines()]
    assert any(r.get('provider_executed') and r['status']=='passed' and r['effective_mode']=='llm' for r in rows)


def n8n_gate():
    assert os.getenv('FOODFLOW_ALLOW_LIVE_N8N')=='true' and os.getenv('FOODFLOW_AUTHORIZATION_REF'),'Live authorization required'
    assert os.getenv('FOODFLOW_N8N_VERSION'),'Record installed n8n version before running'
    url=local_url(os.environ['FOODFLOW_BASE_URL'])
    auth={'customer_id':'CUST-001','demo_token':'DEMO-CUST-001'}
    session='live-'+uuid.uuid4().hex
    with httpx.Client(base_url=url,trust_env=False,timeout=5,follow_redirects=False) as client:
        assert client.get('/health').json()['automation']=='configured_unverified'
        response=client.post('/api/v1/chat',json={**auth,'session_id':session,'message':'ORD-1002 atrasado','requested_mode':'demo'})
        response.raise_for_status();a=response.json()['pending_action']
        r=client.post('/api/v1/actions/'+a['action_id']+'/confirm',json={**auth,'session_id':session,'action_token':a['action_token'],'idempotency_key':session})
        r.raise_for_status();tid=r.json()['ticket_id']
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            r=client.get('/api/v1/tickets/'+tid,params=auth);r.raise_for_status();ticket=r.json()
            if ticket['automation_state']=='confirmed':
                assert any(e['name']=='handoff_acknowledged' for e in ticket['timeline'])
                assert ticket['event_id']
                return
            time.sleep(.5)
        raise AssertionError('Real runtime did not persist a validated ACK in 30s')
