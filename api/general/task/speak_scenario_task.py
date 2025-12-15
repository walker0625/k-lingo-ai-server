import json, os, dotenv, redis
from typing import Any
from pydantic import BaseModel
from api.listening.listening_service import ListeningService
from common.ko_util import korean_to_english_pronunciation

## 쓰기 생성용 클래스
class SpeakScenarioSource(BaseModel):
    kor:str
    eng:str
    answer:str

## redis store process
def store_speak_scenario(username: str, json_obj:Any):
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
    redis_key = f"KLINGO-READY(S):{username}"
    redis_value = json.dumps(json_obj, ensure_ascii=False)
    redis_client.setex(redis_key, REDIS_EXPIRE_SECOND, redis_value)

def get_speaking_questions(username: str, source_list: list[SpeakScenarioSource]):
    print(f"****** 말하기 시나리오 생성 시작 {username} ******")
    try:
        audio_data_list = []
        for _source in source_list:
            try:
                #1. TTS (Text-to-Speech) 서비스 호출
                service = ListeningService() 
                response = service.make_audio_base64_from_text(_source.kor)
                #2. 한국어 발음 표기 생성 (korean_to_english_pronunciation 함수 사용)
                pronunciation = korean_to_english_pronunciation(_source.kor)
                #3. 각 항목을 원하는 JSON 'audio' 리스트의 형태로 가공
                audio_item = {
                    "kor": _source.kor,
                    "eng": _source.eng,
                    "pronunciation": pronunciation,
                    "voice_data": response.audio_base64
                }
                audio_data_list.append(audio_item)
                print(f"Processed: {_source.kor}")
            except Exception as e:
                # 서비스 호출 중 발생하는 예외 처리
                print(f"Error processing interview ID {_source.kor}: {e}")
                continue # 문제 발생 항목은 건너뛰고 다음 항목으로 진행
        store_speak_scenario(username, audio_data_list)
        print(f"****** 말하기 시나리오 Redis 저장 완료 : {username} ******")
    except Exception as e:
        print(f"****** 말하기 시나리오 생성 실패 {username} : {e} ******")
        raise Exception(f"Failed to create speaking scenario : {e}")