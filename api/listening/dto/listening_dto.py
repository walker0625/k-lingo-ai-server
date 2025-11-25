from pydantic import BaseModel

class ListeningResponse(BaseModel):
    audio_text: str
    audio_base64: str  # 문자열(Base64)로 audio 파일 변환하여 응답