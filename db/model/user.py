from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from sqlmodel import Field, SQLModel, Relationship, Session, select
# from db.model.user_store import UserCharacter

# Models
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    fullname: str = Field(default='')
    password: str
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    ## 구매한 혹은 선물 받은 캐릭터 리스트(외형, 컬러...)
    characters: list["UserCharacter"] = Relationship(back_populates="user")

class UserCreate(BaseModel):
    username: str
    fullname: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    fullname: str
    is_active: bool

# JWT Token
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    
## uer util
def get_user_by_id(session: Session, user_id: int) -> Optional[User]:
    statement = select(User).where(User.id == user_id)
    return session.exec(statement).first()