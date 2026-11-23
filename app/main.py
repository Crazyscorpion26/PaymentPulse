import asyncio
from contextlib import asynccontextmanager
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import asyncpg
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST

SERVICE = "paymentpulse-api"
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(message)s")
logger = logging.getLogger(SERVICE)

REQUESTS = Counter("paymentpulse_http_requests_total", "HTTP requests", ["method", "endpoint", "status"])
PAYMENTS = Counter("paymentpulse_transactions_total", "Payment transactions", ["status"])
DURATION = Histogram("paymentpulse_request_duration_seconds", "Request duration", ["endpoint"],
                     buckets=(.01, .025, .05, .1, .25, .5, 1, 2.5, 5))
IN_FLIGHT = Gauge("paymentpulse_in_flight_requests", "Requests currently being processed")

# ── Database / Storage ─────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

_pool: Optional[asyncpg.Pool] = None
_transactions: dict[str, dict] = {}  # in-memory fallback (CI / local dev)

async def init_db(pool: asyncpg.Pool):
    await pool.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id TEXT PRIMARY KEY,
            amount       DOUBLE PRECISION NOT NULL,
            currency     TEXT NOT NULL,
            destination  TEXT NOT NULL,
            status       TEXT NOT NULL,
            events       JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    logger.info("Database table 'transactions' is ready")

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pool
    # Startup
    if DATABASE_URL:
        _pool = await asyncpg.create_pool(dsn=DATABASE_URL, min_size=1, max_size=10)
        await init_db(_pool)
        logger.info("Connected to PostgreSQL")
    else:
        logger.warning("DATABASE_URL not set – using in-memory storage")
    yield
    # Shutdown
    if _pool:
        await _pool.close()

app = FastAPI(
    title="PaymentPulse API",
    version="1.0.0",
    description="Synthetic payment lifecycle service for SRE portfolio practice",
    lifespan=lifespan,
)

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
async def ready():
    if _pool:
        try:
            async with _pool.acquire() as conn:
                count = await conn.fetchval("SELECT count(*) FROM transactions")
            return {"status": "ready", "db": "connected", "transactions": count}
        except Exception as e:
            return {"status": "degraded", "error": str(e)}
    return {"status": "ready", "db": "in_memory", "transactions": len(_transactions)}

def _make_record(transaction_id: str, payload: PaymentRequest, status: str, scenario: Optional[str]) -> dict:
    now_iso = datetime.now(timezone.utc).isoformat()
    events = [
        {"code": "R1", "status": "RECEIVED", "at": now_iso},
        {"code": "R2", "status": "VALIDATED", "at": now_iso},
        {"code": "CUSTOM", "status": status, "at": now_iso},
    ]
    if scenario == "callback_failure":
        events.append({"code": "REMIT_CALLBACK", "status": "FAILED", "at": now_iso})
        emit("remittance_callback_failed", transaction_id=transaction_id, severity="error")
    else:
        events.append({"code": "REMIT_CALLBACK", "status": "ACKNOWLEDGED", "at": now_iso})
    return {
        "transaction_id": transaction_id,
        "amount": payload.amount,
        "currency": payload.currency.upper(),
        "destination": payload.destination.upper(),
        "status": status,
        "events": events,
    }

@app.post("/payments", status_code=201)
async def create_payment(payload: PaymentRequest):
    transaction_id = f"PP-{uuid.uuid4().hex[:12].upper()}"
    scenario = payload.simulate
    if scenario == "slow":
        await asyncio.sleep(1.5)
    status = "DECLINED" if scenario == "decline" else "PROCESSING"
    record = _make_record(transaction_id, payload, status, scenario)

    if _pool:
        async with _pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO transactions (transaction_id, amount, currency, destination, status, events)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                transaction_id, payload.amount, payload.currency.upper(), payload.destination.upper(), status,
                json.dumps(record["events"])
            )
    else:
        _transactions[transaction_id] = record

    PAYMENTS.labels(status).inc()
    emit("payment_created", transaction_id=transaction_id, status=status, amount=payload.amount,
         currency=payload.currency.upper(), scenario=scenario or "normal")
    return record

@app.get("/payments/{transaction_id}")
async def get_payment(transaction_id: str):
    record = None
    if _pool:
        async with _pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM transactions WHERE transaction_id = $1", transaction_id)
            if row:
                record = dict(row)
                record["events"] = json.loads(record["events"]) if isinstance(record["events"], str) else record["events"]
    else:
        record = _transactions.get(transaction_id)

    if not record:
        emit("payment_not_found", transaction_id=transaction_id, severity="warning")
        raise HTTPException(status_code=404, detail="Transaction not found")
    emit("payment_lookup", transaction_id=transaction_id, status=record["status"])
    return record

@app.get("/payments")
async def search_payments(status: Optional[str] = None, limit: int = Query(default=50, ge=1, le=200)):
    if _pool:
        async with _pool.acquire() as conn:
            if status:
                rows = await conn.fetch("SELECT * FROM transactions WHERE status = $1 LIMIT $2", status.upper(), limit)
            else:
                rows = await conn.fetch("SELECT * FROM transactions LIMIT $1", limit)
        items = []
        for row in rows:
            d = dict(row)
            d["events"] = json.loads(d["events"]) if isinstance(d["events"], str) else d["events"]
            items.append(d)
        return {"count": len(items), "items": items}

    results = list(_transactions.values())
    if status:
        results = [r for r in results if r["status"] == status.upper()]
    return {"count": len(results[:limit]), "items": results[:limit]}

@app.post("/simulate/outage")
async def simulate_outage(seconds: int = Query(default=2, ge=1, le=10)):
    emit("simulated_dependency_outage", severity="warning", duration_seconds=seconds)
    await asyncio.sleep(seconds)
    return {"message": "Synthetic dependency delay completed", "duration_seconds": seconds}

@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    return PlainTextResponse(generate_latest().decode("utf-8"), media_type=CONTENT_TYPE_LATEST)
