import os
from openai import OpenAI

from fastapi import APIRouter, HTTPException, status, File, UploadFile, Depends
from typing import Annotated, Optional

from db.session import SessionDep, get_current_active_user
from db.model.user import User

from api.chat.chat_service import ChatService
from api.chat.dto.chat_dto import ChatResponse

from api.chat.dto.chat_dto import DailyResponse

## logger
from loguru import logger

router = APIRouter()

@router.post('/answers', response_model=ChatResponse, status_code=status.HTTP_200_OK)
def ask_question(
    session: SessionDep,
    user: Annotated[User, Depends(get_current_active_user)],
    context: Optional[str] = None, 
    question: Optional[str] = None,
    audio: Optional[UploadFile] = File(None),
    level: int = 1
    ) -> ChatResponse:
    
    try:
        service = ChatService()  
        return service.ask_question(session, user, context, question, audio, level)
    
    except Exception as e:
        logger.error(f"질문 처리 실패: {e}")
        raise HTTPException(status_code=500, detail="질문 처리 중 오류가 발생했습니다")
    
@router.get('/dailys', response_model=DailyResponse, status_code=status.HTTP_200_OK)
def ask_question(
    system: Optional[str] = None, 
    question: Optional[str] = None
    ) -> DailyResponse:
    
    try:
        
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system or "You are a helpful assistant."},
                {"role": "user", "content": question}
            ]
        )
        
        return DailyResponse(question=question, answer=response.choices[0].message.content)
    
    except Exception as e:
        logger.error(f"질문 처리 실패: {e}")
        raise HTTPException(status_code=500, detail="질문 처리 중 오류가 발생했습니다")