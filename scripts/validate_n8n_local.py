"""Supervised N01-N08 native loopback validation; explicit CLI consent required.

Uses an already installed isolated runtime. Never downloads, installs, calls LLM,
or reads existing service credentials. New secrets stay in memory/private runtime.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import socket
import sqlite3
import subprocess
import sys
import time
import uuid
import hashlib
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import httpx

ROOT = Path(__file__).resolve().parents[1]
AUTH = {'customer_id':'CUST-001','demo_token':'DEMO-CUST-001'}
HIDDEN = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def clean_environment():
    allowed = {'SYSTEMROOT','WINDIR','COMSPEC','TEMP','TMP','PATHEXT','SYSTEMDRIVE'}
    env = {k:v for k,v in os.environ.items() if k.upper() in allowed}
    env.update(FOODFLOW_ALLOW_ONLINE_LLM='false', FOODFLOW_WORKER='false', PYTHONUTF8='1')
    return env


def read_rows(database, query, args=()):
    with sqlite3.connect(Path(database).as_uri()+'?mode=ro',uri=True) as con:
        con.row_factory=sqlite3.Row
        return [dict(row) for row in con.execute(query,args)]


def wait_until(check, timeout=30):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        value=check()
        if value:return value
        time.sleep(.05)
    raise RuntimeError('condition_timeout')


def purge_discarded_payloads(database):
    """Runtime must be stopped. Purge only soft-deleted runs in this synthetic DB.

    n8n save=none is soft deletion, not immediate erasure. Retain metadata for
    correlation; never copy execution_data to the evidence directory.
    """
    with sqlite3.connect(database) as con:
        con.execute('PRAGMA secure_delete=ON')
        workflows=con.execute('SELECT name FROM workflow_entity').fetchall()
        if any(not name.startswith('FoodFlow local validation ') for (name,) in workflows):
            raise ValueError('not_exclusive_synthetic_runtime')
        if con.execute('SELECT count(*) FROM execution_entity WHERE deletedAt IS NULL').fetchone()[0]:
            raise ValueError('runtime_contains_non_discarded_executions')
        before=con.execute('SELECT count(*) FROM execution_data').fetchone()[0]
        con.execute('DELETE FROM execution_data WHERE executionId IN (SELECT id FROM execution_entity WHERE deletedAt IS NOT NULL)')
        con.commit()
        after=con.execute('SELECT count(*) FROM execution_data').fetchone()[0]
        con.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        con.execute('VACUUM')
        return {'discarded_payload_rows_before':before,'payload_rows_after':after,
                'execution_metadata_preserved':True,'secure_delete':True,
                'limit':'Local SQLite cleanup, not a forensic disk-erasure guarantee'}


class Validation:
    def __init__(self, runtime, private, output):
        self.runtime=runtime.resolve(); self.private=private.resolve(); self.output=output.resolve()
        if self.private.is_relative_to(ROOT) or self.runtime.is_relative_to(ROOT):
            raise ValueError('Private runtime and databases must be outside the exportable project')
        self.private.mkdir(parents=True,exist_ok=False); self.output.mkdir(parents=True,exist_ok=True)
        self.run_id='stage06-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+uuid.uuid4().hex[:6]
        self.node=self.runtime/'node-v24.22.3-win-x64/node.exe'
        self.cli=self.runtime/'n8n/node_modules/n8n/bin/n8n'
        self.env=clean_environment()
        self.env.update(PATH=str(self.node.parent), USERPROFILE=str(self.private), HOME=str(self.private),
            APPDATA=str(self.private/'appdata'),LOCALAPPDATA=str(self.private/'localappdata'),
            N8N_USER_FOLDER=str(self.private),N8N_LISTEN_ADDRESS='127.0.0.1',N8N_HOST='127.0.0.1',
            N8N_PORT='5678',N8N_PROTOCOL='http',WEBHOOK_URL='http://127.0.0.1:5678/',
            N8N_EDITOR_BASE_URL='http://127.0.0.1:5678',N8N_SECURE_COOKIE='false',
            N8N_DIAGNOSTICS_ENABLED='false',N8N_VERSION_NOTIFICATIONS_ENABLED='false',
            N8N_TEMPLATES_ENABLED='false',N8N_DIAGNOSTICS_CONFIG_FRONTEND='',
            N8N_DIAGNOSTICS_CONFIG_BACKEND='',EXTERNAL_FRONTEND_HOOKS_URLS='',
            N8N_LICENSE_AUTO_RENEW_ENABLED='false',N8N_COMMUNITY_PACKAGES_ENABLED='false',
            N8N_RUNNERS_MODE='external',N8N_RUNNERS_BROKER_LISTEN_ADDRESS='127.0.0.1',
            N8N_RUNNERS_AUTH_TOKEN=secrets.token_urlsafe(32),
            N8N_ENCRYPTION_KEY=secrets.token_hex(32),
            EXECUTIONS_DATA_SAVE_ON_SUCCESS='none',EXECUTIONS_DATA_SAVE_ON_ERROR='none',
            EXECUTIONS_DATA_SAVE_MANUAL_EXECUTIONS='false',N8N_LOG_LEVEL='warn',
            EXTERNAL_HOOK_FILES=str(ROOT/'scripts/n8n_evidence_hook.cjs'),EXTERNAL_HOOK_FILES_SEPARATOR=';',
            FOODFLOW_RUNTIME_EVIDENCE=str(self.output/'runtime-executions.jsonl'),
            FOODFLOW_NETWORK_AUDIT=str(self.output/'network-boundary.jsonl'),
            NODE_OPTIONS='--require '+json.dumps((ROOT/'scripts/n8n_local_guard.cjs').as_posix(),ensure_ascii=False))
        self.secret=secrets.token_urlsafe(32);self.inbox_secret=secrets.token_urlsafe(32)
        self.wrong=secrets.token_urlsafe(32)
        self.n8n=None;self.backend=None;self.logs=[];self.cases=[]
        self.client=httpx.Client(base_url='http://127.0.0.1:5678',trust_env=False,timeout=30)
        self.food=httpx.Client(base_url='http://127.0.0.1:8000',trust_env=False,timeout=10)
        self.original=json.loads((ROOT/'n8n/escalation_workflow.json').read_text(encoding='utf-8'))
        self.workflow_id=None;self.database=None
        self.current_case='runtime_setup'

    def cli_run(self,*args):
        result=subprocess.run([str(self.node),str(self.cli),*args],cwd=ROOT,env=self.env,
            capture_output=True,timeout=120,creationflags=HIDDEN)
        if result.returncode:
            (self.private/'cli-error-private.log').write_bytes(result.stdout+result.stderr)
            raise RuntimeError('n8n_cli_failed')
        return result.stdout.decode('utf-8',errors='replace').strip()

    def spawn(self,cmd,env,label):
        log=(self.private/(label+'.log')).open('ab');self.logs.append(log)
        return subprocess.Popen(cmd,cwd=ROOT,env=env,stdout=log,stderr=log,creationflags=HIDDEN)

    @staticmethod
    def stop(proc):
        if proc and proc.poll() is None:
            proc.terminate()
            try:proc.wait(timeout=10)
            except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)

    def start_n8n(self):
        self.n8n=self.spawn([str(self.node),str(self.cli),'start'],self.env,'n8n')
        def ready():
            if self.n8n.poll() is not None:raise RuntimeError('n8n_start_failed')
            try:return self.client.get('/healthz/readiness').status_code==200
            except httpx.HTTPError:return False
        wait_until(ready,90)

    def request(self,method,path,**kwargs):
        response=self.client.request(method,path,**kwargs)
        if response.status_code>=400:
            # Local private diagnostic only; never export raw runtime errors.
            (self.private/'rest-error-private.log').write_bytes(response.content)
            raise RuntimeError('n8n_rest_'+str(response.status_code))
        body=response.json()
        return body.get('data',body)

    def setup(self):
        for port in (5678,5679,8000,8006):
            with socket.socket() as sock:
                if sock.connect_ex(('127.0.0.1',port))==0:raise RuntimeError('required_loopback_port_in_use')
        version=self.cli_run('--version')
        if version!='2.47.7':raise RuntimeError('unexpected_n8n_version')
        self.start_n8n()
        self.request('POST','/rest/owner/setup',json={'email':'foodflow@example.invalid',
            'firstName':'FoodFlow','lastName':'Synthetic','password':'Aa1!'+secrets.token_urlsafe(24)})
        self.credentials={}
        for label,name,value in [('webhook','X-FoodFlow-Webhook',self.secret),
                                 ('inbox','X-FoodFlow-Inbox',self.inbox_secret),
                                 ('wrong','X-FoodFlow-Inbox',self.wrong)]:
            item=self.request('POST','/rest/credentials',json={'name':'FoodFlow synthetic '+label,
                'type':'httpHeaderAuth','data':{'name':name,'value':value}})
            self.credentials[label]={'id':item['id'],'name':item['name']}
        self.configure('original',initial=True)
        (self.output/'runtime.json').write_text(json.dumps({'run_id':self.run_id,'n8n_version':version,
            'node_version':'24.22.3','bind':'127.0.0.1','retention':'save=none; soft-deleted payloads purged after runtime stops',
            'workflow_original_sha256':hashlib.sha256((ROOT/'n8n/escalation_workflow.json').read_bytes()).hexdigest(),
            'llm_online':'NOT_EXECUTED'},indent=2),encoding='utf-8')

    def configure(self,variant,initial=False):
        workflow=json.loads(json.dumps(self.original))
        workflow['name']='FoodFlow local validation '+variant
        workflow['nodes'][0]['credentials']['httpHeaderAuth']=self.credentials['webhook']
        workflow['nodes'][1]['credentials']['httpHeaderAuth']=self.credentials['wrong' if variant=='wrong_inbox' else 'inbox']
        if variant=='lost_ack':workflow['nodes'][2]['parameters']['options']['responseCode']=504
        if variant=='invalid_ack':workflow['nodes'][2]['parameters']['responseBody']='={{ {} }}'
        if initial:
            item=self.request('POST','/rest/workflows',json=workflow)
            self.workflow_id=item['id']
        else:
            self.request('POST',f'/rest/workflows/{self.workflow_id}/deactivate',json={})
            item=self.request('PATCH',f'/rest/workflows/{self.workflow_id}',json=workflow)
        # Export only public template and version hash, not credential identifiers/data.
        sanitized=json.loads(json.dumps(workflow))
        for i in (0,1):sanitized['nodes'][i]['credentials']=self.original['nodes'][i]['credentials']
        (self.output/('workflow-'+variant+'.json')).write_text(json.dumps(sanitized,indent=2),encoding='utf-8')
        self.request('POST',f'/rest/workflows/{self.workflow_id}/activate',json={'versionId':item['versionId']})

    def new_case(self,name):
        self.current_case=name
        self.stop(self.backend)
        self.database=self.private/(name+'.sqlite3')
        if self.database.exists():raise RuntimeError('existing_case_database')
        self.case_env=clean_environment() | {'FOODFLOW_DB_PATH':str(self.database),
            'N8N_WEBHOOK_URL':'http://127.0.0.1:5678/webhook/foodflow-demo-escalation',
            'N8N_WEBHOOK_SECRET':self.secret,'FOODFLOW_INBOX_SECRET':self.inbox_secret,
            'FOODFLOW_ALLOW_LIVE_N8N':'true','FOODFLOW_AUTHORIZATION_REF':'stage06-user-A-B',
            'FOODFLOW_RUN_ID':self.run_id,'FOODFLOW_SCENARIO_ID':name}
        self.backend=self.spawn([sys.executable,'-m','uvicorn','backend.app.main:app','--host','127.0.0.1',
            '--port','8000','--no-access-log'],self.case_env,'backend-'+name)
        def ready():
            try:return self.food.get('/health').status_code==200
            except httpx.HTTPError:return False
        wait_until(ready)
        self.session='live-'+uuid.uuid4().hex
        result=self.food.post('/api/v1/chat',json=AUTH|{'session_id':self.session,'message':'ORD-1002 atrasado','requested_mode':'demo'})
        assert result.status_code==200 and result.json()['effective_mode']=='demo'
        assert not read_rows(self.database,'SELECT ticket_id FROM tickets')
        action=result.json()['pending_action']
        confirmed=self.food.post('/api/v1/actions/'+action['action_id']+'/confirm',json=AUTH|{
            'session_id':self.session,'action_token':action['action_token'],'idempotency_key':self.session})
        assert confirmed.status_code==200
        self.ticket=confirmed.json()['ticket_id']
        self.event=self.row()['event_id']
        self.snapshots=[]
        self.capture('queued')

    def row(self):return read_rows(self.database,'SELECT * FROM outbox')[0]

    def capture(self,label):
        sys.path.insert(0,str(ROOT))
        from scripts.collect_n8n_evidence import snapshot
        item=snapshot(self.database,self.event)
        item['label']=label
        # These are persistence snapshots, explicitly not standalone runtime proof.
        self.snapshots.append(item)
        return item

    def worker(self,**overrides):
        env=self.case_env|overrides
        return self.spawn([sys.executable,'scripts/n8n_worker_once.py','--confirm-live',
            '--authorization-ref','stage06-user-A-B','--database',str(self.database)],env,'worker')

    def deliver(self,**overrides):
        delay=self.row()['next_at']-time.time()
        if delay>0:time.sleep(delay+.05)
        proc=self.worker(**overrides)
        assert proc.wait(timeout=15)==0
        return self.capture('attempt-'+str(self.row()['attempts']))

    def confirmed(self):
        snap=self.capture('confirmed')
        assert snap['ack_matches_persisted_inbox'] and self.row()['state']=='confirmed'
        assert len(read_rows(self.database,'SELECT * FROM tickets'))==len(read_rows(self.database,'SELECT * FROM inbox'))==1

    def finish_case(self,name,details=None):
        def records():
            path=self.output/'runtime-executions.jsonl'
            if not path.exists():return []
            return [row for line in path.read_text(encoding='utf-8').splitlines()
                    if (row:=json.loads(line)).get('event_id')==self.event]
        runtime=records() if name=='N02' else wait_until(records)
        if name=='N03':assert any(row['error_present'] for row in runtime)
        item={'case_id':name,'status':'PASSED','event_id':self.event,'ticket_id':self.ticket,
              'snapshots':self.snapshots,'runtime_executions':runtime,'details':details or {}}
        self.cases.append(item)
        self.save()
        print(name+' PASSED',flush=True)

    def save(self):
        (self.output/'cases.json').write_text(json.dumps({'run_id':self.run_id,'cases':self.cases},indent=2),encoding='utf-8')

    def run(self):
        self.setup()
        self.new_case('N01');self.deliver();self.confirmed();self.finish_case('N01')
        self.new_case('N02');self.deliver(N8N_WEBHOOK_SECRET=self.wrong)
        assert self.row()['state']=='pending' and not read_rows(self.database,'SELECT * FROM inbox')
        response=self.client.post('/webhook/foodflow-demo-escalation',json=json.loads(self.row()['payload']),
                                  headers={'X-FoodFlow-Webhook':self.wrong})
        assert response.status_code in (401,403)
        self.finish_case('N02',{'fault':'wrong webhook credential; runtime rejects before workflow','http_status':response.status_code})
        self.configure('wrong_inbox');self.new_case('N03');self.deliver()
        assert self.row()['state']=='pending' and not read_rows(self.database,'SELECT * FROM inbox')
        self.finish_case('N03');self.configure('original')
        self.new_case('N04');self.stop(self.n8n)
        for _ in range(3):self.deliver()
        assert self.row()['state']=='failed' and self.row()['attempts']==3
        self.start_n8n()
        assert self.food.post('/api/v1/tickets/'+self.ticket+'/retry',json=AUTH).status_code==200
        self.deliver();self.confirmed();self.finish_case('N04',{'recovery':'runtime process stopped/restarted; same event'})
        self.configure('lost_ack');self.new_case('N05');self.deliver()
        assert self.row()['state']=='pending' and len(read_rows(self.database,'SELECT * FROM inbox'))==1
        record=read_rows(self.database,'SELECT record_id FROM inbox')[0]['record_id']
        self.configure('original');self.deliver();self.confirmed()
        assert record==read_rows(self.database,'SELECT record_id FROM inbox')[0]['record_id']
        self.finish_case('N05',{'fault':'real n8n returns controlled HTTP504 after inbox commit'})
        self.lease_case()
        self.configure('invalid_ack');self.new_case('N07');self.deliver()
        assert self.row()['state']=='pending' and self.row()['ack'] is None
        self.configure('original');self.deliver();self.confirmed();self.finish_case('N07')
        self.new_case('N08');self.deliver();self.confirmed()
        payload=json.loads(self.row()['payload']);codes=[]
        with httpx.Client(trust_env=False,timeout=5) as client:
            for label,body in [('replay',payload),('extra',payload|{'customer_id':'CUST-001'}),
                               ('missing_event',payload|{'event_id':str(uuid.uuid4())}),
                               ('conflict',payload|{'reason_code':'refund'})]:
                response=client.post(self.case_env['N8N_WEBHOOK_URL'],json=body,headers={'X-FoodFlow-Webhook':self.secret})
                if label=='replay':
                    assert response.status_code==200 and response.json()['record_id']==read_rows(self.database,'SELECT record_id FROM inbox')[0]['record_id']
                else:
                    assert response.status_code!=200 or response.json().get('received') is not True
                assert len(read_rows(self.database,'SELECT * FROM inbox'))==1
                codes.append({'variant':label,'http_status':response.status_code})
        self.finish_case('N08',{'requests':codes})

    def lease_case(self):
        self.new_case('N06')
        outer=self;received=threading.Event();release=threading.Event()
        class Relay(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                body=self.rfile.read(int(self.headers['Content-Length']))
                with httpx.Client(trust_env=False,timeout=5) as client:
                    result=client.post(outer.case_env['N8N_WEBHOOK_URL'],content=body,
                        headers={'Content-Type':'application/json','X-FoodFlow-Webhook':outer.secret})
                assert result.status_code==200 and result.json()['received'] is True
                received.set();release.wait(5)
                try:
                    self.send_response(result.status_code);self.end_headers();self.wfile.write(result.content)
                except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):pass
        relay=ThreadingHTTPServer(('127.0.0.1',8006),Relay)
        thread=threading.Thread(target=relay.serve_forever,daemon=True);thread.start()
        interruptions=[]
        try:
            # Three actual process deaths, real lease waits; no database clock editing.
            for index in range(3):
                received.clear();release.clear()
                proc=self.worker(N8N_WEBHOOK_URL='http://127.0.0.1:8006/relay')
                assert received.wait(10)
                assert self.row()['state']=='sending'
                self.stop(proc);release.set()
                interruptions.append({'attempt':index+1,'worker_pid':proc.pid,'process_stopped':proc.poll() is not None})
                self.capture('process-interrupted-'+str(index+1))
                time.sleep(max(0,self.row()['lease_until']-time.time())+.1)
            self.deliver()
            assert self.row()['state']=='failed' and self.row()['attempts']==3 and self.row()['error']=='lease_expired'
            assert self.food.post('/api/v1/tickets/'+self.ticket+'/retry',json=AUTH).status_code==200
            self.deliver();self.confirmed()
            self.finish_case('N06',{'fault':'loopback TCP relay holds genuine n8n ACK after commit; kill worker PID',
                'interruptions':interruptions,'lease_clock':'real; no timestamp or state edits'})
        finally:release.set();relay.shutdown();relay.server_close();thread.join(timeout=5)

    def close(self):
        self.stop(self.backend);self.stop(self.n8n)
        self.client.close();self.food.close()
        for log in self.logs:log.close()
        database=self.private/'.n8n/database.sqlite'
        if database.exists():
            cleanup=purge_discarded_payloads(database)
            (self.output/'retention-cleanup.json').write_text(json.dumps(cleanup,indent=2),encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-local-n8n',action='store_true')
    for name in ('runtime','private','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    if not args.confirm_local_n8n:
        print('BLOCKED: explicit authorization for local runtime and synthetic tests required');return 2
    runner=Validation(args.runtime,args.private,args.output)
    try:runner.run()
    except Exception as exc:
        # Diagnostic class only. Never emit provider/runtime body or a secret.
        runner.cases.append({'case_id':runner.current_case,'status':'FAILED','reason':type(exc).__name__})
        runner.save()
        print('Validation interrupted: '+type(exc).__name__+'; inspect private diagnostics locally.',flush=True)
        raise
    finally:runner.close()
    return 0


if __name__=='__main__':raise SystemExit(main())
