from pydantic import BaseModel

class ChatRequest(BaseModel):
    context: str
    user_prompt: str

class ChatResponse(BaseModel):
    answer: str