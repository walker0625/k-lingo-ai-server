# agent/judge/supervisor.py
import json
from langchain_core.messages import SystemMessage, HumanMessage
from .nodes.analysts import prompts
from .states import AssessmentState
from .logger import get_logger

logger = get_logger("Supervisor")

def supervisor_node(state: AssessmentState, llm) -> dict:
    """[Supervisor Agent] 전체 흐름 제어 및 라우팅 (Hard Override Logic 적용)"""
    
    # [1] 현재 진행 상황 체크
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

    # [2] LLM에게 판단 요청
    messages = [
        SystemMessage(content=prompts["supervisor_system"]),
        HumanMessage(content=f"Current Status: {json.dumps(status)}")
    ]
    response = llm.invoke(messages)
    logger.debug(f"LLM 원본 응답: {response.content}")
    
    # [3] LLM 결정 파싱 (실패 시 None)
    llm_decision = None
    try:
        decision = json.loads(response.content)
        llm_decision = decision.get("next_worker")
    except:
        logger.warning("❌ LLM 응답 파싱 실패. LLM 결정 무효화.")

    # [4] 🔥 하드 오버라이드 로직 (필수 단계 미완료 시 강제 전환)
    
    next_worker = llm_decision
    
    if not has_grammar:
        if next_worker != "linguist":
            logger.warning(f"LLM 결정 '{llm_decision}' 무시. 필수 단계 누락으로 'linguist' 강제.")
        next_worker = "linguist"
    elif not has_context:
        if next_worker != "context_analyst":
            logger.warning(f"LLM 결정 무시. 필수 단계 누락으로 'context_analyst' 강제.")
        next_worker = "context_analyst"
    elif not has_score:
        next_worker = "evaluator"
    elif not has_feedback:
        next_worker = "tutor"
    else:
        # 모든 게 끝났으면 최종 종료
        next_worker = "FINISH"
        
    logger.info(f"➡️ 다음 작업자 결정: {next_worker}")
    return {"next_worker": next_worker}