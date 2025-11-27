# agent/judge/supervisor.py
import json
from langchain_core.messages import SystemMessage, HumanMessage
from .nodes.analysts import prompts
from .states import AssessmentState
from .logger import get_logger

logger = get_logger("Supervisor")

def supervisor_node(state: AssessmentState, llm) -> dict:
    """전체 흐름 제어 및 라우팅"""
    
    # [1] 현재 진행 상황 요약
    has_grammar = state.get("grammar_result") is not None
    has_context = state.get("context_result") is not None
    has_score = state.get("score_result") is not None
    has_feedback = state.get("final_feedback") is not None
    
    status = {
        "grammar": "DONE" if has_grammar else "WAITING",
        "context": "DONE" if has_context else "WAITING",
        "score": "DONE" if has_score else "WAITING",
        "feedback": "DONE" if has_feedback else "WAITING"
    }
    logger.info(f"현재 진행 상황: {status}")

    messages = [
        SystemMessage(content=prompts["supervisor_system"]),
        HumanMessage(content=f"Current Status: {json.dumps(status)}")
    ]
    
    # [2] LLM에게 판단 요청
    response = llm.invoke(messages)
    logger.debug(f"LLM 원본 응답: {response.content}")
    
    # [3] LLM 결정 파싱 및 에러 핸들링
    try:
        decision = json.loads(response.content)
        llm_decision = decision.get("next_worker", "FINISH")
    except:
        logger.warning("❌ LLM 응답 파싱 실패 (JSON 깨짐). 강제 로직을 따릅니다.")
        llm_decision = "ERROR" # 파싱 실패 시 임시 상태

    # [4] 🔥 하드 오버라이드 로직 (Supervisor의 핵심 역할)
    next_worker = llm_decision

    if not has_grammar:
        # 문법 분석이 안 끝났으면 무조건 문법 분석가로 보냄
        if next_worker != "linguist":
            logger.warning(f"LLM이 '{llm_decision}' 명령. 필수 단계 누락으로 'linguist'로 강제 전환.")
        next_worker = "linguist"
    elif not has_context:
        # 문법은 끝났고, 맥락 분석이 안 끝났으면 무조건 맥락 분석가로 보냄
        if next_worker != "context_analyst":
            logger.warning(f"LLM 명령 무시. 필수 단계 누락으로 'context_analyst'로 강제 전환.")
        next_worker = "context_analyst"
    elif not has_score:
        # 분석은 끝났고, 평가가 안 끝났으면 무조건 평가자로 보냄
        next_worker = "evaluator"
    elif not has_feedback:
        # 평가까지 끝났고, 피드백이 없으면 무조건 튜터로 보냄
        next_worker = "tutor"
    else:
        # 모든 게 끝났으면 최종 종료
        next_worker = "FINISH"
        
    logger.info(f"➡️ 다음 작업자 결정: {next_worker}")
    return {"next_worker": next_worker}