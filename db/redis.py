import os, json
import redis.asyncio as redis
from typing import Dict, Any
from db.model.progress import ProgressResponse
from loguru import logger

REDIS_HOST = os.environ["REDIS_HOST"]
REDIS_PORT = int(os.environ["REDIS_PORT"])
class StateStore:
    """
        SingleTon Redis Service Class
        사용 : store = StateStore(), store.save_...
    """
    _instance = None
    redis_store: redis.Redis | None = None
    def __new__(cls, *args, **kwargs):
        ## instance 생성용
        if cls.redis_store is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        if StateStore.redis_store is None:
            StateStore.redis_store = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                decode_responses=True
            )

    async def save_user_state(self, token: str, state_data: Dict[str, Any]):
        """
            사용자 게임 진행 현황 정보를 저장하기 위해
        """
        if StateStore.redis_store:
            await StateStore.redis_store.set(f"token:{token}", json.dumps(state_data))

    async def load_user_state(self, token: str) -> Dict[str, Any]:
        """
            토큰 정보를 이용 저장된 정보 가져오기
        """
        if StateStore.redis_store:
            data = await StateStore.redis_store.get(f"token:{token}")
            if data:
                return json.loads(data)
        return {}
    
    async def save_progress_state(self, username: str, progress_data: ProgressResponse):
        """
            사용자 게임 진행 현황 정보를 저장하기 위해
        """
        logger.info(progress_data)
        if StateStore.redis_store:
            await StateStore.redis_store.set(f"token:{username}", progress_data.model_dump_json())

    async def load_progress_state(self, username: str) -> Dict[str, Any]:
        """
            토큰 정보를 이용 저장된 정보 가져오기
        """
        if StateStore.redis_store:
            data = await StateStore.redis_store.get(f"token:{username}")
            if data:
                return json.loads(data)
        return {}