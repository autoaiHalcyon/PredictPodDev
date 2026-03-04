#!/bin/bash
#
# Soak Test Status Monitor
# Run this script periodically to check test progress
#

API_URL=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2)
STATUS_FILE="/app/test_reports/soak_test_status.json"
LOG_FILE="/app/test_reports/soak_test_output.log"
PID_FILE="/app/test_reports/soak_test.pid"

echo "============================================"
echo "SANDBOX RELEASE GATE - STATUS MONITOR"
echo "$(date)"
echo "============================================"

# Check if test is running
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p $PID > /dev/null 2>&1; then
        echo "STATUS: RUNNING (PID: $PID)"
    else
        echo "STATUS: COMPLETED"
    fi
else
    echo "STATUS: NOT STARTED"
fi

echo ""
echo "=== Test Configuration ==="
if [ -f "$STATUS_FILE" ]; then
    python3 -c "
import json
with open('$STATUS_FILE') as f:
    d = json.load(f)
    print(f'Duration: {d.get(\"duration_minutes\", \"?\")} minutes')
    print(f'Started: {d.get(\"started_at\", \"?\")}')
"
fi

echo ""
echo "=== System Health ==="
curl -s "$API_URL/api/health" 2>/dev/null | python3 -c "
import sys,json
try:
    d = json.load(sys.stdin)
    print(f'  Backend: {d[\"status\"]}')
    print(f'  Database: {d[\"components\"][\"database\"][\"status\"]}')
    print(f'  Uptime: {d[\"uptime_seconds\"]}s')
    print(f'  Kill Switch: {d[\"components\"].get(\"kalshi_integration\",{}).get(\"kill_switch_active\", \"N/A\")}')
except: print('  Error fetching health')
"

echo ""
echo "=== Trading Status ==="
curl -s "$API_URL/api/sandbox/status" 2>/dev/null | python3 -c "
import sys,json
try:
    d = json.load(sys.stdin)
    print(f'  Mode: {d[\"mode\"]}')
    print(f'  Balance: \${d[\"balance\"]:.2f}')
    print(f'  Working Orders: {d[\"working_orders_count\"]}')
except: print('  Error fetching sandbox status')
"

echo ""
echo "=== Reconciliation ==="
curl -s "$API_URL/api/reconciliation/status" 2>/dev/null | python3 -c "
import sys,json
try:
    d = json.load(sys.stdin)
    print(f'  Unreconciled: {d[\"total_unreconciled\"]}')
    print(f'  Critical: {d[\"critical_mismatches\"]}')
    print(f'  Warnings: {d[\"warning_mismatches\"]}')
except: print('  Error fetching reconciliation')
"

echo ""
echo "=== Order Count ==="
curl -s "$API_URL/api/orders?limit=1000" 2>/dev/null | python3 -c "
import sys,json
try:
    d = json.load(sys.stdin)
    print(f'  Total Orders: {d[\"total\"]}')
except: print('  Error fetching orders')
"

echo ""
echo "=== Recent Log Entries ==="
if [ -f "$LOG_FILE" ]; then
    tail -5 "$LOG_FILE"
else
    echo "No log file found"
fi

echo ""
echo "============================================"
