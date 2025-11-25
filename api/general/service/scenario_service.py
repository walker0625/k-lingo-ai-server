import logging
import ollama
import random
from pydantic import BaseModel
from api.general.scenario import ReadingQuest,ListeningQuest, QuestLevel, StageType
from common.ko_util import korean_to_english_pronunciation

# logger
logger = logging.getLogger("app")

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
class QuestInfo(BaseModel):
    index:int
    dificulity:QuestLevel
class QuestReadOrListenInfo(QuestInfo):
    target_data: list[TargetData]
    correct_answer_index: int
    word_data1: WordData
    word_data2: WordData
    full_data: WordData

def quest_words(quests:list[ReadingQuest | ListeningQuest],_type:str,level:QuestLevel):
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
    StageType.READING:{
        'word_data1':"{} 스티커를 찾아라",
        'word_data2':"{} 캐리어를 찾아라",
        'full_data':"{} 스티커가 붙은 {} 캐리어를 찾아라"
    },
    StageType.LISTENING:{
        'word_data1':"{}에서 찾아라",
        'word_data2':"제일 맛있는 {} 집을 찾아라",
        'full_data':"{}에서 제일 맛있는 {} 집을 찾아라"
    }
}

def quest_items(quests:list[BaseModel],_type:str,level:QuestLevel):
    items = []
    for item_zip in [zip(q.quest_codes,q.quest_words)
                 for q in quests if q.quest_type == _type and q.quest_level == level]:
        for item in item_zip:
            items.append(TargetItem(code=item[0],name=item[1]))
    return items
def gen_read_or_listen_quest(stage_type:StageType, quests:list[BaseModel],level:QuestLevel,quest_count:int = 10):
    """
        quests : read quest list
        level  : quest level
        quest_count : 필요 갯수
        읽기 시나리오 생성
    """
    word1_type = 'symbol' if stage_type == StageType.READING else 'region'
    word2_type = 'color' if stage_type == StageType.READING else 'food'
    word1 = quest_items(quests,word1_type,level)
    word2 = quest_items(quests,word2_type,level)
    quest_data = random.sample([(w1, w2) for w1 in word1 for w2 in word2],quest_count)
    correct_index = random.randint(0,quest_count-1)
    target_data = [TargetData(word1=q_data[0],word2=q_data[1]) for q_data in quest_data]
    word_data1 = quest_template[stage_type]['word_data1'].format(quest_data[correct_index][0].name)
    word_data2 = quest_template[stage_type]['word_data2'].format(quest_data[correct_index][1].name)
    full_data = quest_template[stage_type]['full_data'].format(quest_data[correct_index][0].name,quest_data[correct_index][1].name)
    return QuestReadOrListenInfo(
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