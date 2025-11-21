from fastapi import APIRouter, HTTPException, UploadFile, File
from .edu_service import EduService
from .dto.edu_dto import (
    OCRResponse,
    ImmigrationFormValidation,
)
import logging

logger = logging.getLogger(__name__)
router = APIRouter()
edu_service = EduService()


@router.post("/ocr/extract", response_model=OCRResponse)
async def extract_text(file: UploadFile = File(...)):
    try:
        if not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=400, detail="이미지 파일만 업로드 가능합니다"
            )

        result = await edu_service.extract_text_from_image(file)
        return result
    except Exception as e:
        logger.error(f"OCR 처리 실패: {e}")
        raise HTTPException(status_code=500, detail="OCR 처리 중 오류가 발생했습니다")


@router.post("/immigration-form/validate", response_model=ImmigrationFormValidation)
async def validate_immigration_form(file: UploadFile = File(...)):
    try:
        if not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=400, detail="이미지 파일만 업로드 가능합니다"
            )

        result = await edu_service.validate_immigration_form(file)
        return result
    except Exception as e:
        logger.error(f"입국 심사서 검증 실패: {e}")
        raise HTTPException(status_code=500, detail="검증 중 오류가 발생했습니다")
