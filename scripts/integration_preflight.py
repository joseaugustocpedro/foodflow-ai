"""Read-only local prerequisites. No credentials, network, npm/npx or n8n execution."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
from datetime import datetime, timezone
import uuid

ROOT=Path(__file__).resolve().parents[1]


def workflow_checks(data):
    nodes={n['id']:n for n in data.get('nodes',[])}
    if set(nodes)!={'webhook','persist','ack'}:
        return {'three_nodes':False}
    a,b,c=(nodes[k] for k in ('webhook','persist','ack'))
    return {
        'three_nodes':True,'inactive_template':data.get('active') is False,
        'webhook_authenticated':a['parameters'].get('authentication')=='headerAuth',
        'inbox_authenticated':b['parameters'].get('genericAuthType')=='httpHeaderAuth',
        'distinct_credential_references':a['credentials']['httpHeaderAuth']['id']!=b['credentials']['httpHeaderAuth']['id'],
        'callback_literal_loopback':b['parameters'].get('url')=='http://127.0.0.1:8000/internal/queue',
        'ack_after_commit':data['connections'][a['name']]['main'][0][0]['node']==b['name'] and data['connections'][b['name']]['main'][0][0]['node']==c['name'],
        'ack_forwarded':c['parameters'].get('responseBody')=='={{ $json }}',
        'payload_history_disabled':all(data.get('settings',{}).get(k)=='none' for k in ('saveDataSuccessExecution','saveDataErrorExecution')),
    }


def inspect():
    node=shutil.which('node');version=None
    if node:
        result=subprocess.run([node,'--version'],capture_output=True,text=True,timeout=5,check=True)
        version=result.stdout.strip()
    # Only package metadata in conventional locations; do not execute n8n shims.
    candidates=[Path(os.getenv('APPDATA',''))/'npm/node_modules/n8n/package.json',
                Path(os.getenv('ProgramFiles','C:/Program Files'))/'nodejs/node_modules/n8n/package.json']
    packages=[]
    for candidate in candidates:
        if candidate.is_file():
            package=json.loads(candidate.read_text(encoding='utf-8'))
            packages.append({'version':package.get('version'),'node_engine':package.get('engines',{}).get('node')})
    workflow=ROOT/'n8n/escalation_workflow.json'
    return {'run_id':'preflight-'+uuid.uuid4().hex[:12],'captured_at':datetime.now(timezone.utc).isoformat(),
            'scope':'local_read_only_no_credentials','os':platform.system(),'python':platform.python_version(),
            'node_version':version,'n8n_on_path':shutil.which('n8n') is not None,'n8n_packages':packages,
            'discovery_limit':'PATH and two conventional package locations; absence is not a full disk search',
            'workflow_sha256':hashlib.sha256(workflow.read_bytes()).hexdigest(),
            'workflow_static_checks':workflow_checks(json.loads(workflow.read_text(encoding='utf-8'))),
            'n8n_live':'NOT_EXECUTED','llm_online':'NOT_EXECUTED',
            'authorization':'BLOCKED: separate explicit authorization required',
            'compatibility':'NOT_EXECUTED: Node presence does not prove n8n compatibility'}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path)
    args=parser.parse_args();result=inspect();encoded=json.dumps(result,ensure_ascii=False,indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(encoded,encoding='utf-8')
    print(encoded)
    return 0 if all(result['workflow_static_checks'].values()) else 1


if __name__=='__main__':raise SystemExit(main())
