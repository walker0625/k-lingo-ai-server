import os, logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse
from common.file_util import save_input_file_to_temp

## logger
logger = logging.getLogger("app")
## user router
router = APIRouter()

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    logger.debug(f"upload file : {file}")
    result = save_input_file_to_temp(file)
    logger.debug(result)
    return JSONResponse(result)