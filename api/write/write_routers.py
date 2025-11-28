from fastapi import APIRouter, HTTPException, UploadFile, File
from enum import Enum
from typing import List

from .dto.write_dto import (
    ImmigrationFormValidation,
    OCRResponse,
    BridgeRequest,
    BridgeResponse,
)
from .write_service import WriteService
from .write_agent import WriteAgent

router = APIRouter(tags=["write"])

service = WriteService()
write_agent = WriteAgent()

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "bmp", "tiff", "tif", "webp"}


class OCRType(str, Enum):
    PADDLE = "paddle"
    NAVER = "naver"


# 이미지 확장자 검사 (True/False 반환)
def is_valid_image(filename: str):
    if not filename:
        return False
    ext = filename.split(".")[-1].lower()
    return ext in ALLOWED_EXTENSIONS


@router.post("/ocr/extract", response_model=List[OCRResponse])
async def extract_text(
    files: List[UploadFile] = File(...),  # 무조건 리스트로 받음
    mode: OCRType = OCRType.PADDLE,
):
    """
    [통합 OCR] 이미지를 1장 또는 여러 장 업로드하면, 텍스트를 추출해서 리스트로 돌려줍니다.
    """
    results = []

    for file in files:
        if not is_valid_image(file.filename):
            results.append(
                {
                    "filename": file.filename,
                    "text": "",
                    "error": "지원하지 않는 파일 형식",
                }
            )
            continue

        try:
            await file.seek(0)
            result_data = await service.process_immigration(file, mode.value)

            results.append(
                {"filename": file.filename, "text": result_data["text"], "error": None}
            )

        except Exception as e:
            print(f"⚠️ [OCR Error] {file.filename}: {e}")
            results.append({"filename": file.filename, "text": "", "error": str(e)})

    return results


@router.post("/immigration/validate", response_model=ImmigrationFormValidation)
async def validate_immigration_form(
    file: UploadFile = File(...), mode: OCRType = OCRType.PADDLE
):
    """
    [입국신고서 검증]
    업로드된 입국신고서 이미지를 OCR로 분석하고, 기재된 내용이 규칙에 맞는지 검증합니다.
    필수 항목 누락이나 잘못된 형식 등을 체크하여 결과를 반환합니다.
    """
    if not is_valid_image(file.filename):
        raise HTTPException(status_code=400, detail="지원하지 않는 파일입니다.")

    try:
        return await service.process_immigration(file, mode.value)
    except Exception as e:
        print(f"[Validation Error] {str(e)}")
        raise HTTPException(status_code=500, detail=f"검증 오류: {str(e)}")


@router.post(
    "/bridge",
    response_model=BridgeResponse,
    summary="[개발중] Bridge Agent (영어 답변 분석)",
    description="이 기능은 현재 개발 중입니다. 사용자의 영어 답변을 분석해 한국어 가이드를 줍니다.",
)
async def get_writing_bridge(request: BridgeRequest):
    """
    [Bridge Agent]
    사용자의 영어 인터뷰 답변을 분석하여, 한국어 쓰기 학습을 위한 가이드를 생성합니다.
    사용자의 의도를 파악하고 DB에서 적절한 한국어 질문을 매칭하여 난이도별(Easy/Normal/Hard) 예시 답변을 제공합니다.
    """
    try:
        result = await write_agent.generate_guide(request.user_answer)
        return result
    except Exception as e:
        print(f"[Bridge Agent Error] {e}")
        raise HTTPException(
            status_code=500, detail=f"에이전트 처리 중 오류 발생: {str(e)}"
        )
