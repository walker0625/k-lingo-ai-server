import os
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

class ChatService:
    
    def __init__(self):
        # 1. 환경 변수에서 vLLM 서버 주소를 가져옵니다. (없으면 기본값 localhost 사용)
        vllm_host = os.getenv("VLLM_HOST", "localhost")
        vllm_port = os.getenv("VLLM_PORT", "8200")
        base_url = f"http://{vllm_host}:{vllm_port}/v1"
        
        logger.info(f"Connecting to vLLM Server: {base_url}")

        self.client = OpenAI(
            base_url=base_url,
            api_key="EMPTY"  # vLLM은 기본적으로 키 검사를 안 하므로 EMPTY 유지
        )
        self.model_name = "Qwen/Qwen2.5-7B-Instruct-AWQ"

    def ask_question(self, system_prompt: str, user_prompt: str) -> str:
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt}
                ],
                temperature=0.7,
                max_tokens=512
            )
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"vLLM 요청 실패 (서버: {self.client.base_url}): {e}")
            raise e