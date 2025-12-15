from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from sqlmodel import Field, SQLModel #, Relationship
from db.model.user import User

class Transaction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    ## from username None인 경우 시스템이 부여한 것(예: 이벤트, ...)
    from_username: str = Field(default=None, foreign_key="user.username", nullable=True)
    to_username: str = Field(foreign_key="user.username")
    price: float
    desc: str
    created_at: datetime = Field(default_factory=datetime.now)
    # relation ( → User)
    # user: User = Relationship(back_populates="user")

class TransactionCreate(BaseModel):
    from_username: str
    to_username: str
    price: float
    desc: str

class TransactionResponse(BaseModel):
    id: int
    from_username: str
    to_username: str
    price: float
    desc: str
    created_at: datetime
    
