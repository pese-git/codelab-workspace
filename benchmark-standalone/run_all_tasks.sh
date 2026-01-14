#!/bin/bash

# Run all benchmark tasks one by one and collect results
# Usage: ./run_all_tasks.sh

set -e

RESULTS_DIR="task_results"
mkdir -p "$RESULTS_DIR"

echo "🚀 Running all benchmark tasks..."
echo "Results will be saved to $RESULTS_DIR/"
echo ""

# Get all task IDs from tasks.yaml
TASK_IDS=$(grep "^  - id:" tasks.yaml | awk '{print $3}' | head -10)

TOTAL=0
SUCCESS=0
FAILED=0

for task_id in $TASK_IDS; do
    TOTAL=$((TOTAL + 1))
    echo "============================================================"
    echo "📊 Running task $task_id ($TOTAL/10)"
    echo "============================================================"
    
    LOG_FILE="$RESULTS_DIR/${task_id}.log"
    
    # Run task and save log
    if uv run python main.py --task-id="$task_id" 2>&1 | tee "$LOG_FILE"; then
        # Check if task succeeded
        if grep -q "УСПЕШНО завершена" "$LOG_FILE"; then
            SUCCESS=$((SUCCESS + 1))
            echo "✅ Task $task_id: SUCCESS"
        else
            FAILED=$((FAILED + 1))
            echo "❌ Task $task_id: FAILED"
        fi
    else
        FAILED=$((FAILED + 1))
        echo "❌ Task $task_id: ERROR"
    fi
    
    echo ""
    sleep 2
done

echo "============================================================"
echo "📊 Final Results"
echo "============================================================"
echo "Total tasks: $TOTAL"
echo "✅ Successful: $SUCCESS"
echo "❌ Failed: $FAILED"
echo "🎯 Success rate: $(awk "BEGIN {printf \"%.1f\", ($SUCCESS/$TOTAL)*100}")%"
echo ""
echo "Logs saved to $RESULTS_DIR/"
