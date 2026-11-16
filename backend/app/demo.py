"""Trusted seed and strict demo-context checks."""
from __future__ import annotations

import json
from pathlib import Path
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[2]


def _read(name: str):
    return json.loads((ROOT / "fixtures" / name).read_text(encoding="utf-8"))


def customers():
    return _read("demo_customers.json")


def orders():
    return _read("orders.json")


def verify_customer(customer_id: str, demo_token: str) -> None:
    # Explicitly demonstrative; never substitute this for production authentication.
    match = next((c for c in customers() if c["customer_id"] == customer_id), None)
    if not match or demo_token != match["demo_token"]:
        raise HTTPException(status_code=403, detail="Cliente demo não autorizado")


def authorized_order(order_id: str, customer_id: str, demo_token: str) -> dict:
    verify_customer(customer_id, demo_token)
    order = next((o for o in orders() if o["id"] == order_id), None)
    if order is None:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    if order["customer_id"] != customer_id:
        raise HTTPException(status_code=403, detail="Acesso negado a este pedido")
    return order


def policies():
    return _read("policies.json")
