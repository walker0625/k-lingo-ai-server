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

# [중요] MCP 도구 파일이 존재해야 합니다 (app/mcp_tools/brave_search.py)
from mcp_tools.brave_search import BraveSearchTool

# 로깅 설정
logger = logging.getLogger(__name__)

class ChatService:
    
    _asr_pipeline = None 
    
    def __init__(self):
        
        # 1. STT 설정 (Lazy Loading을 위해 초기화는 _get_pipeline에서 수행)
        self.pipe = self._get_pipeline()
        
        # ---------------------------------------------------------
        # 2. vLLM 설정 (Primary Provider)
        # ---------------------------------------------------------
        self.vllm_host = os.getenv("VLLM_HOST", "localhost")
        self.vllm_port = os.getenv("VLLM_PORT", "8200")
        self.vllm_base_url = f"http://{self.vllm_host}:{self.vllm_port}/v1"
        
        # [기본 모델] LoRA 레벨이 지정되지 않았거나 오류 발생 시 사용할 베이스 모델
        self.base_model_name = "Qwen/Qwen2.5-7B-Instruct-AWQ"
        
        logger.info(f"Connecting to vLLM Server: {self.vllm_base_url}")
        
        # vLLM용 클라이언트 초기화
        # [주의] 검색 등 도구 실행 시간을 고려하여 timeout을 20초 이상으로 넉넉히 설정
        self.vllm_client = OpenAI(
            base_url=self.vllm_base_url,
            api_key="EMPTY",
            timeout=20.0 
        )

        # ---------------------------------------------------------
        # 3. Ollama 설정 (Fallback Provider)
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
        """Whisper 모델을 메모리에 한 번만 로드하기 위한 싱글톤 메서드"""
        if cls._asr_pipeline is None:
            from transformers import pipeline
            import torch
            try:
                device = "cuda:0" if torch.cuda.is_available() else "cpu"
                logger.info(f"ASR Pipeline Device set to: {device} (Lazy Load)")
                
                cls._asr_pipeline = pipeline(
                    "automatic-speech-recognition", 
                    model="seastar105/whisper-small-komixv2",
                    device=device 
                )
                logger.info("ASR Pipeline successfully loaded.")
            except Exception as e:
                logger.error(f"FATAL ASR LOAD ERROR: {e}")
                raise HTTPException(status_code=503, detail="AI 서비스 초기화 실패")

        return cls._asr_pipeline
    
    def _get_tool_schemas(self) -> List[Dict]:
        """등록된 도구들의 명세서(JSON Schema)를 리스트로 반환"""
        return [tool.get_schema() for tool in self.available_mcp_tools.values()]

    def _get_model_by_level(self, level: int) -> str:
        """
        사용자 레벨(int)을 vLLM의 모델명(str)으로 변환합니다.
        vLLM 실행 시 --lora-modules level1=..., level2=... 로 설정한 이름과 일치해야 합니다.
        """
        if level == 1:
            return "level1"
        elif level == 2:
            return "level2"
        elif level == 3:
            return "level3"
        else:
            logger.warning(f"Invalid level '{level}'. Falling back to base model.")
            return self.base_model_name

    def ask_question(self, session: SessionDep, user: User, context: str, question: str, audio: UploadFile, level: int) -> str:
        
        # 0. 사용할 모델 결정 (Dynamic Routing)
        target_model = self._get_model_by_level(level)
        logger.info(f"▶ Processing Request with Model: {target_model} (Level: {level})")

        # -----------------------------------------------------
        # A. 오디오 처리 (STT)
        # -----------------------------------------------------
        if question is None:
            file_name = 'chat_' + str(uuid.uuid4()) + '.wav'
            file_path = os.path.join(INPUT_DIR, file_name)

            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(audio.file, buffer)

            audio_array, sampling_rate = sf.read(file_path)
            # audio_duration = len(audio_array) / sampling_rate # 필요시 사용
            
            result = self.pipe(audio_array)
            question = result['text']
            logger.info(f"STT Result: {question}")
        
        # -----------------------------------------------------
        # B. 히스토리 조회 및 저장 (RAG/Memory)
        # -----------------------------------------------------
        history = self.retrieve_similar_history(session, user.username, question)    
        self.save_chat(session, user, question)
        
        # -----------------------------------------------------
        # C. LLM 추론 및 도구 실행 루프
        # -----------------------------------------------------
        messages = self._build_messages(context, history, question)
        tools = self._get_tool_schemas() 

        try:
            # 1. vLLM 1차 요청 (질문 + 도구 목록 전달)
            # [핵심] model=target_model을 사용하여 파인튜닝된 어댑터를 호출
            response = self.vllm_client.chat.completions.create(
                model=target_model,  
                messages=messages,
                tools=tools,
                tool_choice="auto", # 모델이 판단하여 도구 사용
                temperature=0.1,
                max_tokens=512
            )
            
            response_message = response.choices[0].message
            tool_calls = response_message.tool_calls

            logger.warning(f"🧩 LLM Tool Usage Ready: {len(tool_calls)} calls")

            # 2. 모델이 도구 사용을 결정했는지 확인
            if tool_calls:
                
                # 대화 문맥 유지를 위해 AI의 '도구 호출 의도'를 히스토리에 추가
                messages.append(response_message)

                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    # 실제 도구 실행 (MCP 패턴)
                    if function_name in self.available_mcp_tools:
                        tool_instance = self.available_mcp_tools[function_name]
                        
                        logger.info(f"Executing Tool: {function_name} with args: {function_args}")
                        function_response = tool_instance.run(**function_args)
                        
                        # 실행 결과를 메시지에 추가 (Role: tool)
                        messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": function_response,
                        })
                    else:
                        logger.warning(f"Unknown tool called: {function_name}")


                # 3. vLLM 2차 요청 (최종 답변 생성)
                # [핵심] 도구 실행 결과가 포함된 messages를 다시 보냄
                final_response = self.vllm_client.chat.completions.create(
                    model=target_model, 
                    messages=messages,
                    temperature=0.1,
                    max_tokens=512
                )
                
                answer = final_response.choices[0].message.content
                
                return ChatResponse(question=question, answer=answer)

            else:
                
                # 4. 도구 사용이 필요 없는 경우 (바로 답변 반환)
                return ChatResponse(question=question, answer=response_message.content)

        except (APIConnectionError, APITimeoutError, Exception) as e:
            # 5. vLLM 실패 시 Ollama로 전환 (Fallback)
            logger.error(f"vLLM({target_model}) Error: {e}")
            logger.warning("⚠️ Switching to fallback provider: Ollama...")
            
            try:
                # Ollama는 도구 없이 텍스트 대화만 수행
                return ChatResponse(question=question, answer=self._request_ollama(messages))
            except Exception as ollama_e:
                logger.critical(f"All providers failed. Error: {ollama_e}")
                raise ollama_e

    def _build_messages(self, context: str, history: str, question: str) -> List[Dict[str, str]]:
        """
        시스템 프롬프트 구성: 도구 사용 유도와 페르소나 정의
        """
        system_instruction = (
            "# Role Definition\n"
            "당신은 'K-Lingo'입니다. 당신의 역할은 두 가지 모드로 나뉩니다:\n"
            "1. **Language Tutor Mode (기본)**: 한국어 표현, 문법, 번역 요청 시 작동.\n"
            "2. **Information Agent Mode (특수)**: 날씨, 뉴스, 환율 등 실시간 정보 요청 시 작동.\n\n"
            
            "### **[긴급] 도구 호출 포맷 규칙 (엄격 준수)**\n"
            "도구(web_search)를 사용해야 한다면, **절대** '제가 찾아보겠습니다', '잠시만요'와 같은 서론이나 생각(Thought)을 텍스트로 출력하지 마십시오.\n"
            "**반드시 응답의 맨 첫 글자부터 도구 호출 구문(JSON 등)이 시작되어야 합니다.**\n"
            "- ❌ 잘못된 예: '서울 날씨를 검색해 볼게요... <tool_call>...'\n"
            "- ✅ 올바른 예: <tool_call>{\"name\": \"web_search\", ...}</tool_call>\n\n"
            
            "사용자의 질문을 분석하여 다음 로직에 따라 행동하십시오:\n"
            
            "**CASE A: 실시간 정보가 필요한 경우 (Real-time Info)**\n"
            "- 조건: 질문에 '오늘', '지금', '날씨', '뉴스', '주가', '환율', '점수', '최신' 등의 시의성 키워드가 포함되거나 팩트 체크가 필요한 경우.\n"
            "- 행동: **아는 척하거나 기억에 의존해 대답하지 마십시오.** 즉시 `web_search` 도구를 호출하십시오.\n\n"
            
            "**CASE B: 언어 학습 질문인 경우 (Language Learning)**\n"
            "- 조건: '이거 한국어로 뭐야?', '문법 고쳐줘', '무슨 뜻이야?' 등의 질문.\n"
            "- 행동: 검색 없이 당신의 지식으로 답변하십시오.\n\n"
            
            "### **답변 생성 가이드라인 (도구 미사용 시)**\n"
            "도구 사용이 필요 없는 경우, 다음의 **강력한 규칙**을 따르세요:\n"
            "1. **영어 사용 필수**: 모든 응답은 **영어(English)**로 작성하세요. (중국어/한자 절대 금지)\n"
            "2. **인사말 금지**: 'Hello', 'I can help you'와 같은 의례적인 서두를 생략하고 바로 본론으로 시작하세요.\n"
            "3. **[Chat History] 연결**: 답변의 첫 문장은 반드시 이전 대화 내용(History)을 언급하며 시작하세요. "
            "(예: 'Based on your previous question about...', 'As we discussed earlier...')\n"
            "4. **전문적 피드백**: [Game Context]와 [Chat History]를 결합하여 사용자의 한국어 학습 상태에 대해 날카롭고 구체적인 피드백을 제공하세요.\n"
            "5. **간결성 유지**: 가독성을 위해 볼드체를 사용하되, 전체 길이는 **반드시 100자(characters) 이내**로 줄여서 작성하세요."
            
            "### **Examples (Follow these patterns strictly)**\n"
            "User: 오늘 서울 날씨 알려줘\n"
            "Assistant: <tool_call>{\"name\": \"web_search\", \"arguments\": {\"query\": \"Seoul weather today\"}}</tool_call>\n\n"
            "User: 사과가 영어로 뭐야?\n"
            "Assistant: 사과는 영어로 'Apple'입니다.\n\n"
            "User: 삼성전자 주가 얼마야?\n"
            "Assistant: <tool_call>{\"name\": \"web_search\", \"arguments\": {\"query\": \"Samsung Electronics stock price\"}}</tool_call>\n"
        )

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

    def _request_ollama(self, messages: List[Dict[str, str]]) -> str:
        """Ollama 로컬로 요청 (Fallback용)"""
        response = ollama.chat(
            model=self.ollama_model_name,
            messages=messages
        )
        return response['message']['content']
    
    def save_chat(self, session, user, question):
        try:
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
        except Exception as e:
            logger.error(f"Chat save failed: {e}")
        
    def retrieve_similar_history(self, session: SessionDep, username: str, question: str) -> str:
        try:
            response = openai.embeddings.create(
                input=question,
                model="text-embedding-3-small"
            )
            query_vector = response.data[0].embedding

            statement = (
                select(ChatHistory)
                .join(User, ChatHistory.user_id == User.id)
                .where(User.username == username)
                .order_by(ChatHistory.embedding.cosine_distance(query_vector))
                .limit(3)
            )
            
            results = session.exec(statement).all()

            history = ""
            for chat in results:
                history += f"User: {chat.question}\n"
            
            return history
        except Exception as e:
            logger.error(f"Failed to retrieve chat history: {e}")
            return ""