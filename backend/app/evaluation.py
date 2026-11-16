"""Shared scoring summaries and comparison, never treat fake runs as online."""
import json
from pathlib import Path
from .metrics import ratio


def summarize(results):
    counts={s:sum(r['status']==s for r in results) for s in ('passed','failed','skipped')}
    return {'planned':len(results),**counts,'pass_rate':ratio(counts['passed'],counts['passed']+counts['failed']),
            'execution_status':'Não executado' if counts['passed']+counts['failed']==0 else 'Executado'}


def compare(left,right,lrows,rrows):
    keys=('hashes','code_sha256','prompt_sha256','schemas_sha256','runner_sha256','scoring_sha256','scenario_now')
    if left.get('mode')!='demo' or right.get('mode')!='online':
        return {'status':'Não comparável','reason':'Somente demo versus online real','delta':None,'paired':0}
    if any(not left.get(k) or left.get(k)!=right.get(k) for k in keys):
        return {'status':'Não comparável','reason':'Versões ou critérios diferentes','delta':None,'paired':0}
    lmap={r['case_id']:r for r in lrows};rmap={r['case_id']:r for r in rrows}
    pairs=[];excluded=[]
    for cid in sorted(set(lmap)|set(rmap)):
        a,b=lmap.get(cid),rmap.get(cid)
        if not a or not b or 'skipped' in (a['status'],b['status']):
            excluded.append({'case_id':cid,'reason':'não executado em ambos'})
        elif not b.get('provider_executed'):
            excluded.append({'case_id':cid,'reason':'sem execução do provedor'})
        else:
            pairs.append((a,b))
    if not pairs:
        return {'status':'Não executado','reason':'Sem casos pareados executados','delta':None,'paired':0,'excluded':excluded}
    a=sum(x['status']=='passed' for x,_ in pairs)
    b=sum(y['status']=='passed' and y.get('effective_mode')=='llm' for _,y in pairs)
    return {'status':'Comparável','reason':'Casos e versões pareados; fallback não é sucesso LLM',
            'paired':len(pairs),'baseline':ratio(a,len(pairs)),'online':ratio(b,len(pairs)),
            'delta':(b-a)/len(pairs),'excluded':excluded}


def catalog(root):
    entries=[]
    for p in sorted(Path(root).glob('*/summary.json')):
        try:
            summary=json.loads(p.read_text(encoding='utf-8'))
            manifest=json.loads((p.parent/'manifest.json').read_text(encoding='utf-8'))
            rows=[json.loads(x) for x in (p.parent/'results.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
            entries.append((summary,manifest,rows))
        except (ValueError,OSError):
            continue
    comparisons=[]
    for _,rm,rr in entries:
        if rm.get('mode')=='online':
            candidates=[(lm,lr) for _,lm,lr in entries if lm.get('mode')=='demo']
            for lm,lr in candidates:
                comparisons.append({'baseline_run':lm['run_id'],'online_run':rm['run_id'],**compare(lm,rm,lr,rr)})
    return {'runs':[s for s,_,_ in entries],'comparisons':comparisons,
            'comparison':comparisons[-1]['status'] if comparisons else 'Não executado',
            'delta':comparisons[-1]['delta'] if comparisons else None}
