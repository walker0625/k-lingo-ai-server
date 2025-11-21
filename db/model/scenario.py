# import logging
from datetime import datetime
from typing import Optional, Any, Literal
from pydantic import BaseModel
from sqlmodel import Field, SQLModel, UniqueConstraint, Session, select, Relationship
from sqlalchemy.types import JSON
from sqlalchemy import Column
from enum import Enum

## logger
# logger = logging.getLogger("app")

## 교육 대상자 언어권
class LangType(Enum):
    EN = 1
    JP = 2

# Models
class Scenario(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    lang_code: LangType
    scenario: str
    desc: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    ## 보유한 stage 리스트
    stages: list["Stage"] = Relationship(back_populates="scenario")
    
## 교육 대상자 언어권
class StageType(Enum):
    READING = 1
    LISTENING = 2
    WRITING = 3
    SPEAKING = 4

class ReadQuest(BaseModel):
    quest_type: Literal["symbol","color"]
    quest_level: Literal[1,2,3]
    quest_words: list[str]

class Stage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    scenario_id: int = Field(foreign_key="scenario.id")
    type_code: StageType
    quest: list[ReadQuest] = Field(default={}, sa_column=Column(JSON))
    desc: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    ## 연결된 scenario 리스트
    scenario: "Scenario" = Relationship(back_populates="stages")

def quest_words(quests:list[ReadQuest],_type:str,level:int):
    words = []
    for word in [q.quest_words for q in quests if q.quest_type == _type and q.quest_level == level]:
        words.extend(word)
    return words