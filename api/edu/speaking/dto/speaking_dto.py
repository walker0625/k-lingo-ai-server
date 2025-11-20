from pydantic import BaseModel

class SpeakingResponse(BaseModel):
    answer: str