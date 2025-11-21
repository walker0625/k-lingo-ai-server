from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from sqlmodel import Field, SQLModel, UniqueConstraint, Session, select
from enum import Enum

class Store(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    price: float = Field(default=1.0)
    desc: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

class StoreCreate(BaseModel):
    name: str
    desc: str

class StoreResponse(BaseModel):
    id: int
    name: str
    price: float
    desc: str
