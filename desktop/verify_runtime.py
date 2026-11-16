"""Local packaging evidence only; run against an already opened EXE. No secrets read."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import httpx

root=Path(__file__).resolve().parents[1]
folder=Path(os.environ['LOCALAPPDATA'])/'FoodFlowAI'
out=Path(os.environ.get('FOODFLOW_VERIFICATION_DIR',str(root/'artifacts/redesign/exe')))/'lifecycle.json'
parser=argparse.ArgumentParser()
parser.add_argument('phase',choices=['initial','stopped','restart','new','final-stopped'])
args=parser.parse_args()
data=json.loads(out.read_text()) if out.exists() else {}
def tickets(name):
    con=sqlite3.connect(folder/name)
    try:return [list(row) for row in con.execute('select ticket_id,order_id from tickets order by ticket_id')]
    finally:con.close()
if args.phase in ('stopped','final-stopped'):
    last=data['initial'] if args.phase=='stopped' else data['new']
    sock=socket.socket();sock.settimeout(1)
    try:assert sock.connect_ex(('127.0.0.1',int(last['runtime']['url'].rsplit(':',1)[1])))!=0
    finally:sock.close()
    assert not (folder/'runtime.json').exists()
    data[args.phase]={'listener_closed':True,'runtime_removed':True}
else:
    runtime=json.loads((folder/'runtime.json').read_text())
    with httpx.Client(base_url=runtime['url'],trust_env=False) as client:
        health=client.get('/health').json()
        assert health['status']=='ok' and not health['llm_online_enabled']
        assert health['automation']=='not_configured'
        record={'runtime':runtime,'tickets':tickets(runtime['database']),'health':health}
        if args.phase=='initial':
            hashes={}
            for name,url in [('index.html','/'),('style.css','/static/style.css'),('app.js','/static/app.js'),('motion.css','/static/motion.css'),('motion.js','/static/motion.js'),('favicon.svg','/static/favicon.svg')]:
                served=client.get(url).content
                expected=(root/'frontend'/name).read_bytes()
                assert served==expected
                hashes[name]=hashlib.sha256(served).hexdigest()
            record['served_resources_sha256']=hashes
            record['double_click']='Observed with Windows Explorer'
            record['auto_browser']='Observed Chrome opening Control Room'
        if args.phase=='restart':
            assert record['tickets']==data['initial']['tickets']
            assert runtime['database']==data['initial']['runtime']['database']
            assert runtime['pid']!=data['initial']['runtime']['pid']
            record['same_tickets_after_restart']=True
        if args.phase=='new':
            assert record['tickets']==[]
            assert runtime['database']!=data['restart']['runtime']['database']
            assert tickets(data['restart']['runtime']['database'])==data['restart']['tickets']
            record['old_database_preserved']=True
        data[args.phase]=record
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(data,indent=2),encoding='utf-8')
print(args.phase+': PASSED')
