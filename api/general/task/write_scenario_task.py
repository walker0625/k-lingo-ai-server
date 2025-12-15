import os, dotenv, json, redis
from langchain_openai import ChatOpenAI
from typing import Dict, Any
from pydantic import BaseModel
from common.ko_util import korean_to_english_pronunciation
# from api.general.service.scenario_dto import QuestWriteInfo, WriteData
# from api.general.scenario import QuestLevel

## 쓰기 생성용 클래스
class WriteScenarioSource(BaseModel):
    kor:str
    eng:str
    answer:str

## redis store process
def store_write_scenario(username: str, json_obj:Any):
    dotenv.load_dotenv()
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB = int(os.getenv("REDIS_DB", "0"))
    REDIS_EXPIRE_SECOND = int(os.getenv("REDIS_EXPIRE_SECOND", "3600"))
    redis_client = redis.StrictRedis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        decode_responses=True
    )
    redis_key = f"KLINGO-READY(W):{username}"
    redis_value = json.dumps(json_obj, ensure_ascii=False)
    redis_client.setex(redis_key, REDIS_EXPIRE_SECOND, redis_value)

# =========================================================
# 쓰기 문제 생성 메서드
# =========================================================
def _process_single_question(
    source_data: WriteScenarioSource
) -> Dict[str, Any]:
    dotenv.load_dotenv()
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    llm = ChatOpenAI(
        model="gpt-4o", 
        temperature=0, 
        api_key=OPENAI_API_KEY,
        # 아래 model_kwargs를 사용하면 LLM이 JSON을 출력하도록 강제됩니다.
        model_kwargs={"response_format": {"type": "json_object"}}
    )
    
    """
    개별 질문 처리: 발음과 번역을 생성 (동기 함수)
    """
    kor_q = source_data.kor
    eng_q = source_data.eng
    eng_ans = source_data.answer
    
    prompt = f"""
        You are a Korean language tutor.

        Input Data:
        - Korean Question: "{kor_q}"
        - User's Answer (English): "{eng_ans}"      
        Task:
        1. Translate the "User's Answer" into natural, polite Korean (Honorifics).
        2. If the "User's Answer" is incomplete or contains "...", fill in the blank with a generic plausible word (e.g., '독서', '운동') to make it a complete sentence, OR remove the "..." to make it grammatically correct.
        3. Do NOT output "..." in the final Korean sentence.      
        Output Format (JSON only, no markdown):
        {{
            "answer_kor": "..."
        }}
    """

    response = llm.invoke(prompt)
    content = response.content.strip()
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    
    llm_result = json.loads(content)
    result_data = {
        "word_data": {"kor": kor_q, "eng": eng_q, "pronunciation": ""},
        "answer": eng_ans,
        "answer_kor": ""
    }
    result_data["answer_kor"] = llm_result.get("answer_kor", eng_ans)
    result_data["word_data"]["pronunciation"] = korean_to_english_pronunciation(kor_q)
    return result_data

def get_writing_questions(username: str, source_list: list[WriteScenarioSource]):
    """
    쓰기 문제 생성 : UserInterviewResponse 클래스 이용 형식으로 변경(Redis RQ 처리용)
    생성 후 Redis KLINGO-READY(W)에 key:user_id 로 저장
    """
    print(f"****** 쓰기 시나리오 생성 시작 {username} ******")
    try:
        processed_questions = []
        for _source in source_list:
            processed_questions.append(
                _process_single_question(_source)
            )
        store_write_scenario(username, processed_questions)
        print(f"****** 쓰기 시나리오 Redis 저장 완료 : {username} ******")
    except Exception as e:
        print(f"****** 쓰기 시나리오 생성 실패 {username} : {e} ******")
        raise Exception(f"Failed to create writing scenario : {e}")
    
    
# def get_writing_questions(room_id: int, username: str, source_list: list[WriteScenarioSource]):
#     """
#     쓰기 문제 생성 : UserInterviewResponse 클래스 이용 형식으로 변경(Redis RQ 처리용)
#     생성 후 Redis KLINGO-READY(W)에 key:user_id 로 저장
#     """
#     print(f"****** 쓰기문제 생성 시작 {username}******")
#     try:
#         processed_questions = []
#         for _source in source_list:
#             processed_questions.append(
#                 _process_single_question(_source)
#             )
            
#         print(f"쓰기 시나리오 {len(processed_questions)}개 문제 생성 완료")
#         ## Redis 저장 처리

#         questWriteInfo = QuestWriteInfo(
#             index=1, difficulty=QuestLevel.EASY,
#             room_id=room_id,
#             question=[]
#         )
#         for info in processed_questions:
#             questWriteInfo.question.append(
#                 WriteData.model_validate(info, from_attributes=True)
#             )

#         store_write_scenario(username, questWriteInfo)
#         print(f"쓰기 시나리오 Redis 저장 완료 : {username}")
#     except Exception as e:
#         print(f"쓰기문제 생성 실패 {username} : {e}")
#         raise Exception(f"Failed to create write scenario : {e}")