import json
from langchain_core.messages import SystemMessage, HumanMessage
from ..states import AssessmentState
from .analysts import prompts, NodeErrorType, _update_error_state, _update_retry_count
from ..logger import get_logger
from typing import Dict, Any

logger = get_logger("Evaluator")

def chief_evaluator(state: AssessmentState, llm) -> dict:
    """최종 평가 및 점수 산출 (LLM 미사용, 순수 계산)"""
    
    logger.info("⚖️ 최종 평가 및 점수 산출 시작...")
    
    PASS_THRESHOLD = 60
    DEFAULT_SCORE = 50  # 데이터 없을 때 기본 점수
    
    try:
        # 1. 이전 단계(Linguist, Context Analyst)의 분석 결과 가져오기
        grammar_data: Dict[str, Any] = state.get('grammar_result') or {}
        context_data: Dict[str, Any] = state.get('context_result') or {}

        # 2. 각 점수 추출 (fallback 결과 또는 파싱 실패 시 기본값 사용)
        grammar_score = int(grammar_data.get('grammar_score', DEFAULT_SCORE))
        context_score = int(context_data.get('context_score', DEFAULT_SCORE))
        
        # fallback 결과 여부 확인
        is_grammar_fallback = grammar_data.get('is_fallback', False)
        is_context_fallback = context_data.get('is_fallback', False)

        logger.info(f"📊 서브 점수 확인 - 문법: {grammar_score}{'(fallback)' if is_grammar_fallback else ''}, "
                   f"맥락: {context_score}{'(fallback)' if is_context_fallback else ''}")

        # 3. Python 코드로 단순 평균 계산
        # 문법(50%) + 맥락(50%)
        total_score = round((grammar_score + context_score) / 2)

        # 4. 결과 반환
        is_pass = "Pass" if total_score >= PASS_THRESHOLD else "Fail"

        result = {
            "score": total_score,
            "result": is_pass,
            "reason": f"문법 점수({grammar_score})와 맥락 점수({context_score})의 평균 산출",
            "sub_scores": {
                "grammar_score": grammar_score, 
                "context_score": context_score
            },
            "has_fallback_data": is_grammar_fallback or is_context_fallback
        }
            
        logger.info(f"✅ 최종 점수 산출 완료: {total_score}점 ({is_pass})")
        
        return {"score_result": result}
        
    except (TypeError, ValueError) as e:
        # 점수 변환 실패 등 예외 처리
        logger.error(f"❌ 점수 계산 중 오류 발생: {e}")
        
        # 에러 발생 시 시스템 오류 상태 반환 (score: None)
        fallback_result = {
            "score": None,  # 평가 불가
            "result": "SYSTEM_ERROR",
            "status": "EVALUATION_FAILED",
            "reason": f"점수 계산 오류: {str(e)}",
            "sub_scores": {
                "grammar_score": None, 
                "context_score": None
            },
            "is_fallback": True
        }
        
        return {
            "score_result": fallback_result,
            "error_states": _update_error_state(state, "evaluator", NodeErrorType.UNKNOWN_ERROR),
            "retry_counts": _update_retry_count(state, "evaluator")
        }
    except Exception as e:
        # 예상치 못한 오류
        logger.error(f"❌ 평가 노드 예상치 못한 오류: {type(e).__name__} - {e}")
        
        return {
            "score_result": None,
            "error_states": _update_error_state(state, "evaluator", NodeErrorType.UNKNOWN_ERROR),
            "retry_counts": _update_retry_count(state, "evaluator")
        }