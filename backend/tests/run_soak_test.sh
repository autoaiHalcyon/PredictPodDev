#!/bin/bash
#
# Sandbox Release Gate Soak Test Runner
# Runs the 2-hour soak test in background with periodic status updates
#
# Usage: ./run_soak_test.sh [duration_minutes]
#

set -e

DURATION=${1:-120}  # Default 2 hours
LOG_FILE="/app/test_reports/soak_test_output.log"
PID_FILE="/app/test_reports/soak_test.pid"
STATUS_FILE="/app/test_reports/soak_test_status.json"

echo "Starting Sandbox Release Gate Soak Test"
echo "Duration: ${DURATION} minutes"
echo "Log file: ${LOG_FILE}"
echo "Status file: ${STATUS_FILE}"

# Ensure test reports directory exists
mkdir -p /app/test_reports

# Initialize status file
cat > ${STATUS_FILE} << EOF
{
  "status": "starting",
  "duration_minutes": ${DURATION},
  "started_at": "$(date -Iseconds)",
  "log_file": "${LOG_FILE}"
}
EOF

# Run the test in background
cd /app/backend
nohup python -u tests/sandbox_release_gate.py --soak-duration ${DURATION} > ${LOG_FILE} 2>&1 &
TEST_PID=$!

echo $TEST_PID > ${PID_FILE}
echo "Test started with PID: ${TEST_PID}"

# Update status
cat > ${STATUS_FILE} << EOF
{
  "status": "running",
  "pid": ${TEST_PID},
  "duration_minutes": ${DURATION},
  "started_at": "$(date -Iseconds)",
  "log_file": "${LOG_FILE}",
  "report_file": "/app/test_reports/sandbox_release_gate_report.json"
}
EOF

echo "Soak test running in background. Monitor with:"
echo "  tail -f ${LOG_FILE}"
echo "  cat ${STATUS_FILE}"
echo ""
echo "Check completion with:"
echo "  ps -p ${TEST_PID} || echo 'Test completed'"
echo "  cat /app/test_reports/sandbox_release_gate_report.json"
