from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from sqlmodel import Field, SQLModel, Relationship
from .interview import UserInterview
from .user_store import UserCharacter

# Models
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    fullname: str = Field(default='')
    password: str
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    ## relation
    user_character: list["UserCharacter"] = Relationship(back_populates="user")#, link_model=UserCharacter)
    user_interview: list["UserInterview"] = Relationship(back_populates="user")#, link_model=UserInterview)

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
