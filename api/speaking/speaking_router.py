import logging

from fastapi import APIRouter, HTTPException, status, File, UploadFile

from db.session import  SessionDep

from api.speaking.dto.speaking_dto import SpeakingResponse
from api.speaking.speaking_service import SpeakingService

logger = logging.getLogger("__name__")
router = APIRouter()

@router.post('/questions', response_model=SpeakingResponse, status_code=status.HTTP_200_OK)
def listen_speaking_and_answer(audio: UploadFile = File(...)) -> SpeakingResponse:

    try:
        service = SpeakingService()  
        response = service.listen_speaking_and_answer(audio)
        
        return response
    
    except Exception as e:
        logger.error(f"듣기 응답 실패: {e}")
        raise HTTPException(status_code=500, detail="듣기 응답 처리 중 오류가 발생했습니다")