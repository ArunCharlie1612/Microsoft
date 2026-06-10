#!/usr/bin/env bash
# Seed the demo: provision the misconfigured sandbox and kick off a swarm run.
# Usage: ./scripts/seed_demo.sh [API_BASE]
set -euo pipefail

API_BASE="${1:-http://localhost:8000}"

echo "→ Provisioning misconfigured sandbox…"
curl -s -X POST "$API_BASE/v1/demo/seed" | jq .

echo "→ Deploying agent swarm…"
RUN=$(curl -s -X POST "$API_BASE/v1/runs" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Live Demo — misconfigured blob",
    "scope": {
      "subscriptionId": "00000000-0000-0000-0000-000000000000",
      "resourceGroups": ["rg-breachsim-sandbox"],
      "sandboxOnly": true
    }
  }')
echo "$RUN" | jq .
RUN_ID=$(echo "$RUN" | jq -r .runId)

echo "→ Streaming live agent feed (Ctrl-C to stop)…"
curl -N "$API_BASE/v1/runs/$RUN_ID/events"
