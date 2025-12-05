from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Form
from fastapi.responses import JSONResponse
from typing import List, Annotated

from .write_service import WriteService
from db.session import SessionDep, get_current_active_user
from db.model.user import User

# ✅ [수정] prefix 제거! (app.py에서 이미 "/writes"로 연결함)
# 이렇게 해야 최종 URL이 "/writes/submit"이 됩니다.
router = APIRouter()


def get_write_service():
    return WriteService()


ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "bmp", "tiff", "tif", "webp"}


def is_valid_image(filename: str):
    if not filename:
        return False
    name = filename.filename if hasattr(filename, "filename") else filename
    ext = name.split(".")[-1].lower()
    return ext in ALLOWED_EXTENSIONS


# ============================================
# 1. 쓰기 문제 생성 API
# ============================================
@router.get("/questions")
async def get_writing_questions(
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
    service: WriteService = Depends(get_write_service),
):
    """
    [쓰기 문제 생성]
    사용자의 최근 인터뷰 5개를 조회하여 JSON 구조로 반환합니다.
    """
    user_id = current_user.id
    result = await service.get_writing_questions(session, user_id)
    return JSONResponse(content=result, media_type="application/json; charset=utf-8")


# ============================================
# 2. 쓰기 제출 및 평가 API
# ============================================
@router.post("/submit")
async def submit_writing_answer(
    files: List[UploadFile] = File(...),
    target_texts: List[str] = Form(...),
    service: WriteService = Depends(get_write_service),
):
    """
    [쓰기 제출 및 평가]
    다중 파일 및 텍스트 리스트 처리
    """
    # 1. 유효한 이미지 파일만 걸러내기
    valid_files = [f for f in files if is_valid_image(f)]

    if not valid_files:
        return JSONResponse(
            status_code=400, content={"message": "유효한 이미지 파일이 없습니다."}
        )

    try:
        # 2. 서비스 호출
        results = await service.evaluate_tracing(target_texts, valid_files)
        return JSONResponse(
            content=results, media_type="application/json; charset=utf-8"
        )

    except ValueError as ve:
        print(f"⚠️ 요청 데이터 오류: {ve}")
        return JSONResponse(status_code=400, content={"message": str(ve)})

    except Exception as e:
        print(f"❌ 채점 에러: {e}")
        return JSONResponse(
            status_code=500, content={"message": f"서버 에러: {str(e)}"}
        )
