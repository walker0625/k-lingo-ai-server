import logging

from fastapi import APIRouter, Depends, HTTPException, status

from db.session import  SessionDep, get_session
from db.model.item import Item, ItemResponse, ItemCreate

from api.chat.chat_service import ChatService
from api.chat.dto.chat_dto import ChatRequest, ChatResponse

logger = logging.getLogger("__name__")
router = APIRouter()

@router.post('/question', response_model=ChatResponse, status_code=status.HTTP_200_OK)
def ask_question(request: ChatRequest, session: SessionDep) -> ChatResponse:
    
    try:
        service = ChatService()  
        response = service.ask_question(request)
        
        return response
    
    except Exception as e:
        logger.error(f"질문 처리 실패: {e}")
        raise HTTPException(status_code=500, detail="질문 처리 중 오류가 발생했습니다")