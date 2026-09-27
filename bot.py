from __future__ import annotations
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel, Field

from context_store import ContextStore
from composer import compose as _compose_fn
from conversation_handlers import conversation_manager

app = FastAPI(title="Vera Assistant", version="1.0.0")

START_TIME = time.time()
BASE_DIR = Path(__file__).resolve().parent
DATASET_DIR = BASE_DIR / "dataset"
store = ContextStore(dataset_dir=DATASET_DIR if DATASET_DIR.exists() else None)


def compose(
    category: Dict[str, Any],
    merchant: Dict[str, Any],
    trigger: Dict[str, Any],
    customer: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return _compose_fn(category, merchant, trigger, customer)


class ContextPushBody(BaseModel):
    scope: str
    context_id: str
    version: int
    payload: Dict[str, Any]
    delivered_at: Optional[str] = None


class TickBody(BaseModel):
    now: Optional[str] = None
    available_triggers: List[str] = Field(default_factory=list)


class ReplyBody(BaseModel):
    conversation_id: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    from_role: str = "merchant"
    message: str
    received_at: Optional[str] = None
    turn_number: int = 1


@app.get("/v1/healthz")
async def healthz():
    uptime = int(time.time() - START_TIME)
    counts = store.get_counts()
    return {
        "status": "ok",
        "uptime_seconds": uptime,
        "contexts_loaded": counts,
    }


@app.get("/v1/metadata")
async def metadata():
    return {
        "team_name": "Team Antigravity",
        "team_members": ["Lead Engineer"],
        "model": "hybrid-domain-specialist-llm",
        "approach": "4-Context Framework Composer with Domain Specialists & Multi-Turn State Machine",
        "contact_email": "vera-lead@magicpin.ai",
        "version": "1.0.0",
        "submitted_at": "2026-04-26T10:00:00Z",
    }


@app.post("/v1/context")
async def push_context(body: ContextPushBody, response: Response):
    accepted, status_code, details = store.push(
        scope=body.scope,
        context_id=body.context_id,
        version=body.version,
        payload=body.payload,
    )
    response.status_code = status_code
    return details


@app.post("/v1/tick")
async def tick(body: TickBody):
    actions = []
    
    for trg_id in body.available_triggers:
        trg = store.get("trigger", trg_id)
        if not trg:
            continue

        merchant_id = trg.get("merchant_id") or trg.get("payload", {}).get("merchant_id")
        customer_id = trg.get("customer_id") or trg.get("payload", {}).get("customer_id")
        
        merchant = store.get("merchant", merchant_id) if merchant_id else None
        customer = store.get("customer", customer_id) if customer_id else None

        if not merchant:
            continue

        cat_slug = merchant.get("category_slug")
        category = store.get("category", cat_slug) or {"slug": cat_slug}

        comp = compose(category, merchant, trg, customer)
        conv_id = f"conv_{merchant_id}_{trg_id}"

        action = {
            "conversation_id": conv_id,
            "merchant_id": merchant_id,
            "customer_id": customer_id,
            "send_as": comp.get("send_as", "vera"),
            "trigger_id": trg_id,
            "template_name": f"vera_{category.get('slug', 'default')}_v1",
            "template_params": [
                merchant.get("identity", {}).get("name", "Partner"),
                trg.get("kind", "update"),
            ],
            "body": comp.get("body", ""),
            "cta": comp.get("cta", "binary"),
            "suppression_key": comp.get("suppression_key", trg.get("suppression_key", "")),
            "rationale": comp.get("rationale", "Composed from 4-context framework"),
        }
        actions.append(action)

    return {"actions": actions}


@app.post("/v1/reply")
async def reply(body: ReplyBody):
    merchant = store.get("merchant", body.merchant_id) if body.merchant_id else None
    
    response_action = conversation_manager.handle_reply(
        conversation_id=body.conversation_id,
        merchant_id=body.merchant_id,
        customer_id=body.customer_id,
        from_role=body.from_role,
        message=body.message,
        turn_number=body.turn_number,
        merchant_context=merchant,
    )
    return response_action


@app.post("/v1/teardown")
async def teardown():
    store.clear()
    return {"status": "ok", "cleared": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("bot:app", host="0.0.0.0", port=8080, reload=False)
