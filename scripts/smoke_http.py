import json,uuid,os
from pathlib import Path
import httpx
base=os.getenv('FOODFLOW_BASE_URL','http://127.0.0.1:8000')
auth={'customer_id':'CUST-001','demo_token':'DEMO-CUST-001'}
session='http-smoke-'+str(uuid.uuid4())
checks=[]
with httpx.Client(base_url=base,trust_env=False) as c:
    assert c.get('/health').status_code==200
    for oid,code in [('ORD-1001',200),('ORD-1009',200),('ORD-1004',403)]:
        r=c.post('/api/v1/chat',json={**auth,'session_id':session,'message':oid})
        assert r.status_code==code
        checks.append({'name':oid,'status':r.status_code,'request_id':r.headers['x-request-id']})
    r=c.post('/api/v1/chat',json={**auth,'session_id':session,'message':'ORD-1002 atrasado'}).json()
    a=r['pending_action'];body={**auth,'session_id':session,'action_token':a['action_token'],'idempotency_key':session}
    first=c.post('/api/v1/actions/'+a['action_id']+'/confirm',json=body)
    second=c.post('/api/v1/actions/'+a['action_id']+'/confirm',json=body)
    assert first.status_code==second.status_code==200 and first.json()['ticket_id']==second.json()['ticket_id']
    tid=first.json()['ticket_id'];record=c.get('/api/v1/tickets/'+tid,params=auth).json()
    assert record['automation_state']=='not_configured'
    assert c.get('/').status_code==200 and c.get('/static/app.js').status_code==200
    checks.append({'name':'confirmed_ticket_and_repeat','ticket_id':tid,'event_id':record['event_id'],'state':record['automation_state']})
    metrics=c.get('/api/v1/metrics').json()
    checks.append({'name':'metrics','requests':metrics['total_interactions'],'sample':metrics['sample_size']})
    def oversized():
        yield b'a'*10000
        yield b'b'*10000
    r=c.post('/api/v1/chat',content=oversized())
    assert r.status_code==413 and r.headers['x-request-id']==r.json()['request_id']
    checks.append({'name':'actual_chunked_bytes_limit','status':413})
out=Path(os.getenv('FOODFLOW_VERIFICATION_DIR',str(Path(__file__).resolve().parents[1]/'artifacts/verification')));out.mkdir(parents=True,exist_ok=True)
(out/'http-smoke.json').write_text(json.dumps({'run_id':os.getenv('FOODFLOW_EVIDENCE_RUN_ID',session),'checks':checks},indent=2),encoding='utf-8')
print('HTTP smoke: 6 checks passed; persisted ticket and actual chunked body limit verified through TCP.')
