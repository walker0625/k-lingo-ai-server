from pydantic import BaseModel

class ChatRequest(BaseModel):
    context: str
    user_prompt: str

class ChatResponse(BaseModel):
    question: str
    answer: str
    
class DailyResponse(BaseModel):
    question: str
    answer: str