from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from sqlmodel import Field, SQLModel
from enum import Enum

class ItemType(Enum):
    TOP = 1
    BOTTOM = 2
    SHOES = 3
    GLOVES = 4
    HAT = 5    

# Models
class Item(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    type: ItemType
    name: str
    desc: str = Field(default="")
    price: int = Field(default=1)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
class ItemResponse(BaseModel):
    id: int
    type: ItemType
    name: str
    desc: str
    price: int
    
class ItemCreate(BaseModel):
    type: ItemType
    name: str
    desc: str