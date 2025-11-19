
import ollama
import logging
from api.chat.dto.chat_dto import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)

class ChatService:
    
    def ask_question(self, request: ChatRequest) -> ChatResponse: 

        response = ollama.chat(
            model='hf.co/LGAI-EXAONE/EXAONE-4.0-1.2B-GGUF:Q4_K_M',
            messages=[
                {'role': 'system', 'content': '너는 한국어 교육에 능통한 개인 과외 선생님이야'},
                {'role': 'user', 'content': request.message}
            ]
        )
        
        return ChatResponse(message=response['message']['content'])