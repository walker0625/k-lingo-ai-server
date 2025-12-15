import os
from fastapi import APIRouter, Depends, HTTPException, status
from pathlib import Path
## logger
from loguru import logger
## user router
router = APIRouter()

# Routes
@router.get("/{log_file}")
def read_logfile(log_file:str):
    logger.info("********* log viewer")
    logger.info(log_file)
    
    log_file_path = os.path.join("./logs",log_file)
    if not os.path.exists(log_file_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File not found"
        )
    log_data = Path(log_file_path).read_text(encoding="utf-8")
    return {"result":log_data}
