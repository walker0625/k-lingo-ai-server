## READING, LISTENING Scenario
import random
import ollama
from typing import Literal
from pydantic import BaseModel
from db.model.scenario import ReadingQuest,ListeningQuest, QuestLevel, StageType
from api.general.service.scenario_dto import WordData, TargetItem, TargetData, QuestReadInfo, QuestListenInfo
from common.ko_util import korean_to_english_pronunciation
from api.listening.listening_service import ListeningService
## logger
from loguru import logger
## tts
tts = ListeningService()

### quest type, level에 해당하는 quest 정보 가져오기
def quest_words(quests:list[ReadingQuest | ListeningQuest],_type:str,level:QuestLevel):
    words = []
    for word in [q.quest_words for q in quests if q.quest_type == _type and q.quest_level == level]:
        words.extend(word)
    return words

### 읽기, 듣기 시나리오 생성용
def ko_to_en(ko:str):
    system_prompt = """
        당신은 **영어** 번역 전문가 입니다.
        한글 문장을 영문으로 번역하여 **번역된 영문**만 알려주세요.
        다른 설명이나 인사는 **절대로** 포함하지 마세요.
    """
    system_prompt = """당신은 한국어 문장을 **영어**로 번역하는 전문 영어 번역가입니다. 
            번역할 한국어 문장을 입력받으면, 해당 문장의 **영어 번역 결과**만 출력하고
            다른 설명이나 추가 문장은 절대 포함하지 마세요."""
    user_prompt = "한글 문장을 영문으로 번역해줘 : {}"

    ko_sample1 = "하늘이 매우 파랗습니다."
    en_answer1 = "The sky is very blue."
    ko_sample2 = "나는 사과를 먹었다."
    en_answer2 = "He ate a apple."
    response = ollama.chat(
        model="hf.co/LGAI-EXAONE/EXAONE-4.0-1.2B-GGUF:Q4_K_M",
        messages=[
            {'role': 'system', 'content': system_prompt},
            ## 예시
            {'role': 'user', 'content': user_prompt.format(ko_sample1)},
            {'role': 'assistant', 'content': en_answer1},
            {'role': 'user', 'content': user_prompt.format(ko_sample2)},
            {'role': 'assistant', 'content': en_answer2},
            ## 사용자 정보
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
def gen_read_or_listen_quest(stage_type: Literal[StageType.READING, StageType.LISTENING],
        quests:list[BaseModel],level:QuestLevel,quest_count:int = 10):
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
    if stage_type == StageType.READING:
        return QuestReadInfo(
            index=1,
            difficulty=level,
            room_id=0,
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
    else: #if stage_type == StageType.LISTENING:
        return QuestListenInfo(
            index=1,
            difficulty=level,
            room_id=0,
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
            ),
            voice_data = tts.make_audio_base64_from_text(full_data).audio_base64
        )