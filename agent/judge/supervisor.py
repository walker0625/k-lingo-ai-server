# agent/judge/supervisor.py
import json
from langchain_core.messages import SystemMessage, HumanMessage
from .nodes.analysts import prompts
from .states import AssessmentState
from .logger import get_logger

logger = get_logger("Supervisor")

# 최대 재시도 횟수 설정
MAX_RETRY_COUNT = 3

def _check_node_failed(state: AssessmentState, node_name: str) -> bool:
    """특정 노드가 실패 상태인지 확인"""
    error_states = state.get("error_states") or {}
    return error_states.get(node_name) is not None

def _get_retry_count(state: AssessmentState, node_name: str) -> int:
    """특정 노드의 재시도 횟수 반환"""
    retry_counts = state.get("retry_counts") or {}
    return retry_counts.get(node_name, 0)

def _should_retry(state: AssessmentState, node_name: str) -> bool:
    """재시도 가능 여부 확인 (최대 횟수 미만인 경우)"""
    return _get_retry_count(state, node_name) < MAX_RETRY_COUNT

def _create_fallback_result(node_name: str) -> dict:
    """노드별 실패 시 기본 fallback 결과 생성 (score: None + status: SYSTEM_ERROR)"""
    if node_name == "linguist":
        return {
            "grammar_result": {
                "grammar_score": None,  # 평가 불가
                "status": "SYSTEM_ERROR",
                "issues": ["시스템 오류로 인해 문법 분석을 완료할 수 없습니다."],
                "is_fallback": True
            }
        }
    elif node_name == "context_analyst":
        return {
            "context_result": {
                "context_score": None,  # 평가 불가
                "status": "SYSTEM_ERROR",
                "is_relevant": None,  # 판단 불가
                "reason": "시스템 오류로 인해 맥락 분석을 완료할 수 없습니다.",
                "is_fallback": True
            }
        }
    elif node_name == "tutor":
        return {
            "final_feedback": "We apologize, but we couldn't generate personalized feedback at this time. "
                             "Please try again later. Your response has been recorded for evaluation.",
            "feedback_status": "SYSTEM_ERROR",
            "is_fallback": True
        }
    elif node_name == "evaluator":
        return {
            "score_result": {
                "score": None,  # 평가 불가
                "result": "SYSTEM_ERROR",  # Pass/Fail 대신 에러 상태
                "status": "EVALUATION_FAILED",
                "reason": "시스템 오류로 평가를 완료할 수 없습니다.",
                "sub_scores": {"grammar_score": None, "context_score": None},
                "is_fallback": True
            }
        }
    return {}

def supervisor_node(state: AssessmentState, llm) -> dict:
    """전체 흐름 제어 및 라우팅 (노드 실패 처리 포함)"""
    
    # [1] 현재 진행 상황 요약
    has_grammar = state.get("grammar_result") is not None
    has_context = state.get("context_result") is not None
    has_score = state.get("score_result") is not None
    has_feedback = state.get("final_feedback") is not None
    
    # [1.1] 에러 상태 확인
    error_states = state.get("error_states") or {}
    linguist_failed = _check_node_failed(state, "linguist")
    context_failed = _check_node_failed(state, "context_analyst")
    evaluator_failed = _check_node_failed(state, "evaluator")
    tutor_failed = _check_node_failed(state, "tutor")
    
    status = {
        "grammar": "FAILED" if linguist_failed else ("DONE" if has_grammar else "WAITING"),
        "context": "FAILED" if context_failed else ("DONE" if has_context else "WAITING"),
        "score": "FAILED" if evaluator_failed else ("DONE" if has_score else "WAITING"),
        "feedback": "FAILED" if tutor_failed else ("DONE" if has_feedback else "WAITING")
    }
    logger.info(f"현재 진행 상황: {status}")
    
    # [2] 노드 실패 처리 로직
    result_updates = {}
    
    # 문법 분석 실패 처리
    if linguist_failed:
        retry_count = _get_retry_count(state, "linguist")
        if _should_retry(state, "linguist"):
            logger.warning(f"🔄 linguist 노드 실패 감지. 재시도 시도 ({retry_count + 1}/{MAX_RETRY_COUNT})")
            return {"next_worker": "linguist"}
        else:
            logger.error(f"❌ linguist 노드 최대 재시도 횟수({MAX_RETRY_COUNT}) 초과. Fallback 결과 사용.")
            result_updates.update(_create_fallback_result("linguist"))
            # 에러 상태 클리어
            error_states["linguist"] = None
            result_updates["error_states"] = error_states
            has_grammar = True  # fallback으로 처리 완료
    
    # 맥락 분석 실패 처리
    if context_failed:
        retry_count = _get_retry_count(state, "context_analyst")
        if _should_retry(state, "context_analyst"):
            logger.warning(f"🔄 context_analyst 노드 실패 감지. 재시도 시도 ({retry_count + 1}/{MAX_RETRY_COUNT})")
            return {"next_worker": "context_analyst", **result_updates}
        else:
            logger.error(f"❌ context_analyst 노드 최대 재시도 횟수({MAX_RETRY_COUNT}) 초과. Fallback 결과 사용.")
            result_updates.update(_create_fallback_result("context_analyst"))
            # 에러 상태 클리어
            error_states["context_analyst"] = None
            result_updates["error_states"] = error_states
            has_context = True  # fallback으로 처리 완료

    # 평가(점수 산출) 실패 처리
    if evaluator_failed:
        retry_count = _get_retry_count(state, "evaluator")
        if _should_retry(state, "evaluator"):
            logger.warning(f"🔄 evaluator 노드 실패 감지. 재시도 시도 ({retry_count + 1}/{MAX_RETRY_COUNT})")
            return {"next_worker": "evaluator", **result_updates}
        else:
            logger.error(f"❌ evaluator 노드 최대 재시도 횟수({MAX_RETRY_COUNT}) 초과. Fallback 결과 사용.")
            result_updates.update(_create_fallback_result("evaluator"))
            # 에러 상태 클리어
            error_states["evaluator"] = None
            result_updates["error_states"] = error_states
            has_score = True  # fallback으로 처리 완료

    # 튜터(피드백) 실패 처리
    if tutor_failed:
        retry_count = _get_retry_count(state, "tutor")
        if _should_retry(state, "tutor"):
            logger.warning(f"🔄 tutor 노드 실패 감지. 재시도 시도 ({retry_count + 1}/{MAX_RETRY_COUNT})")
            return {"next_worker": "tutor", **result_updates}
        else:
            logger.error(f"❌ tutor 노드 최대 재시도 횟수({MAX_RETRY_COUNT}) 초과. Fallback 결과 사용.")
            result_updates.update(_create_fallback_result("tutor"))
            # 에러 상태 클리어
            error_states["tutor"] = None
            result_updates["error_states"] = error_states
            has_feedback = True  # fallback으로 처리 완료

    # [3] LLM에게 판단 요청 (정상 흐름)
    messages = [
        SystemMessage(content=prompts["supervisor_system"]),
        HumanMessage(content=f"Current Status: {json.dumps(status)}")
    ]
    
    try:
        response = llm.invoke(messages)
        logger.debug(f"LLM 원본 응답: {response.content}")
        decision = json.loads(response.content)
        llm_decision = decision.get("next_worker", "FINISH")
    except json.JSONDecodeError:
        logger.warning("❌ LLM 응답 파싱 실패 (JSON 깨짐). 강제 로직을 따릅니다.")
        llm_decision = "ERROR"
    except Exception as e:
        logger.error(f"❌ Supervisor LLM 호출 실패: {e}. 강제 로직을 따릅니다.")
        llm_decision = "ERROR"

    # [4] 🔥 하드 오버라이드 로직 (Supervisor의 핵심 역할)
    next_worker = llm_decision

    if not has_grammar:
        if next_worker != "linguist":
            logger.warning(f"LLM이 '{llm_decision}' 명령. 필수 단계 누락으로 'linguist'로 강제 전환.")
        next_worker = "linguist"
    elif not has_context:
        if next_worker != "context_analyst":
            logger.warning(f"LLM 명령 무시. 필수 단계 누락으로 'context_analyst'로 강제 전환.")
        next_worker = "context_analyst"
    elif not has_score:
        next_worker = "evaluator"
    elif not has_feedback:
        next_worker = "tutor"
    else:
        next_worker = "FINISH"
        
    logger.info(f"➡️ 다음 작업자 결정: {next_worker}")
    
    # result_updates가 있으면 함께 반환 (fallback 결과 포함)
    return {"next_worker": next_worker, **result_updates}