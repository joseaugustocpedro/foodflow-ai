"""One authorized delivery attempt in an explicitly selected one-event synthetic DB.

No install, account login, n8n launch or retry loop. Future live use only.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.app import automation


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-live',action='store_true');parser.add_argument('--authorization-ref')
    parser.add_argument('--database',type=Path,required=True)
    args=parser.parse_args(argv)
    if not args.confirm_live or os.getenv('FOODFLOW_ALLOW_LIVE_N8N')!='true' or not args.authorization_ref or args.authorization_ref!=os.getenv('FOODFLOW_AUTHORIZATION_REF'):
        print('BLOCKED: explicit live authorization flag and reference required.');return 2
    if not args.database.is_file():
        print('BLOCKED: dedicated existing database required.');return 2
    con=sqlite3.connect(args.database.resolve().as_uri()+'?mode=ro',uri=True)
    try:
        rows=con.execute('SELECT payload FROM outbox').fetchall()
        if len(rows)!=1 or json.loads(rows[0][0]).get('source')!='synthetic-demo':
            print('BLOCKED: exactly one synthetic outbox required.');return 2
    finally:con.close()
    if not automation.preflight()['ready']:
        print('BLOCKED: preflight configuration invalid or absent.');return 2
    prior=os.environ.get('FOODFLOW_DB_PATH')
    try:
        os.environ['FOODFLOW_DB_PATH']=str(args.database.resolve())
        attempted=asyncio.run(automation.deliver_once())
        print('One local delivery cycle evaluated.' if attempted else 'No due event or lease still held.')
        return 0
    finally:
        if prior is None:os.environ.pop('FOODFLOW_DB_PATH',None)
        else:os.environ['FOODFLOW_DB_PATH']=prior


if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,sqlite3.Error):
        print('Local validation failed; no raw database or configuration details printed.');raise SystemExit(1)
