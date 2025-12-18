#!/bin/bash

# =================================================================
# RQ 워커 실행 스크립트
# =================================================================

# 1. 환경 설정 (필요에 따라 수정)

REDIS_URL="redis://100.100.53.32:6379"
QUEUES="KLINGO:RQ"
VENV_PATH=".venv/bin/activate"
LOG_DIR="./logs"
# =================================================================
# 2. 스크립트 실행 로직

echo "Starting RQ Worker..."
echo "Redis URL: $REDIS_URL"
echo "Queues: $QUEUES"

# log 디렉토리 생성
mkdir -p "$LOG_DIR"
# 가상 환경 활성화
if [ -n "$VENV_PATH" ]; then
    source "$VENV_PATH"
    echo "Virtual environment activated."
fi

# RQ 워커 실행
rq worker --url "$REDIS_URL" $QUEUES

# nohup rq worker --url "$REDIS_URL" --name "klingo_worker" $QUEUES > "$LOG_DIR/rq_worker.log" 2>&1 &
# echo "RQ Worker started. Logs are being written to $LOG_DIR/rq_worker.log"
# =================================================================