from fastapi import APIRouter, HTTPException, status, File, UploadFile, Depends
from typing import Annotated

from db.session import get_current_active_user
from db.model.user import User

from api.chat.chat_service import ChatService
from api.chat.dto.chat_dto import ChatResponse
## logger
from loguru import logger

router = APIRouter()

@router.post('/answers', response_model=ChatResponse, status_code=status.HTTP_200_OK)
def ask_question(
    current_user: Annotated[User, Depends(get_current_active_user)],
    context: str, 
    audio: UploadFile = File(...)
    ) -> ChatResponse:
    
    try:
        service = ChatService()  
        answer = service.ask_question(current_user.username, context, audio)
        
        return ChatResponse(answer=answer)
    
    except Exception as e:
        logger.error(f"질문 처리 실패: {e}")
        raise HTTPException(status_code=500, detail="질문 처리 중 오류가 발생했습니다")