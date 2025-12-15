from datetime import datetime
from typing import Optional
from enum import Enum
from pydantic import BaseModel
from sqlmodel import Field, SQLModel, UniqueConstraint, Relationship
from db.model.user_store import UserCharacter

class CharacterType(Enum):
    AVATAR = 1
    COLOR = 2

# Models
class Character(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    type_code: CharacterType
    idx: int
    name: str
    desc: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    ## 보유한 유저 리스트
    user_character: list["UserCharacter"] = Relationship(back_populates="character")#, link_model=UserCharacter)

    __table_args__ = (
        UniqueConstraint("type_code", "idx", name="character_type_index"),
    )

class CharacterCreate(BaseModel):
    type_code: CharacterType
    name: str
    desc: str

class CharacterResponse(BaseModel):
    id: int
    type_code: CharacterType
    idx: int
    name: str
    desc: str