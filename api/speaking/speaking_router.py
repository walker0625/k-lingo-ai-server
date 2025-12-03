# api/speaking/speaking_router.py
from fastapi import APIRouter, HTTPException, status, File, UploadFile

from api.speaking.dto.speaking_dto import SpeakingResponse
from api.speaking.speaking_service import SpeakingService # 💡 import는 유지
## logger
from loguru import logger
router = APIRouter()

@router.post('/judges', response_model=SpeakingResponse, status_code=status.HTTP_200_OK)
def listen_speaking_and_judge(question: str, audio: UploadFile = File(...)) -> SpeakingResponse:
    
    try:
        #💡 요청이 들어올 때마다 SpeakingService 인스턴스 생성
        #   (내부적으로 모델 로딩은 __init__에서 한 번만 발생)
        service = SpeakingService() 
        response = service.listen_speaking_and_judge(question, audio)
        
        return response
    
    except HTTPException as http_e:
        # 💡 HTTP 예외는 그대로 다시 발생 (e.g. 400, 503)
        raise http_e
        
    except Exception as e:
        logger.error(f"듣기 응답 실패: {e}")
        # 💡 AI 모델 로딩 실패 시 500 대신 503 Service Unavailable을 고려
        raise HTTPException(status_code=500, detail="듣기 응답 처리 중 오류가 발생했습니다")