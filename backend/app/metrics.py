"""Immutable start cohorts observed as_of. Until limits admission, not completion."""
import math
from datetime import datetime,timezone
from . import db


def ratio(n,d):
    return {'numerator':n,'denominator':d,'value':n/d if d else None}


def aggregate(source,run_id='interactive',mode=None,since=None,until=None,as_of=None):
    as_of = as_of or datetime.now(timezone.utc)
    stamp = lambda t:datetime.fromisoformat(t).timestamp()
    lower = since.timestamp() if since else float('-inf')
    upper = until.timestamp() if until else float('inf')
    rows = [r for r in source if r['run_id']==run_id and stamp(r['created_at'])<=as_of.timestamp()]
    ends = {r['request_id']:r for r in rows if r['name']=='chat_completed'}
    def match(r):
        effective = ends.get(r['request_id'],r).get('effective_mode')
        return mode is None or effective==mode
    def cohort(r):
        return lower<=stamp(r['created_at'])<=upper and match(r)
    received = {r['request_id']:r for r in rows if r['name']=='chat_received' and cohort(r)}
    terminal = [ends[k] for k in received if k in ends]
    confirmed = {r['request_id'] for r in rows if r['name']=='ticket_confirmed'}
    outcomes = {key:0 for key in ('answered','escalated','denied','failed')}
    for r in terminal:
        outcome = 'escalated' if r['request_id'] in confirmed else r['outcome']
        outcomes[outcome]+=1
    durations = sorted(r['duration_ms'] for r in terminal if r['duration_ms'] is not None)
    # New events have tool_call_id. Legacy records without IDs cannot be safely paired.
    started = {r['tool_call_id']:r for r in rows if r['name']=='tool_started' and r.get('tool_call_id') and cohort(r)}
    completed = {r['tool_call_id']:r for r in rows if r['name']=='tool_completed' and r.get('tool_call_id')}
    tools = [completed[k] for k in started if k in completed]
    operations = {r['ticket_id']:r['operation_id'] for r in rows if r.get('operation_id') and r.get('ticket_id')}
    operation = lambda r:r.get('operation_id') or operations.get(r['ticket_id'],r['ticket_id'])
    queued = {operation(r) for r in rows if r['name']=='handoff_queued' and cohort(r)}
    acked = {operation(r) for r in rows if r['name']=='handoff_acknowledged'} & queued
    blocks = {key:sum(r['name']=='safety_blocked' and r['outcome']==key and cohort(r) for r in rows)
              for key in ('direct_order','ownership','identity_or_session')}
    count = len(received)
    return {'data_origin':'synthetic','run_id':run_id,'mode':mode,'updated_at':db.now(),
            'period':{'since':since,'until':until},'as_of':as_of,'semantics':'start_cohort_observed_as_of',
            'total_interactions':count,'responses':outcomes['answered'],'outcomes':outcomes,
            'pending_requests':count-len(terminal),'tickets':len(queued),
            'blocked_requests':blocks['ownership']+blocks['identity_or_session'],
            'blocked_by_channel':blocks,'blocked_total':sum(blocks.values()),
            'rejected_requests':sum(r['name']=='chat_rejected' and cohort(r) for r in rows),
            'answered_rate':ratio(outcomes['answered'],count),'escalation_rate':ratio(outcomes['escalated'],count),
            'automation_delivery':ratio(len(acked),len(queued)),
            'tool_success':ratio(sum(r['outcome']=='success' for r in tools),len(tools)),
            'tool_denied':sum(r['outcome']=='denied' for r in tools),'tool_pending':len(started)-len(tools),
            'legacy_unpaired_tools':sum(r['name'] in ('tool_started','tool_completed') and not r.get('tool_call_id') and cohort(r) for r in rows),
            'orphan_tool_terminals':sum(k not in {r.get('tool_call_id') for r in rows if r['name']=='tool_started'} for k in completed),
            'orphan_terminals':sum(r['request_id'] not in {e['request_id'] for e in rows if e['name']=='chat_received'} for r in ends.values()),
            'sample_size':len(durations),'avg_response_ms':sum(durations)/len(durations) if durations else None,
            'p95_response_ms':durations[math.ceil(.95*len(durations))-1] if durations else None,
            'not_measured':['customer_satisfaction','hours_saved','financial_roi','llm_accuracy']}
