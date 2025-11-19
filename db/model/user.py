from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from sqlmodel import Field, SQLModel

# Models
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.now)

class UserCreate(BaseModel):
    username: str
    email: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool

# JWT Token
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None