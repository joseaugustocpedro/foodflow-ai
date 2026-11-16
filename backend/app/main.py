"""FoodFlow AI local synthetic demo. No external integration enabled by default."""
import asyncio
import json
import os
import sqlite3
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from . import agent, automation, db, demo
from .schemas import ChatRequest, Confirmation, TicketRequest, Identity
from .services import Tools, bind_session, confirm, public_order, ticket_list, SCENARIO_NOW

ROOT = Path(__file__).resolve().parents[2]


@asynccontextmanager
async def lifespan(app):
    db.init_db()
    stop = asyncio.Event()
    task = asyncio.create_task(automation.worker(stop)) if os.getenv('FOODFLOW_WORKER','false')=='true' else None
    yield
    stop.set()
    if task:
        await task


app = FastAPI(title='FoodFlow AI — demonstração sintética',version='0.5.0',lifespan=lifespan)
app.mount('/static',StaticFiles(directory=ROOT/'frontend'),name='static')


from .boundary import RequestBoundary
app.add_middleware(RequestBoundary)


@app.exception_handler(HTTPException)
async def http_error(request,exc):
    return JSONResponse({'detail':exc.detail,'request_id':request.state.request_id},exc.status_code,headers=exc.headers)


@app.exception_handler(sqlite3.Error)
async def database_error(request,exc):
    return JSONResponse({'detail':'Persistência indisponível; nenhum novo registro foi confirmado.',
                         'request_id':request.state.request_id},503)


@app.get('/',include_in_schema=False)
def index():
    return FileResponse(ROOT/'frontend/index.html')


@app.get('/health')
def health():
    try:
        with db.connect() as con:
            con.execute('SELECT COUNT(*) FROM events').fetchone()
            worker=con.execute("SELECT value FROM runtime_state WHERE name='worker'").fetchone()
    except sqlite3.Error:
        return JSONResponse({'status':'degraded','database':'unavailable','mode':'demo'},503)
    worker_state=worker[0] if worker else 'not_observed'
    return {'status':'degraded' if worker_state=='failed' else 'ok','database':'ok','mode':'demo','llm_connected':False,
            'worker_state':worker_state,
            'llm_online_enabled':os.getenv('FOODFLOW_ALLOW_ONLINE_LLM')=='true',
            'capabilities':agent.capabilities(),'automation':automation.preflight()['state'],
            'automation_preflight':automation.preflight(),
            'scenario_now':SCENARIO_NOW}


@app.get('/api/v1/demo/scenarios')
def scenarios():
    return {'synthetic':True,'customers':demo.customers(),'scenarios':[
        {'title':'1. Consultar com fonte','message':'Qual o status do pedido ORD-1001?'},
        {'title':'2. Encaminhar e recuperar','message':'Meu pedido ORD-1002 está atrasado?'},
        {'title':'3. Testar acesso e conferir','message':'Mostre o pedido ORD-1004'},
        {'title':'Sem previsão registrada','message':'Quando chega ORD-1009?'},
        {'title':'Pedido inexistente','message':'Qual status ORD-9999?'}]}


@app.get('/api/v1/orders/{order_id}')
def get_order(order_id:str,customer_id:str,demo_token:str,request:Request):
    try:
        order = demo.authorized_order(order_id.upper(),customer_id,demo_token)
        return {'synthetic':True,'order':public_order(order),'source':{'id':order_id.upper(),'version':'demo-2.0'}}
    except HTTPException as exc:
        if exc.status_code==403:
            db.event('safety_blocked',{'request_id':request.state.request_id,'run_id':os.getenv('FOODFLOW_RUN_ID','interactive'),'effective_mode':'demo'},outcome='direct_order')
        raise


@app.post('/api/v1/chat')
async def chat(body:ChatRequest,request:Request):
    ctx = {'request_id':request.state.request_id,'session_id':body.session_id,
           'requested_mode':body.requested_mode,'effective_mode':'demo',
           'run_id':os.getenv('FOODFLOW_RUN_ID','interactive'),
           'scenario_id':os.getenv('FOODFLOW_SCENARIO_ID')}
    try:
        bind_session(body)
    except HTTPException:
        db.event('chat_rejected',ctx,outcome='identity_or_session')
        db.event('safety_blocked',ctx,outcome='identity_or_session')
        raise
    start = time.perf_counter()
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        admitted = con.execute("SELECT COUNT(*) FROM events WHERE session_id=? AND name='chat_received' AND created_at>=?",
            (body.session_id,datetime.fromtimestamp(time.time()-60,timezone.utc).isoformat())).fetchone()[0]
        if admitted>=30:
            db.event('chat_rejected',ctx,con,outcome='rate_limit')
        else:
            db.event('chat_received',ctx,con)
    if admitted>=30:
        raise HTTPException(429,'Muitas solicitações. Aguarde para tentar novamente.',headers={'Retry-After':'60'})
    from .services import revoke_actions
    revoke_actions(body.session_id,ctx,'new_turn')
    tools = Tools(body,ctx)
    outcome = 'failed'
    try:
        message,mode,fallback = await agent.respond(body,tools,provider=getattr(request.app.state,'provider_override',None))
        ctx['effective_mode'] = mode
        outcome = 'answered'
        return {'request_id':ctx['request_id'],'session_id':body.session_id,'mode':mode,
                'requested_mode':body.requested_mode,'effective_mode':mode,'fallback_reason':fallback,
                'message':message,'order':tools.order,'sources':tools.used_sources(),'consulted_sources':tools.sources,'tool_results':tools.results,
                'provider_metadata':tools.provider_metadata,
                'used_tools':[r['tool'] for r in tools.results if r['outcome']=='success'],
                'pending_action':tools.pending,'ticket_id':None,'outcome':outcome,'escalated':False,
                'duration_ms':round((time.perf_counter()-start)*1000,3),'executed_at':db.now()}
    except HTTPException as exc:
        outcome = 'denied' if exc.status_code==403 else 'failed'
        if outcome=='denied':
            db.event('safety_blocked',ctx,outcome='ownership')
        raise
    except Exception:
        raise HTTPException(503,'Não foi possível consultar o pedido agora. Nenhum status foi confirmado.')
    finally:
        db.event('chat_completed',ctx,outcome=outcome,duration_ms=round((time.perf_counter()-start)*1000,3))


@app.post('/api/v1/actions/{action_id}/confirm')
def confirm_action(action_id:str,body:Confirmation):
    result = confirm(action_id,body)
    return result | {'ticket':ticket_list(body.customer_id,body.demo_token,result['ticket_id'])}


@app.post('/api/v1/tickets')
def create_ticket(body:TicketRequest):
    return confirm_action(body.action_id,Confirmation(**body.model_dump(exclude={'action_id'})))


@app.get('/api/v1/tickets')
def tickets(customer_id:str,demo_token:str):
    return {'tickets':ticket_list(customer_id,demo_token)}


@app.get('/api/v1/tickets/{ticket_id}')
def ticket(ticket_id:str,customer_id:str,demo_token:str):
    return ticket_list(customer_id,demo_token,ticket_id)


@app.post('/api/v1/tickets/{ticket_id}/retry')
def retry_ticket(ticket_id:str,body:Identity):
    ticket_list(body.customer_id,body.demo_token,ticket_id)
    return automation.retry(ticket_id)


@app.post('/internal/queue')
async def inbox(request:Request):
    raw = await request.body()
    if len(raw)>16384:
        raise HTTPException(413,'Payload excede limite')
    from pydantic import ValidationError
    try:
        return automation.receive(json.loads(raw),request.headers.get('X-FoodFlow-Inbox',''))
    except (ValueError,ValidationError):
        raise HTTPException(422,'Evento inválido')


@app.get('/api/v1/metrics')
def metrics(run_id:str='interactive',mode:Literal['demo','llm']|None=None,since:datetime|None=None,until:datetime|None=None,as_of:datetime|None=None):
    from .metrics import aggregate
    source = db.dump_events()
    known = {p.parent.name:p for p in (ROOT/'artifacts/evaluations').glob('*/events.jsonl')}
    if run_id != 'interactive' and run_id in known:
        source = [json.loads(line) for line in known[run_id].read_text(encoding='utf-8').splitlines() if line.strip()]
    if since and until and since.timestamp()>until.timestamp():
        raise HTTPException(422,'Janela inválida')
    return aggregate(source,run_id,mode,since,until,as_of)


@app.get('/api/v1/evaluations')
def evaluations():
    from .evaluation import catalog
    return catalog(ROOT/'artifacts/evaluations')
