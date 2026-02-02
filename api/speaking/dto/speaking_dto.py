from pydantic import BaseModel
from typing import Optional

class SpeakingResponse(BaseModel):
    grammar_score: Optional[int] = None
    context_score: Optional[int] = None
    final_overall_score: Optional[int] = None
    final_feedback: Optional[str] = None
    
    # 시스템 오류 처리 필드
    status: str = "SUCCESS"  # SUCCESS, SYSTEM_ERROR, PARTIAL_ERROR
    is_system_error: bool = False
    error_message: Optional[str] = None