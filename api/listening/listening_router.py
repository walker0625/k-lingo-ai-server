import logging

from fastapi import APIRouter, HTTPException, status, File, UploadFile

from db.session import  SessionDep

from api.listening.dto.listening_dto import ListeningResponse
from api.listening.listening_service import ListeningService

logger = logging.getLogger("__name__")
router = APIRouter()

@router.post('/audio', response_model=ListeningResponse, status_code=status.HTTP_200_OK)
def make_audio_base64_from_text(audio_text: str) -> ListeningResponse:

    try:
        service = ListeningService()  
        response = service.make_audio_base64_from_text(audio_text)
        
        return response
    
    except Exception as e:
        logger.error(f"음성 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))