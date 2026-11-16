"""Capture real offline contract evidence; this does NOT execute n8n or a remote LLM."""
import asyncio,json,os,sys,tempfile,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app import automation,db,agent
from backend.app.services import Tools
from backend.app.schemas import ChatRequest

def main():
    saved=dict(os.environ)
    run_id=os.getenv('FOODFLOW_EVIDENCE_RUN_ID','contracts-'+uuid.uuid4().hex[:12])
    out=Path(os.getenv('FOODFLOW_VERIFICATION_DIR',str(ROOT/'artifacts/verification')));out.mkdir(parents=True,exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix='foodflow-contract-') as temp:
            os.environ.update(FOODFLOW_DB_PATH=str(Path(temp)/'demo.sqlite3'),FOODFLOW_WORKER='false',
                FOODFLOW_RUN_ID=run_id,FOODFLOW_ALLOW_ONLINE_LLM='false',N8N_WEBHOOK_URL='http://127.0.0.1:5678/webhook/local',
                N8N_WEBHOOK_SECRET='synthetic-webhook-test',FOODFLOW_INBOX_SECRET='synthetic-inbox-test')
            with TestClient(app) as c:
                auth={'customer_id':'CUST-001','demo_token':'DEMO-CUST-001'}
                body={**auth,'session_id':'evidence','message':'ORD-1002 atrasado'}
                chat=c.post('/api/v1/chat',json=body).json();a=chat['pending_action']
                ticket=c.post('/api/v1/actions/'+a['action_id']+'/confirm',json={**auth,'session_id':'evidence','action_token':a['action_token'],'idempotency_key':'evidence-key'}).json()
                states=[]
                def capture(label):
                    with db.connect() as con:
                        row=dict(con.execute('SELECT * FROM outbox').fetchone())
                        row.pop('lease_token',None)
                        states.append({'step':label,'outbox':row,'inbox_count':con.execute('SELECT COUNT(*) FROM inbox').fetchone()[0]})
                async def unavailable(*args):raise TimeoutError()
                capture('ticket_and_outbox_committed')
                for stamp in (0,2,12):asyncio.run(automation.deliver_once(unavailable,stamp))
                capture('three_attempts_exhausted')
                automation.retry(ticket['ticket_id'])
                async def lost_ack(url,payload,secret):
                    automation.receive(payload,'synthetic-inbox-test');raise TimeoutError()
                asyncio.run(automation.deliver_once(lost_ack,13));capture('receiver_committed_ack_lost')
                async def recovered(url,payload,secret):return automation.receive(payload,'synthetic-inbox-test')
                asyncio.run(automation.deliver_once(recovered,15));capture('same_event_recovered')
                assert states[-1]['inbox_count']==1 and states[-1]['outbox']['state']=='confirmed'
                (out/'automation-offline.json').write_text(json.dumps({'run_id':run_id,'scope':'Offline sender and durable local receiver; no n8n runtime','captured_at':db.now(),'states':states,'events':db.dump_events()},ensure_ascii=False,indent=2),encoding='utf-8')
                class Fake:
                    def __init__(self):self.inputs=[]
                    async def respond(self,items,tools):
                        self.inputs.append(json.loads(json.dumps(items)))
                        if len(self.inputs)==1:return {'output':[{'type':'function_call','name':'lookup_order','call_id':'offline-call','arguments':'{"order_id":"ORD-1001"}'}]}
                        return {'output':[{'type':'message','content':[{'type':'output_text','text':'Texto não exibido diretamente.'}]}]}
                b=ChatRequest(**auth,session_id='offline-agent',message='ORD-1001',requested_mode='llm')
                tools=Tools(b,{'request_id':str(uuid.uuid4()),'session_id':b.session_id,'run_id':run_id})
                fake=Fake();message,mode,fallback=asyncio.run(agent.respond(b,tools,fake))
                (out/'llm-offline.json').write_text(json.dumps({'run_id':run_id,'scope':'Simulated provider only; zero remote LLM requests','captured_at':db.now(),'provider_inputs':fake.inputs,'tools':tools.results,'sources':tools.sources,'rendered_message':message,'mode_in_test':mode,'fallback':fallback},ensure_ascii=False,indent=2),encoding='utf-8')
    finally:
        os.environ.clear();os.environ.update(saved)
    print('Offline artifacts: durable recovery/dedupe and function-call exchange captured.')
if __name__=='__main__':main()
