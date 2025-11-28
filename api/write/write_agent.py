import os
import json
from typing import Dict, Any

# Langchain 관련 임포트
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import AgentExecutor
from langchain.agents.format_scratchpad import format_to_openai_function_messages
from langchain.agents.output_parsers import OpenAIFunctionsAgentOutputParser

# [중요] DB 데이터 가져오기
# 상위 폴더(db)에 있는 interview_data.py를 import 합니다.
# 만약 파일명이 다르다면 맞춰주세요 (예: db.interview_db)

try:
    from db.inteview_data import INTERVIEW_DB
except ImportError:
    # 경로 에러 방지를 위한 예외처리 (서버 실행 위치에 따라 다를 수 있음)
    import sys

    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from db.interview_data import INTERVIEW_DB


# 1. [TOOL] 검색 도구 (한글 설명)
@tool
def search_interview_question(intent_keyword: str):
    """
    사용자의 답변에서 파악된 "핵심의도 키워드(영어)"를 기반으로,
    DB에서 가장 연관성 높은 인터뷰 질문 데이터를 검색하여 반환합니다.
    한국어 번역문이나 원본 질문 ID를 찾을 때 사용합ㄴ디ㅏ.

    Args:
        intent_keyword (str): 사용자 답변과 관련된 간단한 영어 키워드 (예: 'job', 'food', 'name').
    """
    keyword_lower = intent_keyword.lower()

    for item in INTERVIEW_DB:
        if keyword_lower in item["keyword"]:
            return item

    return {"error": "DB에서 일치하는 질문을 찾을 수 없습니다."}


# 2. [Class] 에이전트 클래스
class WriteAgnet:
    def __init__(self):
        # API 키 확인
        if "OPEN_API_KEY" not in os.environ:
            print("[WriteAgent] Warning: OPENAI_API_KEY is not set.")

        self.agent_executor = self._create_agent_executor()

    def _create_agent_executor(self) -> AgentExecutor:
        # 1. 모델 설정 (gpt-4o 권장)
        llm = ChatOpenAI(model="gpt-4o", temperature=0)

        # 2. 툴 바인딩
        tools = [search_interview_question]
        llm_with_tools = llm.bind_functions(tools)

        # 3. 시스템 프롬프트 (한글)
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """
            당신은 'Klingo 브릿지 에이전트'입니다. 
            당신의 임무는 사용자의 영어 답변을 분석하여, 한국어 쓰기 학습 가이드를 제공하는 것입니다.
             
            [처리 과정]
            1. 사용자의 입력(영어)을 분석하여 핵심 주제(의도)를 파악하세요.
            2. 'search_interview_question' 도구를 사용하여 DB에서 관련 질문 데이터를 찾으세요.
            3. 도구의 검색 결과와 사용자의 답변을 바탕으로, 언리얼 엔진에 보낼 JSON 데이터를 생성하세요.
             
            [출력 JSON 형식]
            반드시 아래 구조를 가진 유효한 JSON 문자열만 반환해야 합니다:
            {{
                "status": "success",
                "matched_id": <정수형, 도구에서 찾은 index>,
                "korean_question": <문자열, 도구에서 찾은 한국어 질문>,
                "user_answer_summary": <문자열, 사용자 영어 답변 요약>,
                "learning_guide": {{
                    "easy": <문자열, 따라 쓰기 쉬운 한국어 단어 혹은 짧은 구>,
                    "normal": <문자열, '요'나 '니다'로 끝나는 정중한 한국어 문장>,
                    "hard": <문자열, 구체적이고 유창한 한국어 문장>
                }}
            }}
            
            만약 도구 검색에 실패하거나 에러가 발생하면 "status"를 "fail"로, "matched_id"는 -1로 설정하세요.
            """,
                ),
                ("user", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )

        # 4. 파이프라인 구성
        agent = (
            {
                "input": lambda x: x["input"],
                "agent_scratchpad": lambda x: format_to_openai_function_messages(
                    x["intermediate_steps"]
                ),
            }
            | prompt
            | llm_with_tools
            | OpenAIFunctionsAgentOutputParser()
        )

        return AgentExecutor(agent=agent, tools=tools, verbose=True)


async def generate_guide(self, user_answer: str) -> Dict[str, Any]:
    """
    사용자의 답변을 받아 가이드를 생성합니다. (비동기 호출)
    """
    try:
        # 에이전트 실행
        result = await self.agent_executor.ainvoke({"input": user_answer})

        # JSON 파싱 및 반환
        output = result["output"]
        if isinstance(output, str):
            return json.loads(output)
        return output

    except Exception as e:
        print(f"Agent Error: {e}")
        return {
            "status": "error",
            "message": str(e),
            "matched_id": -1,
            "learning_guide": {},
        }
