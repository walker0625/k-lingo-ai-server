from dotenv import load_dotenv
load_dotenv()
import os, json
import redis.asyncio as redis
from redis import Redis
from rq import Queue
from typing import Dict, Any
from enum import Enum
from db.model.progress import ProgressResponse
from db.model.scenario import StageType
from loguru import logger

class RedisPageType(Enum):
    CURRENT_STAGE = 0
    READY_READING = 1
    READY_LISTENING = 2
    READY_WRITING = 3
    READY_SPEAKING = 4
            
REDIS_HOST = os.environ["REDIS_HOST"]
REDIS_PORT = int(os.environ["REDIS_PORT"])
REDIS_EXPIRE_SECOND = int(os.environ["REDIS_EXPIRE_SECOND"])
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_QUEUE_NAME = os.getenv("REDIS_QUEUE_NAME", "default")

REDIS_PAGE_MAP = {
    RedisPageType.CURRENT_STAGE     : "KLINGO-CURRENT",      ## 현재 진행 시나리오
    RedisPageType.READY_READING     : "KLINGO-READY(R)",     ## 대기 시나리오 - 읽기
    RedisPageType.READY_LISTENING   : "KLINGO-READY(L)",     ## 대기 시나리오 - 듣기
    RedisPageType.READY_WRITING     : "KLINGO-READY(W)",     ## 대기 시나리오 - 쓰기
    RedisPageType.READY_SPEAKING    : "KLINGO-READY(S)"      ## 대기 시나리오 - 말하기
}

class StateStore:
    """
        SingleTon Redis Service Class
        사용 : store = StateStore(), store.save_...
    """
    _instance = None
    def __new__(cls, *args, **kwargs):
        ## instance 생성용
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls.redis_store = None
        return cls._instance
    
    def __init__(self) -> None:
        if self.redis_store is None:
            self.redis_store = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                decode_responses=True
            )

    def stageType_to_redisPageType(self, stage_type:StageType):
        """ StageType To RedisPageType """
        if stage_type is StageType.READING:
            return RedisPageType.READY_READING
        if stage_type is StageType.LISTENING:
            return RedisPageType.READY_LISTENING
        if stage_type is StageType.WRITING:
            return RedisPageType.READY_WRITING
        if stage_type is StageType.SPEAKING:
            return RedisPageType.READY_SPEAKING
        return RedisPageType.CURRENT_STAGE


    async def save_user_state(self, page: str, key: str, state_data: str):
        """
            페이지:키 정보 이용 상태 정보 저장
        """
        if self.redis_store:
            await self.redis_store.set(
                f"{page}:{key}", 
                state_data,
                REDIS_EXPIRE_SECOND
            )

    async def load_user_state(self, page:str, key: str) -> str:
        """
            페이지:키 정보 이용 상태 정보 가져오기
        """
        if self.redis_store:
            data = await self.redis_store.get(f"{page}:{key}")
            if data:
                return data
        return "{}"
    
    async def save_progress_state(self, username: str, progress_data: ProgressResponse):
        """
            사용자 게임 진행 현황 정보를 저장용
        """
        logger.info(progress_data)
        await self.save_user_state(
            REDIS_PAGE_MAP[RedisPageType.CURRENT_STAGE],
            username,
            progress_data.model_dump_json()
        )
        # if StateStore.redis_store:
        #     await StateStore.redis_store.set(
        #         f"token:{username}",
        #         progress_data.model_dump_json(),
        #         REDIS_EXPIRE_SECOND
        #     )

    async def load_progress_state(self, username: str) -> Dict[str, Any]:
        """
            사용자 게임 진행 현황 정보 결과 저장용
        """
        logger.info(username)
        data = await self.load_user_state(
            REDIS_PAGE_MAP[RedisPageType.CURRENT_STAGE],
            username
        )
        return json.loads(data)
        # if StateStore.redis_store:
        #     data = await StateStore.redis_store.get(f"token:{username}")
        #     if data:
        #         return json.loads(data)
        # return {}
    
    async def save_ready_stage(self, stage_type:StageType, username: str, stage: str):
        """
            사용자 스테이지(쓰기, 말하기) 사전 작성 후 저장용
        """
        _page_type = self.stageType_to_redisPageType(stage_type)
        logger.info(stage)
        logger.info(f"{stage_type} / {_page_type}")
        await self.save_user_state(
            REDIS_PAGE_MAP[_page_type],
            username,
            stage
        )

    async def load_ready_stage(self, stage_type:StageType, username: str) -> Dict[str, Any]:
        """
            사용자 사전 작성 후 저장된 스테이지 정보 가져오기
        """
        _page_type = self.stageType_to_redisPageType(stage_type)
        logger.info(f"{username} / {stage_type} / {_page_type}")
        data = await self.load_user_state(
            REDIS_PAGE_MAP[_page_type],
            username
        )
        return json.loads(data)


class QueueStore:
    """
        SingleTon Redis Queue Class
        사용 : store = QueueStore(), store.enqueue...
    """
    _instance = None
    def __new__(cls, *args, **kwargs):
        ## instance 생성용
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls.queue_store = None
        return cls._instance
    
    def __init__(self) -> None:
        if self.queue_store is None:
            self.queue_store = Queue(
                REDIS_QUEUE_NAME,
                connection= Redis(
                        host=REDIS_HOST,
                        port=REDIS_PORT,
                        db=REDIS_DB
                    )
            )

    def enqueue(self, func, *args, **kwargs):
        """
            Add a task to the task queue
        """
        if self.queue_store:
            job = self.queue_store.enqueue(func, *args, **kwargs)
            return job
        return None    