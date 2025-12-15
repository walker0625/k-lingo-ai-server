from pydantic import BaseModel
from api.general.scenario import QuestLevel

class WordData(BaseModel):
    kor: str
    eng: str
    pronunciation: str
class TargetItem(BaseModel):
    name:str
    code:str
class TargetData(BaseModel):
    word1:TargetItem
    word2:TargetItem
class QuestBase(BaseModel):
    index:int
    difficulty:QuestLevel
    room_id:int
    
## Reading, Listening Scenario Quest Info    
class QuestReadInfo(QuestBase):
    target_data: list[TargetData]
    correct_answer_index: int
    word_data1: WordData
    word_data2: WordData
    full_data: WordData

class QuestListenInfo(QuestReadInfo):
    voice_data: str
    
## Writing Scenario Quest Info
class WriteData(BaseModel):
    word_data: WordData
    answer: str
    answer_kor: str

class QuestWriteInfo(QuestBase):
    question: list[WriteData]

## Speaking Scenario Quest Info
class SpeakData(WordData):
    voice_data: str | None = None

class QuestSpeakInfo(QuestBase):
    audio: list[SpeakData]