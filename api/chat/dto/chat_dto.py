from pydantic import BaseModel

class ChatRequest(BaseModel):
    system_prompt: str
    user_prompt: str

class ChatResponse(BaseModel):
    answer: str