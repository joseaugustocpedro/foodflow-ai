"""Tests isolate every database and disable all external integrations."""
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('FOODFLOW_DB_PATH',str(tmp_path/'test.sqlite3'))
    monkeypatch.setenv('FOODFLOW_WORKER','false')
    monkeypatch.setenv('FOODFLOW_ALLOW_ONLINE_LLM','false')
    monkeypatch.setenv('FOODFLOW_RUN_ID','interactive')
    monkeypatch.delenv('N8N_WEBHOOK_URL',raising=False)
    with TestClient(app) as c:
        yield c

AUTH={'customer_id':'CUST-001','demo_token':'DEMO-CUST-001'}

def chat(c,message='ORD-1001',session='session',**extra):
    return c.post('/api/v1/chat',json={**AUTH,'session_id':session,'message':message,**extra})

def proposal(c,message='ORD-1002 está atrasado?',session='session'):
    r=chat(c,message,session)
    assert r.status_code==200,r.text
    return r.json()['pending_action']

def confirmation(c,a,key='same-key-123',session='session',auth=None):
    return c.post('/api/v1/actions/'+a['action_id']+'/confirm',json={**(auth or AUTH),'session_id':session,'action_token':a['action_token'],'idempotency_key':key})


def pytest_addoption(parser):
    parser.addoption('--run-online',action='store_true',default=False)
    parser.addoption('--run-n8n',action='store_true',default=False)


@pytest.fixture(autouse=True)
def no_accidental_network(request,monkeypatch):
    import socket
    import httpx
    allowed=(request.node.name=='test_llm_online' and request.config.getoption('--run-online')) or (request.node.name=='test_n8n_live' and request.config.getoption('--run-n8n'))
    if allowed:
        return
    def forbidden(*args,**kwargs):
        raise AssertionError('Network is forbidden in offline tests')
    async def async_forbidden(*args,**kwargs):
        forbidden()
    original=socket.socket.connect
    def local_runtime_only(sock,address):
        # Windows asyncio uses TCP loopback for its internal socketpair.
        if isinstance(address,tuple) and address[0] in ('127.0.0.1','::1'):
            return original(sock,address)
        forbidden()
    monkeypatch.setattr(socket.socket,'connect',local_runtime_only)
    monkeypatch.setattr(httpx.HTTPTransport,'handle_request',forbidden)
    monkeypatch.setattr(httpx.AsyncHTTPTransport,'handle_async_request',async_forbidden)
