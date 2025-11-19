from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import Dict
import logging

# 라우터 생성
router = APIRouter()

# 로거 설정
logger = logging.getLogger("app")

@router.get("/health")
async def health_check():
    """
    EDU API 상태 확인
    """
    logger.info("EDU health check called")
    return {
        "status: "OK",
        "message": "EDU API is running"
    }

@router.post("/listening/broadcast", response_model = 
