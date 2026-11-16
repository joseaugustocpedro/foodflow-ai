"""Start only the offline FoodFlow app, on literal loopback, with a sanitized child environment."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def offline_environment(environment,database):
    result=dict(environment)
    for key in list(result):
        if key.startswith(('OPENAI_','N8N_')) or key in ('FOODFLOW_INBOX_SECRET','FOODFLOW_ALLOW_LIVE_N8N','FOODFLOW_AUTHORIZATION_REF','FOODFLOW_SCENARIO_ID'):
            del result[key]
    result.update(FOODFLOW_ALLOW_ONLINE_LLM='false',FOODFLOW_WORKER='false',
                  FOODFLOW_DB_PATH=str(Path(database).resolve()),FOODFLOW_RUN_ID='interactive')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8000)
    parser.add_argument('--database',type=Path,default=ROOT/'backend/foodflow_v2.sqlite3')
    args=parser.parse_args()
    if not 1024<=args.port<=65535:parser.error('Port must be between 1024 and 65535')
    return subprocess.call([sys.executable,'-m','uvicorn','backend.app.main:app','--host','127.0.0.1',
                            '--port',str(args.port),'--no-access-log'],cwd=ROOT,
                           env=offline_environment(os.environ,args.database))


if __name__=='__main__':raise SystemExit(main())
