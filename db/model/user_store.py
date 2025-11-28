from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from sqlmodel import Field, SQLModel, Relationship
# from db.model.user import User
# from db.model.character import Character

class UserCharacter(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    character_id: int = Field(foreign_key="character.id")
    is_used: bool = Field(default=False)
    desc: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    # relation ( → User)
    user: "User" = Relationship(back_populates="user_character")
    # relation ( → Character)
    character: "Character" = Relationship(back_populates="user_character")

class UserCharacterCreate(BaseModel):
    user_id: int
    character_id: int
    desc: str

class UserCharacterResponse(BaseModel):
    id: int
    user_id: int
    username: str
    character_id: int
    character_name: str
    is_used: bool
    desc: str
    
