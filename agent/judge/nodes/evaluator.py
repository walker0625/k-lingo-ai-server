import json
from langchain_core.messages import SystemMessage, HumanMessage
from ..states import AssessmentState
from .analysts import prompts 
from ..logger import get_logger
from typing import Dict, Any

logger = get_logger("Evaluator")

def chief_evaluator(state: AssessmentState, llm) -> dict:
    
    logger.info("⚖️ 최종 평가 및 점수 산출 시작...")
    
    PASS_THRESHOLD = 60
    
    # 1. 이전 단계(Linguist, Context Analyst)의 분석 결과 가져오기
    grammar_data: Dict[str, Any] = state.get('grammar_result') or {}
    context_data: Dict[str, Any] = state.get('context_result') or {}

    # 2. 각 점수 추출
    grammar_score = int(grammar_data.get('grammar_score', 0))
    
    context_score = int(context_data.get('context_score', 0))

    logger.info(f"📊 서브 점수 확인 - 문법: {grammar_score}, 맥락: {context_score}")

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
        }
    }
        
    logger.info(f"✅ 최종 점수 산출 완료: {total_score}점 ({is_pass})")
    
    return {"score_result": result}