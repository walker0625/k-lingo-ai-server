
import ollama
import logging
from api.chat.dto.chat_dto import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)

class ChatService:
    
    def ask_question(self, system_prompt:str, user_prompt:str) -> ChatResponse: 

        response = ollama.chat(
            model="hf.co/LGAI-EXAONE/EXAONE-4.0-1.2B-GGUF:Q4_K_M",
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ]
        )
        
        return response['message']['content']