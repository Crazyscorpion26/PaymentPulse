import json
import logging
import os
import random
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST

SERVICE = "paymentpulse-api"
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(message)s")
logger = logging.getLogger(SERVICE)

REQUESTS = Counter("paymentpulse_http_requests_total", "HTTP requests", ["method", "endpoint", "status"])
PAYMENTS = Counter("paymentpulse_transactions_total", "Payment transactions", ["status"])
DURATION = Histogram("paymentpulse_request_duration_seconds", "Request duration", ["endpoint"], buckets=(.01,.025,.05,.1,.25,.5,1,2.5,5))
IN_FLIGHT = Gauge("paymentpulse_in_flight_requests", "Requests currently being processed")

app = FastAPI(title="PaymentPulse API", version="1.0.0", description="Synthetic payment lifecycle service for SRE portfolio practice")
transactions: dict[str, dict] = {}

class PaymentRequest(BaseModel):
    amount: float = Field(gt=0, le=1000000)
    currency: str = Field(default="USD", min_length=3, max_length=3, pattern="^[A-Za-z]{3}$")
    destination: str = Field(default="GB", min_length=2, max_length=2, pattern="^[A-Za-z]{2}$")
    simulate: Optional[str] = Field(default=None, description="Optional scenario: decline, slow, callback_failure")


def emit(event: str, **fields):
    logger.info(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(), "service": SERVICE, "event": event, **fields}))

@app.middleware("http")
async def observe_requests(request, call_next):
    started = time.perf_counter()
    IN_FLIGHT.inc()
    status = "500"
    try:
        response = await call_next(request)
        status = str(response.status_code)
        return response
    finally:
        elapsed = time.perf_counter() - started
        route = request.scope.get("route")
        endpoint = getattr(route, "path", request.url.path)
        DURATION.labels(endpoint).observe(elapsed)
        REQUESTS.labels(request.method, endpoint, status).inc()
        IN_FLIGHT.dec()

@app.get("/health")
def health():
    return {"status": "healthy", "service": SERVICE, "timestamp": datetime.now(timezone.utc).isoformat()}

@app.get("/ready")
def ready():
    return {"status": "ready", "in_memory_transactions": len(transactions)}

@app.post("/payments", status_code=201)
def create_payment(payload: PaymentRequest):
    transaction_id = f"PP-{uuid.uuid4().hex[:12].upper()}"
    scenario = payload.simulate
    if scenario == "slow":
        time.sleep(1.5)
    status = "DECLINED" if scenario == "decline" else "PROCESSING"
    record = {
        "transaction_id": transaction_id,
        "amount": payload.amount,
        "currency": payload.currency.upper(),
        "destination": payload.destination.upper(),
        "status": status,
        "events": [
            {"code": "R1", "status": "RECEIVED", "at": datetime.now(timezone.utc).isoformat()},
            {"code": "R2", "status": "VALIDATED", "at": datetime.now(timezone.utc).isoformat()},
            {"code": "CUSTOM", "status": status, "at": datetime.now(timezone.utc).isoformat()},
        ],
    }
    if scenario == "callback_failure":
        record["events"].append({"code": "REMIT_CALLBACK", "status": "FAILED", "at": datetime.now(timezone.utc).isoformat()})
        emit("remittance_callback_failed", transaction_id=transaction_id, severity="error")
    else:
        record["events"].append({"code": "REMIT_CALLBACK", "status": "ACKNOWLEDGED", "at": datetime.now(timezone.utc).isoformat()})
    transactions[transaction_id] = record
    PAYMENTS.labels(status).inc()
    emit("payment_created", transaction_id=transaction_id, status=status, amount=payload.amount, currency=payload.currency.upper(), scenario=scenario or "normal")
    return record

@app.get("/payments/{transaction_id}")
def get_payment(transaction_id: str):
    record = transactions.get(transaction_id)
    if not record:
        emit("payment_not_found", transaction_id=transaction_id, severity="warning")
        raise HTTPException(status_code=404, detail="Transaction not found")
    emit("payment_lookup", transaction_id=transaction_id, status=record["status"])
    return record

@app.get("/payments")
def search_payments(status: Optional[str] = None, limit: int = Query(default=50, ge=1, le=200)):
    results = list(transactions.values())
    if status:
        results = [r for r in results if r["status"] == status.upper()]
    return {"count": len(results[:limit]), "items": results[:limit]}

@app.post("/simulate/outage")
def simulate_outage(seconds: int = Query(default=2, ge=1, le=10)):
    emit("simulated_dependency_outage", severity="warning", duration_seconds=seconds)
    time.sleep(seconds)
    return {"message": "Synthetic dependency delay completed", "duration_seconds": seconds}

@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    return PlainTextResponse(generate_latest().decode("utf-8"), media_type=CONTENT_TYPE_LATEST)
