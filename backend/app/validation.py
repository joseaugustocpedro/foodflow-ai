"""Offline provider and explicitly authorized online pilot budget controls."""
import json
import asyncio
import math
import re
from dataclasses import dataclass
from .agent import Provider


class OfflineProvider:
    async def respond(self,items,tools):
        message=items[0]['content']
        calls=[x for x in items if x.get('type')=='function_call']
        def call(name,args):
            return {'id':'fake-response','model':'offline-scripted-v1','status':'completed','output':[
                {'type':'function_call','name':name,'arguments':json.dumps(args),'call_id':'fake-'+str(len(calls))}]}
        oid=re.search(r'ORD-\d+',message,re.I)
        if not calls and oid:
            return call('lookup_order',{'order_id':oid[0].upper()})
        results=[json.loads(x['output']) for x in items if x.get('type')=='function_call_output']
        if results and oid:
            order=results[0];text=message.lower()
            reason=('refund' if 'reembolso' in text else 'cancel' if 'cancel' in text else
                    'wrong_item' if any(t in text for t in ('errado','incorreto','faltante')) else
                    'late_delivery' if order.get('is_delayed') else 'assistance')
            names=[x['name'] for x in calls]
            if reason!='assistance' and 'get_policy' not in names:
                return call('get_policy',{'topic':reason})
            if (reason!='assistance' or any(t in text for t in ('ticket','chamado','humano','problema','ajuda'))) and 'create_ticket' not in names:
                return call('create_ticket',{'order_id':oid[0].upper(),'reason':reason})
        return {'id':'fake-response','model':'offline-scripted-v1','status':'completed',
                'output':[{'type':'message','content':[{'type':'output_text','text':'Resultado disponível nos fatos.'}]}]}


@dataclass
class BudgetProvider:
    max_requests: int
    budget: float
    input_price: float
    output_price: float
    max_input_bytes: int = 24000
    calls: int = 0
    spent: float = 0
    stopped: str | None = None

    def __post_init__(self):
        if self.max_requests<1 or self.max_requests>140 or any(not math.isfinite(x) or x<=0 for x in (self.budget,self.input_price,self.output_price)):
            raise ValueError('Limites/preços explícitos válidos são obrigatórios')

    async def respond(self,items,tools):
        if self.stopped:
            raise ValueError('pilot_stopped')
        # Reserve using UTF-8 byte count as conservative token bound for the fixed request.
        from .agent import SYSTEM
        size=len(json.dumps({'input':items,'tools':tools,'instructions':SYSTEM},ensure_ascii=False).encode())+1024
        reserve=(size*self.input_price+600*self.output_price)/1_000_000
        if self.calls>=self.max_requests or size>self.max_input_bytes or self.spent+reserve>self.budget:
            self.stopped='budget_or_request_limit'
            raise ValueError(self.stopped)
        self.calls+=1
        self.spent+=reserve
        try:
            response=await Provider().respond(items,tools)
            usage=response.get('usage',{})
            if any(type(usage.get(k)) is not int or usage[k]<0 for k in ('input_tokens','output_tokens')):
                self.stopped='usage_unavailable'
                raise ValueError(self.stopped)
            actual=(usage['input_tokens']*self.input_price+usage['output_tokens']*self.output_price)/1_000_000
            self.spent+=actual-reserve
            if actual>reserve:
                self.stopped='reservation_exceeded'
            return response
        except asyncio.CancelledError:
            # wait_for cancels the coroutine; billing may already have occurred.
            self.stopped='provider_cancelled_cost_uncertain'
            raise
        except Exception:
            self.stopped=self.stopped or 'provider_error_cost_uncertain'
            raise
