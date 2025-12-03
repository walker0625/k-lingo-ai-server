from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Form
from fastapi.responses import JSONResponse
from enum import Enum
from typing import List, Annotated

from .write_service import WriteService
from db.session import SessionDep, get_current_active_user
from db.model.user import User

router = APIRouter(tags=["write"])


def get_write_service():
    return WriteService()


ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "bmp", "tiff", "tif", "webp"}


def is_valid_image(filename: str):
    if not filename:
        return False
    ext = filename.split(".")[-1].lower()
    return ext in ALLOWED_EXTENSIONS


# ============================================
# 1. 쓰기 문제 생성 API (Game Start)
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
    # 서비스가 비동기이므로 await 필수
    result = await service.get_writing_questions(session, user_id)
    return JSONResponse(content=result, media_type="application/json; charset=utf-8")


# ============================================
# 2. 쓰기 제출 및 평가 API (Game Play - Multiple Files)
# ============================================
@router.post("/submit")
async def submit_writing_answer(
    files: List[UploadFile] = File(...),  # ✅ 여러 장 받도록 List로 변경
    target_text: str = Form(...),  # 정답 텍스트
    service: WriteService = Depends(get_write_service),
):
    """
    [쓰기 제출 및 평가]
    - 여러 장의 이미지 파일과 정답을 전송하면,
    - 서버가 순차적으로 모두 평가하여 결과 리스트를 반환합니다.
    """
    # 1. 유효한 이미지 파일만 걸러내기
    valid_files = []
    for file in files:
        if is_valid_image(file.filename):
            valid_files.append(file)

    if not valid_files:
        return JSONResponse(
            status_code=400, content={"message": "유효한 이미지 파일이 없습니다."}
        )

    try:
        # 2. 서비스의 다중 평가 함수 호출 (await 필수)
        results = await service.evaluate_tracing(target_text, valid_files)

        # 3. 결과 리스트 반환
        return JSONResponse(
            content=results, media_type="application/json; charset=utf-8"
        )

    except Exception as e:
        print(f"❌ 채점 에러: {e}")
        return JSONResponse(
            status_code=500, content={"message": f"서버 에러: {str(e)}"}
        )
