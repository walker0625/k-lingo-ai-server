from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from enum import Enum
from typing import List, Annotated, Optional # Optional 추가
from pydantic import BaseModel

from .dto.write_dto import (
    ImmigrationFormValidation,
    OCRResponse,
)
from .write_service import WriteService

# 쓰기 문제 생성용
from db.session import SessionDep, get_current_active_user
from db.model.user import User

router = APIRouter(tags=["write"])

# [수정 1] 전역 변수 삭제 (여기서 에러가 자주 터짐)
# service = WriteService() 

# [수정 2] 서비스를 필요할 때만 불러오는 함수 생성
def get_write_service():
    return WriteService()

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
    # [수정 3] 함수 안으로 서비스 주입 (Depends 사용)
    service: WriteService = Depends(get_write_service)
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
    file: UploadFile = File(...), 
    mode: OCRType = OCRType.PADDLE,
    # [수정 4] 여기도 서비스 주입
    service: WriteService = Depends(get_write_service)
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
        # 에러 메시지를 좀 더 명확하게 반환
        raise HTTPException(status_code=500, detail=f"검증 오류: {str(e)}")


# ============================================
# 쓰기 문제 생성 API
# ============================================

class WritingQuestionData(BaseModel):
    """쓰기 문제 데이터"""
    interview_id: int
    korean_question: str
    english_question: str
    expected_answer: str  # 예상 답변 (한글)


class WritingQuestionsResponse(BaseModel):
    """쓰기 문제 생성 응답"""
    status: str
    user_id: int
    total_questions: int
    questions: List[WritingQuestionData]
    message: Optional[str] = None # 에러 메시지 필드 안전하게 추가


@router.get("/questions", response_model=WritingQuestionsResponse)
async def get_writing_questions(
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
    # [수정 5] 여기도 서비스 주입
    service: WriteService = Depends(get_write_service)
):
    """
    쓰기 문제 5개 랜덤 생성
    """
    # service 변수를 위에서 주입받았으므로 바로 사용 가능
    result = await service.get_writing_questions(session, current_user.id)
    
    if result["status"] != "success":
        # status가 fail일 때 message가 없으면 에러가 날 수 있으므로 .get() 사용
        raise HTTPException(status_code=400, detail=result.get("message", "문제 생성 실패"))
    
    return WritingQuestionsResponse(**result)