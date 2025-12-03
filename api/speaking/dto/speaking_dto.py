from pydantic import BaseModel
from typing import Optional

class SpeakingResponse(BaseModel):
    grammar_score: Optional[int]
    context_score: Optional[int]
    final_overall_score: Optional[int]
    final_feedback: Optional[str]