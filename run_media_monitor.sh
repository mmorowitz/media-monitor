#!/bin/bash

# Media Monitor Cron Wrapper Script
# This script checks for internet connectivity before running the media monitor application.
# It attempts to retry if the initial connectivity check fails.

# Configuration
MAX_RETRIES=3
RETRY_DELAY=60  # seconds between retries
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$SCRIPT_DIR/venv/bin/python"
HEALTHCHECK_URL="https://hc-ping.com/3bed5299-97cb-4dcf-8818-921c7b3c5dca"
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
        "$PYTHON_BIN" main.py
        exit_code=$?

        log "Media monitor finished with exit code: $exit_code"

        # Send health check ping if application succeeded
        if [ $exit_code -eq 0 ]; then
            log "Sending health check ping..."
            if curl -fsS -m 10 --retry 5 -o /dev/null "$HEALTHCHECK_URL"; then
                log "Health check ping sent successfully"
            else
                log "WARNING: Failed to send health check ping"
            fi
        else
            log "Skipping health check ping due to application error"
        fi

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
