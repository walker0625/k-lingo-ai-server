from fastapi import APIRouter, HTTPException, status

from db.session import  SessionDep

from api.chat.chat_service import ChatService
from api.chat.dto.chat_dto import ChatRequest, ChatResponse
## logger
from loguru import logger

router = APIRouter()

@router.post('/answers', response_model=ChatResponse, status_code=status.HTTP_200_OK)
def ask_question(request: ChatRequest, session: SessionDep) -> ChatResponse:
    
    try:
        service = ChatService()  
        answer = service.ask_question(request.system_prompt, request.user_prompt)
        
        return ChatResponse(answer=answer)
    
    except Exception as e:
        logger.error(f"질문 처리 실패: {e}")
        raise HTTPException(status_code=500, detail="질문 처리 중 오류가 발생했습니다")