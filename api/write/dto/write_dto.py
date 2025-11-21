from pydantic import BaseModel
from typing import List, Optional


# 교육 관련 질문 DTO
class WriteQuestionRequest(BaseModel):
    message: str


class WriteQuestionResponse(BaseModel):
    answer: str


# OCR 관련 DTO
class OCRResponse(BaseModel):
    success: bool
    extracted_text: str


class ImmigrationFormValidation(BaseModel):
    success: bool
    extracted_text: str
    validations: List[dict]