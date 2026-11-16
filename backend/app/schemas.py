from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, strict=True)


class Identity(Strict):
    customer_id: str = Field(pattern=r'^CUST-00[123]$')
    demo_token: str = Field(min_length=4, max_length=80)


class ChatRequest(Identity):
    session_id: str = Field(min_length=1, max_length=96)
    message: str = Field(min_length=1, max_length=1500)
    requested_mode: Literal['demo', 'llm'] = 'demo'


class Confirmation(Identity):
    session_id: str = Field(min_length=1, max_length=96)
    action_token: str = Field(min_length=16, max_length=128)
    idempotency_key: str = Field(min_length=8, max_length=96)


class TicketRequest(Confirmation):
    action_id: str


class LookupArgs(Strict):
    order_id: str = Field(pattern=r'^ORD-\d{4,8}$')


class PolicyArgs(Strict):
    topic: Literal['late_delivery', 'cancel', 'wrong_item', 'refund', 'privacy']


class ProposeArgs(LookupArgs):
    reason: Literal['late_delivery', 'cancel', 'wrong_item', 'refund', 'assistance']


class HandoffPayload(Strict):
    schema_version: Literal['1']
    event_id: str = Field(min_length=10, max_length=64)
    ticket_id: str = Field(pattern=r'^TCK-[A-F0-9]{16}$')
    order_id: str = Field(pattern=r'^ORD-\d{4,8}$')
    reason_code: Literal['late_delivery', 'cancel', 'wrong_item', 'refund', 'assistance']
    created_at: str = Field(min_length=10, max_length=40)
    source: Literal['synthetic-demo']


class Ack(Strict):
    received: Literal[True]
    event_id: str
    ticket_id: str
    record_id: str = Field(min_length=1, max_length=64)
    received_at: str = Field(min_length=10, max_length=40)
