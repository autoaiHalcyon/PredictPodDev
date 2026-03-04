#!/bin/bash
#
# Checkpoint Scheduler for Soak Test
# Captures checkpoints at specified intervals
#

LOG_FILE="/app/test_reports/checkpoint_scheduler.log"
CHECKPOINTS_DIR="/app/test_reports/checkpoints"

mkdir -p $CHECKPOINTS_DIR

echo "$(date) - Checkpoint scheduler started" >> $LOG_FILE

# Function to capture checkpoint
capture_checkpoint() {
    local label=$1
    echo "$(date) - Capturing checkpoint: $label" >> $LOG_FILE
    cd /app/backend && python tests/enhanced_monitor.py checkpoint "$label" > "$CHECKPOINTS_DIR/${label}.json" 2>&1
    echo "$(date) - Checkpoint $label saved" >> $LOG_FILE
}

# Get soak test start time
START_TIME=$(python3 -c "import json; d=json.load(open('/app/test_reports/soak_test_status.json')); print(d['started_at'])")
echo "$(date) - Soak test started at: $START_TIME" >> $LOG_FILE

# Calculate minutes since start
minutes_since_start() {
    python3 -c "
from datetime import datetime
start = datetime.fromisoformat('$START_TIME'.replace('+00:00', ''))
now = datetime.utcnow()
print(int((now - start).total_seconds() / 60))
"
}

# Main loop - check every minute
while true; do
    ELAPSED=$(minutes_since_start)
    echo "$(date) - Elapsed: ${ELAPSED}min" >> $LOG_FILE
    
    # Capture at specific intervals
    if [ $ELAPSED -ge 30 ] && [ ! -f "$CHECKPOINTS_DIR/soak_30min.json" ]; then
        capture_checkpoint "soak_30min"
    fi
    
    if [ $ELAPSED -ge 60 ] && [ ! -f "$CHECKPOINTS_DIR/soak_60min.json" ]; then
        capture_checkpoint "soak_60min"
    fi
    
    if [ $ELAPSED -ge 90 ] && [ ! -f "$CHECKPOINTS_DIR/soak_90min.json" ]; then
        capture_checkpoint "soak_90min"
    fi
    
    if [ $ELAPSED -ge 120 ]; then
        capture_checkpoint "soak_120min"
        echo "$(date) - All checkpoints captured, exiting" >> $LOG_FILE
        break
    fi
    
    sleep 60
done

echo "$(date) - Checkpoint scheduler completed" >> $LOG_FILE
