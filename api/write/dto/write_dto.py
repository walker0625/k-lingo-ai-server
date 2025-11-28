from pydantic import BaseModel
from typing import List, Optional

# 1. 단순 OCR 응답용
class OCRResponse(BaseModel):
    filename: str 
    text: str 
    error: Optional[str] = None

# 2. 입국 심사서 검증 항목 (질문-답변)
class ValidationItem(BaseModel):
    question: str
    answer: str

# 3. 입국 심사서 전체 검증 응답
class ImmigrationFormValidation(BaseModel):
    mode: str                         
    text: str                         
    validations: List[ValidationItem]