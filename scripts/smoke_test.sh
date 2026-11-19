#!/usr/bin/env bash
set -euo pipefail
BASE_URL="${1:-http://localhost:8000}"
echo "Health check..."
curl -fsS "$BASE_URL/health" | python -m json.tool
echo "Creating synthetic payment..."
RESPONSE=$(curl -fsS -X POST "$BASE_URL/payments" -H 'Content-Type: application/json' -d '{"amount":125.75,"currency":"USD","destination":"IN"}')
echo "$RESPONSE" | python -m json.tool
TXN=$(python -c 'import json,sys; print(json.load(sys.stdin)["transaction_id"])' <<< "$RESPONSE")
echo "Retrieving $TXN ..."
curl -fsS "$BASE_URL/payments/$TXN" | python -m json.tool
