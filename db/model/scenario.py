# import logging
import random
from datetime import datetime
from typing import Optional, Any, Literal
from enum import Enum
from pydantic import BaseModel
from sqlmodel import Field, SQLModel, UniqueConstraint, Session, select, Relationship
from sqlalchemy.types import JSON
from sqlalchemy import Column
import ollama
from common.ko_util import korean_to_english_pronunciation


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
    title: str = Field(unique=True, index=True) ## 시나리오 조회용
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

class QuestLevel(Enum):
    EASY = 1
    NORMAL = 2
    HARD = 3

class ReadQuest(BaseModel):
    quest_type: Literal["symbol","color"]
    quest_level: QuestLevel
    quest_words: list[str]

class Stage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    scenario_id: int = Field(foreign_key="scenario.id")
    title: str = Field(unique=True, index=True) ## 스테이지 조회용
    type_code: StageType
    quest: list[ReadQuest] = Field(default={}, sa_column=Column(JSON))
    desc: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    ## 연결된 scenario 리스트
    scenario: "Scenario" = Relationship(back_populates="stages")

def quest_words(quests:list[ReadQuest],_type:str,level:QuestLevel):
    words = []
    for word in [q.quest_words for q in quests if q.quest_type == _type and q.quest_level == level]:
        words.extend(word)
    return words

### 읽기 시나리오 생성용
def ko_to_en(ko:str):
    system_prompt = """
        당신은 영어 번역가 입니다.
        한글 문장을 영문으로 번역하여 해당 영문만 알려주세요.
    """
    user_prompt = "한글 문장을 영문으로 번역해줘 : {}"
    response = ollama.chat(
        model="hf.co/LGAI-EXAONE/EXAONE-4.0-1.2B-GGUF:Q4_K_M",
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt.format(ko)}
        ]
    )
    return response['message']['content']

quest_template = {
    'word_data1':"{} 스티커를 찾아라",
    'word_data2':"{} 캐리어를 찾아라",
    'full_data':"{} 스티커가 붙은 {} 캐리어를 찾아라"
}
class WordData(BaseModel):
    kor: str
    eng: str
    pronunciation: str
class ReadTargetData(BaseModel):
    symbol:str
    color:str
class QuestInfo(BaseModel):
    index:int
    dificulity:QuestLevel
class QuestReadInfo(QuestInfo):
    target_data: list[ReadTargetData]
    correct_answer_index: int
    word_data1: WordData
    word_data2: WordData
    full_data: WordData
def gen_read_quest(quests:list[ReadQuest],level:QuestLevel,quest_count:int = 10):
    """
        quests : read quest list
        level  : quest level
        quest_count : 필요 갯수
        읽기 시나리오 생성
    """
    symbols = quest_words(quests,'symbol',level)
    colors = quest_words(quests,'color',level)
    quest_data = random.sample([(symbol, color) for symbol in symbols for color in colors],quest_count)
    correct_index = random.randint(0,quest_count-1)
    target_data = [ReadTargetData(symbol=q_data[0],color=q_data[1]) for q_data in quest_data]
    word_data1 = quest_template['word_data1'].format(quest_data[correct_index][0])
    word_data2 = quest_template['word_data2'].format(quest_data[correct_index][1])
    full_data = quest_template['full_data'].format(*quest_data[correct_index])
    return QuestReadInfo(
        index=1,
        dificulity=QuestLevel.EASY,
        target_data=target_data,
        correct_answer_index=correct_index,
        word_data1=WordData(
            kor = word_data1,
            eng = ko_to_en(word_data1),
            pronunciation=korean_to_english_pronunciation(word_data1)
        ),
        word_data2=WordData(
            kor = word_data2,
            eng = ko_to_en(word_data2),
            pronunciation=korean_to_english_pronunciation(word_data2)
        ),
        full_data=WordData(
            kor = full_data,
            eng = ko_to_en(full_data),
            pronunciation=korean_to_english_pronunciation(full_data)
        )
    )