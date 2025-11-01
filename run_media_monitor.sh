#!/bin/bash

# Media Monitor Cron Wrapper Script
# This script checks for internet connectivity before running the media monitor application.
# It attempts to retry if the initial connectivity check fails.

# Configuration
MAX_RETRIES=3
RETRY_DELAY=600  # seconds between retries
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/logs/cron.log"

# Ensure log directory exists
mkdir -p "$SCRIPT_DIR/logs"

# Function to log messages
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# Function to check internet connectivity
check_connectivity() {
    # Try multiple reliable hosts to ensure we're not failing due to a single host being down
    local hosts=("8.8.8.8" "1.1.1.1" "google.com")

    for host in "${hosts[@]}"; do
        if ping -c 1 -W 5 "$host" &> /dev/null; then
            log "Connectivity check passed (reached $host)"
            return 0
        fi
    done

    log "Connectivity check failed (could not reach any test host)"
    return 1
}

# Main execution
log "========== Starting media monitor cron job =========="

for attempt in $(seq 1 $MAX_RETRIES); do
    log "Connectivity check attempt $attempt/$MAX_RETRIES"

    if check_connectivity; then
        log "Running media monitor application..."
        cd "$SCRIPT_DIR" || exit 1

        # Run the Python application
        python3 main.py
        exit_code=$?

        log "Media monitor finished with exit code: $exit_code"
        exit $exit_code
    else
        if [ $attempt -lt $MAX_RETRIES ]; then
            log "Retrying in $RETRY_DELAY seconds..."
            sleep $RETRY_DELAY
        else
            log "ERROR: No internet connectivity after $MAX_RETRIES attempts. Exiting."
            exit 1
        fi
    fi
done

log "========== Media monitor cron job completed =========="
