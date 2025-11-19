from pydantic import BaseModel
from typing import Optional
## general api 내부 사용 모델 정의

class MyModel(BaseModel):
    """사용자 기본 정보 모델"""
    username: str
    email: Optional[str] = None
