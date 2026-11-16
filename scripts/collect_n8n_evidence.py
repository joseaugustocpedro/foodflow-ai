"""Read-only projection from an explicitly selected synthetic validation database.

Does not query n8n, use credentials or certify runtime execution from supplied IDs.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import re
import sqlite3
import uuid


def identifier(value):
    if not re.fullmatch(r'[A-Za-z0-9_.:-]{1,100}',value):
        raise ValueError('invalid_identifier')
    return value


def snapshot(database,event_id,execution_id=None,n8n_version=None):
    identifier(event_id)
    if execution_id:identifier(execution_id)
    if n8n_version:identifier(n8n_version)
    path=Path(database).resolve()
    if not path.is_file():raise ValueError('database_missing')
    # URI read-only; never creates or initializes a database.
    con=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)
    con.row_factory=sqlite3.Row
    try:
        row=con.execute('SELECT event_id,ticket_id,state,attempts,retry_cycles,ack,payload FROM outbox WHERE event_id=?',(event_id,)).fetchone()
        if not row:raise ValueError('event_missing')
        payload=json.loads(row['payload'])
        if payload.get('source')!='synthetic-demo':raise ValueError('synthetic_source_required')
        inbox=con.execute('SELECT event_id,ticket_id,record_id,received_at FROM inbox WHERE event_id=?',(event_id,)).fetchone()
        ack=json.loads(row['ack']) if row['ack'] else None
        persisted=bool(inbox and ack and ack.get('received') is True and all(ack.get(k)==inbox[k] for k in ('event_id','ticket_id','record_id','received_at')))
        events=[dict(r) for r in con.execute('SELECT name,outcome,created_at,request_id,operation_id,attempt_id FROM events WHERE ticket_id=? ORDER BY created_at',(row['ticket_id'],))]
        # Never dump actions, tokens, raw payload, environment, headers or lease token.
        return {'run_id':'n8n-snapshot-'+uuid.uuid4().hex[:12],'captured_at':datetime.now(timezone.utc).isoformat(),
                'scope':'synthetic_local_persistence_only','event_id':row['event_id'],'ticket_id':row['ticket_id'],
                'outbox':{k:row[k] for k in ('state','attempts','retry_cycles')},'inbox':dict(inbox) if inbox else None,
                'ack_matches_persisted_inbox':persisted,
                'local_delivery_status':'PASSED' if row['state']=='confirmed' and persisted else 'NOT_EXECUTED' if not row['attempts'] else 'FAILED',
                'operator_supplied_runtime_reference':{'execution_id':execution_id,'version':n8n_version},
                'runtime_reference_verified':False,'n8n_live':'NOT_EXECUTED','events':events}
    finally:con.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',type=Path,required=True);parser.add_argument('--event-id',required=True)
    parser.add_argument('--execution-id');parser.add_argument('--n8n-version');parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:result=snapshot(args.database,args.event_id,args.execution_id,args.n8n_version)
    except (ValueError,sqlite3.Error,KeyError):
        print('Evidence unavailable: check selected synthetic database/event/schema. No raw error exported.');return 1
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Sanitized persistence snapshot written; n8n runtime is not certified by this command.');return 0


if __name__=='__main__':raise SystemExit(main())
