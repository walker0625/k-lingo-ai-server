import json
import yaml
from pathlib import Path
from langchain_core.messages import SystemMessage, HumanMessage
from ..states import AssessmentState
from ..utils.sejong_criteria import get_sejong_criteria
from ..logger import get_logger
from typing import Dict, Any

logger = get_logger("Analyst")

# 에러 타입 상수 정의
class NodeErrorType:
    LLM_TIMEOUT = "LLM_TIMEOUT"
    LLM_API_ERROR = "LLM_API_ERROR"
    PARSE_ERROR = "PARSE_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"

def load_prompts():
    prompt_path = Path(__file__).parent.parent / "prompts" / "assessment.yaml"
    with open(prompt_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

prompts = load_prompts()

def _get_safe_state_value(value, default: str = ""):
    """Dict/List인 경우 JSON 문자열로 변환하여 반환"""
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)

def _update_error_state(state: AssessmentState, node_name: str, error_type: str) -> Dict[str, str]:
    """에러 상태를 업데이트하고 반환"""
    error_states = dict(state.get("error_states") or {})
    error_states[node_name] = error_type
    return error_states

def _update_retry_count(state: AssessmentState, node_name: str) -> Dict[str, int]:
    """재시도 횟수를 증가시키고 반환"""
    retry_counts = dict(state.get("retry_counts") or {})
    retry_counts[node_name] = retry_counts.get(node_name, 0) + 1
    return retry_counts

def linguistic_analyst(state: AssessmentState, llm) -> dict:
    logger.info("📝 문법 분석 시작...")
    
    level = state["target_level"]
    criteria = get_sejong_criteria(level)
    
    system_msg = prompts["linguist_system"].format(
        level=level,
        description=criteria["description"],
        grammar_criteria=_get_safe_state_value(criteria["grammar"]),
        topic_criteria=criteria["topic"]
    )
    
    messages = [
        SystemMessage(content=system_msg),
        HumanMessage(content=f"사용자 발화: {state['user_text']}")
    ]
    
    # LLM 호출 with 에러 핸들링
    try:
        response = llm.invoke(messages)
    except TimeoutError as e:
        logger.error(f"❌ 문법 분석 LLM 타임아웃: {e}")
        return {
            "grammar_result": None,
            "error_states": _update_error_state(state, "linguist", NodeErrorType.LLM_TIMEOUT),
            "retry_counts": _update_retry_count(state, "linguist")
        }
    except Exception as e:
        logger.error(f"❌ 문법 분석 LLM 호출 실패: {type(e).__name__} - {e}")
        return {
            "grammar_result": None,
            "error_states": _update_error_state(state, "linguist", NodeErrorType.LLM_API_ERROR),
            "retry_counts": _update_retry_count(state, "linguist")
        }
    
    # JSON 파싱
    try:
        result = json.loads(response.content)
        logger.info("✅ 문법 분석 완료")
        # 성공 시 에러 상태 클리어
        error_states = dict(state.get("error_states") or {})
        error_states["linguist"] = None
        return {"grammar_result": result, "error_states": error_states}
    except json.JSONDecodeError as e:
        logger.error(f"❌ 문법 분석 결과 파싱 실패: {e}")
        result = {"grammar_score": 0, "issues": [f"파싱 실패: {e}"]} 
        return {"grammar_result": result}

def context_analyst(state: AssessmentState, llm) -> dict:
    logger.info("👀 맥락 분석 시작...")
    
    level = state["target_level"]
    criteria = get_sejong_criteria(level)
    
    system_msg = prompts["context_system"].format(
        context=state["context"],
        question=state["question"],
        level=level,
        task_goal=criteria["task_goal"],
        discourse_criteria=criteria["discourse"]
    )
    
    messages = [
        SystemMessage(content=system_msg),
        HumanMessage(content=f"답변: {state['user_text']}")
    ]
    
    # LLM 호출 with 에러 핸들링
    try:
        response = llm.invoke(messages)
    except TimeoutError as e:
        logger.error(f"❌ 맥락 분석 LLM 타임아웃: {e}")
        return {
            "context_result": None,
            "error_states": _update_error_state(state, "context_analyst", NodeErrorType.LLM_TIMEOUT),
            "retry_counts": _update_retry_count(state, "context_analyst")
        }
    except Exception as e:
        logger.error(f"❌ 맥락 분석 LLM 호출 실패: {type(e).__name__} - {e}")
        return {
            "context_result": None,
            "error_states": _update_error_state(state, "context_analyst", NodeErrorType.LLM_API_ERROR),
            "retry_counts": _update_retry_count(state, "context_analyst")
        }
    
    # JSON 파싱
    try:
        json_text = response.content.strip()
        if json_text.startswith("```json"):
            json_text = json_text.split("```json")[1].split("```")[0].strip()
        
        result = json.loads(json_text)
        logger.info("✅ 맥락 분석 완료")
        # 성공 시 에러 상태 클리어
        error_states = dict(state.get("error_states") or {})
        error_states["context_analyst"] = None
        return {"context_result": result, "error_states": error_states}
    except json.JSONDecodeError as e:
        logger.error(f"❌ 맥락 분석 결과 파싱 실패: {e}")
        result = {"context_score": 0, "is_relevant": False, "reason": "시스템 오류"}
        return {"context_result": result}