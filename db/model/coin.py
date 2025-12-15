from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from sqlmodel import Field, SQLModel
from enum import Enum

class Coin(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    value: float = Field(default=1.0)
    desc: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

class CoinCreate(BaseModel):
    name: str
    desc: str

class CoinResponse(BaseModel):
    id: int
    name: str
    value: float
    desc: str
