from fastapi import APIRouter, HTTPException, UploadFile, File
from enum import Enum
from .dto.write_dto import ImmigrationFormValidation, OCRResponse
from .write_service import WriteService

router = APIRouter(tags=["write"])
service = WriteService()

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "bmp", "tiff", "tif", "webp"}


class OCRType(str, Enum):
    PADDLE = "paddle"
    NAVER = "naver"


def validate_image(file: UploadFile):
    ext = file.filename.split(".")[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="지원하지 않는 파일입니다.")


@router.post("/ocr/extract", response_model=OCRResponse)
async def extract_text_only(
    file: UploadFile = File(...), mode: OCRType = OCRType.PADDLE
):
    validate_image(file)
    try:
        result = await service.process_immigration(file, mode.value)
        return {"text": result["text"]}
    except Exception:
        raise HTTPException(status_code=500, detail="OCR 추출 실패")


@router.post("/immigration/validate", response_model=ImmigrationFormValidation)
async def validate_immigration_form(
    file: UploadFile = File(...), mode: OCRType = OCRType.PADDLE
):
    validate_image(file)
    try:
        return await service.process_immigration(file, mode.value)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"검증 오류: {str(e)}")
