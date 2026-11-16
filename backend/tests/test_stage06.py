"""Offline checks for the live harness; these do not certify n8n execution."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sqlite3
import sys
import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_cleanup_preserves_metadata_and_refuses_non_discarded_runs(tmp_path):
    from scripts.validate_n8n_local import purge_discarded_payloads
    database=tmp_path/'runtime.sqlite'
    with sqlite3.connect(database) as con:
        con.executescript("CREATE TABLE workflow_entity(name TEXT); CREATE TABLE execution_entity(id INTEGER,deletedAt TEXT); CREATE TABLE execution_data(executionId INTEGER,data TEXT);")
        con.execute('INSERT INTO workflow_entity VALUES(?)',('FoodFlow local validation original',))
        con.execute('INSERT INTO execution_entity VALUES(1,NULL)')
        con.execute('INSERT INTO execution_data VALUES(1,?)',('synthetic-private',))
    with pytest.raises(ValueError,match='non_discarded'):purge_discarded_payloads(database)
    with sqlite3.connect(database) as con:
        assert con.execute('SELECT count(*) FROM execution_data').fetchone()[0]==1
        con.execute("UPDATE execution_entity SET deletedAt='2026-11-14'")
    result=purge_discarded_payloads(database)
    assert result['discarded_payload_rows_before']==1 and result['payload_rows_after']==0
    with sqlite3.connect(database) as con:
        assert con.execute('SELECT count(*) FROM execution_entity').fetchone()[0]==1
        con.execute("UPDATE workflow_entity SET name='Unrelated project'")
    with pytest.raises(ValueError,match='exclusive_synthetic'):purge_discarded_payloads(database)


def test_live_harness_refuses_without_explicit_flag(tmp_path):
    result=subprocess.run([sys.executable,str(ROOT/'scripts/validate_n8n_local.py'),
        '--runtime',str(tmp_path/'runtime'),'--private',str(tmp_path/'private'),
        '--output',str(tmp_path/'output')],capture_output=True,text=True,check=False)
    assert result.returncode==2 and 'BLOCKED' in result.stdout
    assert not (tmp_path/'private').exists() and not (tmp_path/'output').exists()


def test_live_environment_does_not_inherit_secrets(monkeypatch):
    from scripts.validate_n8n_local import clean_environment
    for key in ('OPENAI_API_KEY','N8N_ENCRYPTION_KEY','HTTP_PROXY','FOODFLOW_ALLOW_ONLINE_LLM'):
        monkeypatch.setenv(key,'synthetic-stage06-canary')
    result=clean_environment()
    assert result['FOODFLOW_ALLOW_ONLINE_LLM']==result['FOODFLOW_WORKER']=='false'
    assert 'synthetic-stage06-canary' not in json.dumps(result)


def test_runtime_hook_omits_headers_and_error_payloads(tmp_path):
    node=shutil.which('node')
    if not node:pytest.skip('Node unavailable for offline hook contract')
    destination=tmp_path/'evidence.jsonl'
    code="""
const hook=require(process.argv[1]);
const run={status:'error',data:{resultData:{error:{message:'synthetic-private'},runData:{
'Webhook autenticado':[{data:{main:[[{json:{headers:{authorization:'synthetic-private'},body:{event_id:'event-1',ticket_id:'ticket-1',secret:'synthetic-private'}}}]]}}],
'Persistir fila local':[{data:{main:[[{json:{record_id:'record-1',received:true}}]]}}]}}}};
hook.workflow.postExecute[0](run,{id:'workflow-1'},'12');
"""
    subprocess.run([node,'-e',code,str(ROOT/'scripts/n8n_evidence_hook.cjs')],
        env=os.environ|{'FOODFLOW_RUNTIME_EVIDENCE':str(destination)},check=True,capture_output=True)
    content=destination.read_text()
    assert 'synthetic-private' not in content and 'headers' not in content
    item=json.loads(content)
    assert item['execution_id']=='12' and item['event_id']=='event-1' and item['record_id']=='record-1'


def test_runtime_network_guard_blocks_external_before_connect(tmp_path):
    node=shutil.which('node')
    if not node:pytest.skip('Node unavailable for offline network guard contract')
    code="""
require(process.argv[1]);
try { require('node:net').connect({host:'203.0.113.1',port:443});process.exit(4); }
catch(e) { if (!e.message.includes('literal loopback'))process.exit(5); }
"""
    result=subprocess.run([node,'-e',code,str(ROOT/'scripts/n8n_local_guard.cjs')],
        capture_output=True,check=False)
    assert result.returncode==0


def test_runtime_network_guard_allows_literal_loopback():
    node=shutil.which('node')
    if not node:pytest.skip('Node unavailable for network guard contract')
    code="""
require(process.argv[1]);
const net=require('node:net');
const server=net.createServer(socket=>socket.end());
server.listen(0,'127.0.0.1',()=>{
  const client=net.connect({host:'127.0.0.1',port:server.address().port});
  client.on('end',()=>server.close());client.on('error',()=>process.exit(6));
});
"""
    result=subprocess.run([node,'-e',code,str(ROOT/'scripts/n8n_local_guard.cjs')],
        capture_output=True,check=False,timeout=10)
    assert result.returncode==0
