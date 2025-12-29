import os
import logging
import uuid
import shutil
import soundfile as sf
import json 

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

from mcp_tools.brave_search import BraveSearchTool

# 로깅 설정
logger = logging.getLogger(__name__)

class ChatService:
    
    _asr_pipeline = None 
    
    def __init__(self):
        
        # 1. STT 설정
        self.pipe = self._get_pipeline()
        
        # ---------------------------------------------------------
        # 2. vLLM 설정 (Primary)
        # ---------------------------------------------------------
        self.vllm_host = os.getenv("VLLM_HOST", "localhost")
        self.vllm_port = os.getenv("VLLM_PORT", "8200")
        self.vllm_base_url = f"http://{self.vllm_host}:{self.vllm_port}/v1"
        
        # vLLM 사용 모델명
        self.vllm_model_name = "Qwen/Qwen2.5-7B-Instruct-AWQ"
        
        logger.info(f"Connecting to vLLM Server: {self.vllm_base_url}")
        
        # vLLM용 클라이언트 초기화 (타임아웃 설정 권장)
        self.vllm_client = OpenAI(
            base_url=self.vllm_base_url,
            api_key="EMPTY",  # vLLM은 보통 키가 필요 없음
            timeout=20.0      # [수정] 검색 대기 시간을 고려해 타임아웃을 넉넉히 설정
        )

        # ---------------------------------------------------------
        # 3. Ollama 설정 (Fallback)
        # ---------------------------------------------------------
        self.ollama_model_name = "qwen2:7b-instruct"
        
        # ------------------------------------------------------------------
        # 4. MCP 도구 등록 (Dependency Injection)
        # ------------------------------------------------------------------
        self.available_mcp_tools = {
            "web_search": BraveSearchTool() 
        }
        
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
    
    def _get_tool_schemas(self) -> List[Dict]:
        return [tool.get_schema() for tool in self.available_mcp_tools.values()]

    def ask_question(self, session: SessionDep, user: User, context: str, question: str, audio: UploadFile, level: int) -> str:
        
        # -----------------------------------------------------
        # A. 오디오 처리 (STT)
        # -----------------------------------------------------
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

            # 💡 싱글톤 self.pipe 사용
            result = self.pipe(audio_array)
            question = result['text']
        
        # -----------------------------------------------------
        # B. 히스토리 조회 및 저장 (RAG/Memory)
        # -----------------------------------------------------
        history = self.retrieve_similar_history(session, user.username, question)    
        self.save_chat(session, user, question)
        
        # -----------------------------------------------------
        # C. LLM 추론 및 도구 실행 루프
        # -----------------------------------------------------
        # 1. 초기 메시지 및 도구 스키마 준비
        messages = self._build_messages(context, history, question)
        tools = self._get_tool_schemas() # 동적으로 스키마 가져오기

        try:
            # 2. vLLM에 1차 요청 (질문 + 도구 목록 전달)
            response = self.vllm_client.chat.completions.create(
                model=self.vllm_model_name,
                messages=messages,
                tools=tools,
                tool_choice="auto", # [핵심] 모델이 도구 사용 여부를 스스로 판단 (required로 하면 무조건 tool 사용)
                temperature=0.7,
                max_tokens=512
            )
            
            response_message = response.choices[0].message
            tool_calls = response_message.tool_calls

            logger.warning(f"LLM이 도구 사용을 시도했는지 확인: {len(tool_calls)}건")
            
            # 3. 모델이 "도구를 써야해!"라고 판단했는지 확인
            if tool_calls:
                logger.warning(f"LLM이 도구 사용을 요청했습니다: {len(tool_calls)}건")
                
                # (중요) 대화 흐름 유지를 위해 모델의 '도구 호출 의도'를 히스토리에 추가
                messages.append(response_message)

                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    # [MCP 패턴] 문자열 이름으로 실제 도구 객체를 찾아 실행
                    if function_name in self.available_mcp_tools:
                        tool_instance = self.available_mcp_tools[function_name]
                        
                        # 도구 실행 (Brave API 호출 등)
                        function_response = tool_instance.run(**function_args)
                        
                        logger.warning(function_response)
                        
                        # 실행 결과(검색 내용)를 대화 내역에 추가 (Role: tool)
                        messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": function_response,
                        })
                    else:
                        logger.warning(f"알 수 없는 도구 호출: {function_name}")

                # 4. 도구 실행 결과를 포함하여 vLLM에 2차 요청 (최종 답변 생성)
                final_response = self.vllm_client.chat.completions.create(
                    model=self.vllm_model_name,
                    messages=messages, # 이제 여기엔 검색 결과가 포함되어 있음
                    temperature=0.7,
                    max_tokens=512
                )
                
                answer = final_response.choices[0].message.content
                
                return ChatResponse(question=question, answer=answer)

            else:
                # 5. 도구 사용이 필요 없는 경우 (일반 대화)
                return ChatResponse(question=question, answer=response_message.content)

        except (APIConnectionError, APITimeoutError, Exception) as e:
            # 6. 실패 시 에러 로깅 후 Ollama로 전환 (Fallback)
            logger.warning(f"vLLM request failed ({type(e).__name__}): {e}")
            logger.warning("Switching to fallback provider: Ollama...")
            
            try:
                # Ollama는 도구 없이 기본 답변만 수행 (복잡성 최소화)
                return ChatResponse(question=question, answer=self._request_ollama(messages))
            except Exception as ollama_e:
                logger.error(f"Both vLLM and Ollama failed. Final error: {ollama_e}")
                raise ollama_e

    def _build_messages(self, context: str, history: str, question: str) -> List[Dict[str, str]]:
        
        """
        시스템 프롬프트와 컨텍스트를 조합하여 메시지 리스트를 생성합니다.
        """
        system_instruction = (
            # 역할을 너무 한국어 튜터로 한정 지으면 tool 사용을 잘 하지 않아서 페르소나 유연하게 변경
            "# 역할\n"
            "당신은 한국어 학습자를 위한 스마트 AI 비서 'K-Lingo'입니다.(tutor + tool)\n\n"
            
            "### **[중요] 도구 사용 규칙 (최우선 순위)**\n"
            "답변을 생성하기 **전**, 사용자의 질문을 먼저 분석하십시오:\n"
            "- 사용자가 **실시간 정보**(예: 날씨, 뉴스, 주가, 최신 사건 등)를 요청하면, **반드시** `web_search` 도구를 즉시 사용하십시오.\n"
            "- 실시간 주제에 대해 당신의 학습된 기억(Training Memory)에 의존하여 대답하지 마십시오.\n"
            "- 예시: 사용자가 '서울 날씨 어때?'라고 묻는다면, 즉시 `web_search(query='current weather in Seoul')`을 호출하세요.\n\n"
            
            "### **답변 생성 가이드라인 (도구 미사용 시)**\n"
            "도구 사용이 필요 없는 경우, 다음의 **강력한 규칙**을 따르세요:\n"
            "1. **영어 사용 필수**: 모든 응답은 **영어(English)**로 작성하세요. (중국어/한자 절대 금지)\n"
            "2. **인사말 금지**: 'Hello', 'I can help you'와 같은 의례적인 서두를 생략하고 바로 본론으로 시작하세요.\n"
            "3. **[Chat History] 연결**: 답변의 첫 문장은 반드시 이전 대화 내용(History)을 언급하며 시작하세요. "
            "(예: 'Based on your previous question about...', 'As we discussed earlier...')\n"
            "4. **전문적 피드백**: [Game Context]와 [Chat History]를 결합하여 사용자의 한국어 학습 상태에 대해 날카롭고 구체적인 피드백을 제공하세요.\n"
            "5. **간결성 유지**: 가독성을 위해 볼드체를 사용하되, 전체 길이는 **반드시 100자(characters) 이내**로 줄여서 작성하세요."
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
        """
        단순 텍스트 요청용 메서드 (ask_question 내부 로직과 별도로 필요할 때 사용 - 현재 미사용)
        """
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