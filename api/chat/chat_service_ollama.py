
import ollama
import logging
from api.chat.dto.chat_dto import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)

class ChatService:
    
    def ask_question(self, system_prompt:str, user_prompt:str) -> ChatResponse: 

        response = ollama.chat(
            model="qwen2:7b-instruct",
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ]
        )
        
        return response['message']['content']