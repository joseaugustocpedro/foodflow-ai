"""Generate inactive local fault-test workflows, without starting/importing n8n."""
import argparse
import copy
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def variants(data):
    result={}
    for name,code,body in (('N05_ack_lost',504,'={{ {"test_fault":"ack_lost_after_commit"} }}'),
                           ('N07_invalid_ack',200,'={{ {} }}')):
        item=copy.deepcopy(data)
        item['name']='FoodFlow isolated validation '+name;item['active']=False
        ack=next(n for n in item['nodes'] if n['id']=='ack')
        ack['parameters']['responseBody']=body
        ack['parameters']['options']['responseCode']=code
        result[name]=item
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    data=json.loads((ROOT/'n8n/escalation_workflow.json').read_text(encoding='utf-8'))
    for name,item in variants(data).items():
        (args.output/(name+'.json')).write_text(json.dumps(item,indent=2),encoding='utf-8')
    print('Two inactive variants prepared. Import compatibility and runtime behavior NOT_EXECUTED.')


if __name__=='__main__':main()
