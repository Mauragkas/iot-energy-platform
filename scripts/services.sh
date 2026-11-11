#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOGS_DIR="$ROOT_DIR/target/services_logs"
PIDS_FILE="$ROOT_DIR/target/services.pids"

mkdir -p "$LOGS_DIR"

start() {
    echo "Starting compiled microservices in background..."

    # Ingestor Bridge
    METRICS_PORT=8085 nohup "$ROOT_DIR/target/release/ingestor-rs" > "$LOGS_DIR/ingestor.log" 2>&1 &
    INGESTOR_PID=$!

    # Persister
    METRICS_PORT=8082 nohup "$ROOT_DIR/target/release/persister-rs" > "$LOGS_DIR/persister.log" 2>&1 &
    PERSISTER_PID=$!

    # Anomaly Worker
    METRICS_PORT=8083 PYTHONPATH="$ROOT_DIR/services/anomaly-worker-py" nohup "$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/services/anomaly-worker-py/main.py" > "$LOGS_DIR/anomaly.log" 2>&1 &
    ANOMALY_PID=$!

    # REST API
    PORT=8088 MONGO_URI="mongodb://mongo_admin:mongo_password@localhost:27018/iot_twins?authSource=admin" nohup "$ROOT_DIR/target/release/api-rs" > "$LOGS_DIR/api.log" 2>&1 &
    API_PID=$!

    echo "$INGESTOR_PID" > "$PIDS_FILE"
    echo "$PERSISTER_PID" >> "$PIDS_FILE"
    echo "$ANOMALY_PID" >> "$PIDS_FILE"
    echo "$API_PID" >> "$PIDS_FILE"

    echo "Services spawned (PIDs: $INGESTOR_PID, $PERSISTER_PID, $ANOMALY_PID, $API_PID). Waiting for readiness..."
    sleep 2

    status
}

stop() {
    echo "Stopping background microservices..."
    if [ -f "$PIDS_FILE" ]; then
        while IFS= read -r pid; do
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid" 2>/dev/null || true
            fi
        done < "$PIDS_FILE"
        rm -f "$PIDS_FILE"
    fi
    pkill -f "target/release/ingestor-rs" 2>/dev/null || true
    pkill -f "target/release/persister-rs" 2>/dev/null || true
    pkill -f "anomaly-worker-py/main.py" 2>/dev/null || true
    pkill -f "target/release/api-rs" 2>/dev/null || true
    echo "All microservices stopped."
}

status() {
    echo "Checking microservices health:"
    curl -s -w "  ✔ Ingestor (port 8085): HTTP %{http_code}\n" -o /dev/null http://localhost:8085/healthz || echo "  ✖ Ingestor: not responding"
    curl -s -w "  ✔ Persister (port 8082): HTTP %{http_code}\n" -o /dev/null http://localhost:8082/healthz || echo "  ✖ Persister: not responding"
    curl -s -w "  ✔ REST API (port 8088): HTTP %{http_code}\n" -o /dev/null http://localhost:8088/healthz || echo "  ✖ REST API: not responding"
    curl -s -w "  ✔ REST API Readyz: HTTP %{http_code}\n" -o /dev/null http://localhost:8088/readyz || echo "  ✖ REST API Readyz: not responding"
}

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    status)
        status
        ;;
    restart)
        stop
        sleep 1
        start
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
