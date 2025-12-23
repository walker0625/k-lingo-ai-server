import os
import logging
import uuid
import shutil
import soundfile as sf

from common.path import INPUT_DIR
from typing import List, Dict

from db.session import SessionDep

from db.model.user import User
from db.model.chat_history import ChatHistory

from api.chat.dto.chat_dto import ChatResponse

from sqlmodel import select

import openai
from fastapi import UploadFile, HTTPException
from openai import OpenAI, APIConnectionError, APITimeoutError
import ollama

# 로깅 설정
logger = logging.getLogger(__name__)

class ChatService:
    
    _asr_pipeline = None 
    
    def __init__(self):
        
        # STT 설정
        self.pipe = self._get_pipeline()
        
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
        
    @classmethod
    def _get_pipeline(cls):
        if cls._asr_pipeline is None:
            
            # 💡 모델 로딩이 필요한 시점에야 import 실행 (Lazy Loading)
            from transformers import pipeline
            import torch
            
            try:
                # 💡 GPU 사용 여부 확인 및 장치 설정
                device = "cuda:0" if torch.cuda.is_available() else "cpu"
                logger.info(f"ASR Pipeline Device set to: {device} (Lazy Load)")
                
                # 모델 초기화
                cls._asr_pipeline = pipeline(
                    "automatic-speech-recognition", 
                    model="seastar105/whisper-small-komixv2",
                    device=device 
                )
                
                logger.info("ASR Pipeline successfully loaded.")
            except Exception as e:
                logger.error(f"FATAL ASR LOAD ERROR during lazy load: {e}")
                raise HTTPException(status_code=503, detail="AI 서비스 초기화 실패")

        return cls._asr_pipeline

    def ask_question(self, session: SessionDep, user: User, context: str, question: str, audio: UploadFile) -> str:
        
        if question is None:
        
            file_name = 'chat_' + str(uuid.uuid4()) + '.wav'
            file_path = os.path.join(INPUT_DIR, file_name)

            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(audio.file, buffer)

            # soundfile로 오디오 로드
            audio_array, sampling_rate = sf.read(file_path)

            # 오디오 시간 계산
            audio_duration = len(audio_array) / sampling_rate

            logger.info(f"오디오 처리 중: {audio_duration:.2f}초")

            # 💡 싱글톤 self.pipe 사용 (이미 __init__에서 할당됨)
            result = self.pipe(audio_array)
            question = result['text']
        
        history = self.retrieve_similar_history(session, user.username, question)    
        
        self.save_chat(session, user, question)
        
        """
        vLLM에 먼저 요청을 보내고, 실패 시 Ollama로 재요청합니다.
        """
        # 1. 프롬프트 메시지 구성 (시스템 프롬프트 + 유저 질문)
        messages = self._build_messages(context, history, question)

        try:
            # 2. vLLM 시도
            return ChatResponse(question=question, answer=self._request_vllm(messages))

        except (APIConnectionError, APITimeoutError, Exception) as e:
            # 3. 실패 시 에러 로깅 후 Ollama로 전환
            logger.warning(f"vLLM request failed ({type(e).__name__}): {e}")
            logger.warning("Switching to fallback provider: Ollama...")
            
            try:
                # 4. Ollama 시도
                return ChatResponse(question=question, answer=self._request_ollama(messages))
            except Exception as ollama_e:
                # 둘 다 실패한 경우
                logger.error(f"Both vLLM and Ollama failed. Final error: {ollama_e}")
                raise ollama_e

    def _build_messages(self, context: str, history: str, question: str) -> List[Dict[str, str]]:
        
        """
        시스템 프롬프트와 컨텍스트를 조합하여 메시지 리스트를 생성합니다.
        """
        system_instruction = (
            "당신은 'K-Lingo'의 핵심 지식 엔진입니다. 불필요한 인사말(Hello, Hi 등)이나 "
            "의례적인 문장은 **절대 사용하지 마세요.** 질문을 받자마자 본론으로 시작하십시오.\n\n"
            
            "답변 시 다음의 **강력한 규칙**을 따르세요:\n"
            "1. **인사말 금지**: 'Hello', ' assist you'와 같은 도입부를 생략하고 바로 피드백이나 정보를 제공하세요.\n"
            "2. **[Chat History] 중심 답변**: 답변의 첫 문장은 반드시 이전 대화 내용(History)을 언급하며 시작하세요. "
            "(예: 'Based on your previous question about...', 'As we discussed earlier regarding...') "
            "이전 기록을 인용하여 현재 질문과 어떻게 연결되는지 명확히 밝히세요.\n"
            "3. **전문적 피드백**: [Game Context]와 [Chat History]를 결합하여 사용자의 한국어 학습 상태에 대한 "
            "날카롭고 구체적인 피드백을 제공하세요.\n"
            "4. **가독성 극대화**: 본론만 전달하되, 볼드체와 리스트를 사용하여 정보를 구조화하세요.\n"
            "5. 모든 응답은 **영어(English)**로 작성하세요.(중국어/한자 절대 금지)\n"
            "6. 응답의 전체 길이는 **반드시 100자 이내**로 줄여서 간결하게 작성 해주세요"
        )

        # 컨텍스트와 유저 질문을 결합 (RAG 패턴)
        full_user_content = f"""
        [Game Context]
        {context}
        
        [Chat History]
        {history}

        [User Question]
        {question}
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
    
    def save_chat(self, session, user, question):
        
        response = openai.embeddings.create(
            input=question,
            model="text-embedding-3-small"
        )
        vector_data = response.data[0].embedding 

        chat = ChatHistory(
            user_id=user.id,
            question=question,
            embedding=vector_data
        )
        session.add(chat)
        session.commit()
        
    def retrieve_similar_history(self, session: SessionDep, username: str, question: str) -> str:
        """
        사용자의 과거 대화 중 현재 질문과 가장 유사한 3개를 조회하여 문자열로 반환합니다.
        """
        try:
            # 1. 현재 질문의 임베딩 벡터 생성
            response = openai.embeddings.create(
                input=question,
                model="text-embedding-3-small"
            )
            query_vector = response.data[0].embedding

            # 2. DB 조회 쿼리 작성
            # pgvector의 cosine_distance를 사용하여 유사도 정렬
            statement = (
                select(ChatHistory)
                .join(User, ChatHistory.user_id == User.id)
                .where(User.username == username)
                .order_by(ChatHistory.embedding.cosine_distance(query_vector))
                .limit(3)
            )
            
            results = session.exec(statement).all()

            # 3. LLM 프롬프트에 넣기 좋은 형태(문자열)로 변환
            history = ""
            
            for chat in results:
                history += f"User: {chat.question}\n"
            
            return history

        except Exception as e:
            logger.error(f"Failed to retrieve chat history: {e}")
            return ""