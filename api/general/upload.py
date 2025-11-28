from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse
from common.file_util import save_input_file_to_temp
## logger
from loguru import logger
## user router
router = APIRouter()

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    logger.debug(f"upload file : {file}")
    result = save_input_file_to_temp(file)
    logger.debug(result)
    return JSONResponse(result)