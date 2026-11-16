"""Verify synthetic seed integrity; call: python scripts/check_fixtures.py."""
import json
import re
from pathlib import Path
p = Path(__file__).resolve().parents[1] / 'fixtures'
customers = json.loads((p / 'demo_customers.json').read_text(encoding='utf-8'))
orders = json.loads((p / 'orders.json').read_text(encoding='utf-8'))
policies = json.loads((p / 'policies.json').read_text(encoding='utf-8'))
cids = {c['customer_id'] for c in customers}
assert len(cids) == len(customers)
assert len({o['id'] for o in orders}) == len(orders)
assert all(o['customer_id'] in cids for o in orders)
assert policies['metadata']['affiliated_with_ifood'] is False
cases = [json.loads(line) for line in (p / 'eval_cases.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
assert len(cases) >= 25
assert len({x['id'] for x in cases}) == len(cases)
assert len(cases) == 35
for case in cases:
    match = re.search(r'ORD-\d+',case['message'])
    assert case['order_id'] == (match[0] if match else None), case['id']
    assert case['expected_http'] in (200,403,404)
    assert case['dataset_version'] == '2.0'
print(f'OK: {len(customers)} clientes, {len(orders)} pedidos, {len(cases)} casos de avaliação PLANEJADOS (não executados).')
