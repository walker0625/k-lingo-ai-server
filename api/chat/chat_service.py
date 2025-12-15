import os
import logging
from typing import List, Dict

from openai import OpenAI, APIConnectionError, APITimeoutError
import ollama

# 로깅 설정
logger = logging.getLogger(__name__)

class ChatService:
    
    def __init__(self):
        # ---------------------------------------------------------
        # 1. vLLM 설정 (Primary)
        # ---------------------------------------------------------
        self.vllm_host = os.getenv("VLLM_HOST", "localhost")
        self.vllm_port = os.getenv("VLLM_PORT", "8200")
        self.vllm_base_url = f"http://{self.vllm_host}:{self.vllm_port}/v1"
        
        # vLLM 모델명
        self.vllm_model_name = "Qwen/Qwen2.5-7B-Instruct-AWQ"
        
        logger.info(f"Connecting to vLLM Server: {self.vllm_base_url}")
        
        # vLLM용 클라이언트 초기화 (타임아웃 설정 권장)
        self.vllm_client = OpenAI(
            base_url=self.vllm_base_url,
            api_key="EMPTY",  # vLLM은 보통 키가 필요 없음
            timeout=5.0      # 5초 내 응답 없으면 Ollama로 전환
        )

        # ---------------------------------------------------------
        # 2. Ollama 설정 (Fallback)
        # ---------------------------------------------------------
        # Ollama 모델명
        self.ollama_model_name = "qwen2:7b-instruct"

    def ask_question(self, context: str, user_prompt: str) -> str:
        
        """
        vLLM에 먼저 요청을 보내고, 실패 시 Ollama로 재요청합니다.
        """
        # 1. 프롬프트 메시지 구성 (시스템 프롬프트 + 유저 질문)
        messages = self._build_messages(context, user_prompt)

        try:
            # 2. vLLM 시도
            return self._request_vllm(messages)

        except (APIConnectionError, APITimeoutError, Exception) as e:
            # 3. 실패 시 에러 로깅 후 Ollama로 전환
            logger.warning(f"vLLM request failed ({type(e).__name__}): {e}")
            logger.warning("Switching to fallback provider: Ollama...")
            
            try:
                # 4. Ollama 시도
                return self._request_ollama(messages)
            except Exception as ollama_e:
                # 둘 다 실패한 경우
                logger.error(f"Both vLLM and Ollama failed. Final error: {ollama_e}")
                raise ollama_e

    def _build_messages(self, context: str, user_prompt: str) -> List[Dict[str, str]]:
        
        """
        시스템 프롬프트와 컨텍스트를 조합하여 메시지 리스트를 생성합니다.
        """
        system_instruction = (
            "당신은 'K-Lingo'입니다. 당신은 유능하고 친절한 AI 사고 파트너이며, "
            "한국어 튜터이자 게임 가이드 역할을 수행합니다.\n"
            "사용자의 질문에 대해 공감하고 통찰력 있게 답변하세요.\n"
            "답변 시 다음 규칙을 따르세요:\n"
            "1. 제공된 [Game Context]를 바탕으로 게임 내 정보를 정확히 설명하세요.\n"
            "2. 한국어 학습에 도움이 되는 표현이 있다면 자연스럽게 설명에 녹여내세요.\n"
            "3. 답변은 가독성 있게 서식(볼드체, 리스트 등)을 활용하세요.\n"
            "4. 답변 끝에는 사용자가 할 수 있는 다음 행동(Next step)을 제안하세요."
            "5. 모든 응답은 영어로 제공해주세요"
        )

        # 컨텍스트와 유저 질문을 결합 (RAG 패턴)
        full_user_content = f"""
        [Game Context]
        {context}

        [User Question]
        {user_prompt}
        """

        return [
            {'role': 'system', 'content': system_instruction},
            {'role': 'user', 'content': full_user_content}
        ]

    def _request_vllm(self, messages: List[Dict[str, str]]) -> str:
        
        """vLLM 서버로 요청"""
        response = self.vllm_client.chat.completions.create(
            model=self.vllm_model_name,
            messages=messages,
            temperature=0.7,
            max_tokens=512
        )
        
        return response.choices[0].message.content

    def _request_ollama(self, messages: List[Dict[str, str]]) -> str:
        
        """Ollama 로컬로 요청"""
        response = ollama.chat(
            model=self.ollama_model_name,
            messages=messages
        )
        
        return response['message']['content']