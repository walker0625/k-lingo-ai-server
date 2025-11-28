import json
from langchain_core.messages import SystemMessage, HumanMessage
from ..states import AssessmentState
from .analysts import prompts 
from ..logger import get_logger
from typing import Dict, Any

logger = get_logger("Evaluator")

def chief_evaluator(state: AssessmentState, llm) -> dict:
    logger.info("⚖️ 최종 평가 및 점수 산출 시작...")
    
    # [하이브리드 로직 설정]
    WEIGHT_ACCURACY = 0.5
    WEIGHT_FLUENCY = 0.5   
    PASS_THRESHOLD = 60
    CRITICAL_FAIL_SCORE = 30 # 질문에 답하지 않았을 때 강제 부여 점수 (30점 이하)
    
    # 🚨 데이터 안전하게 가져오기
    grammar_data: Dict[str, Any] = state.get('grammar_result', {'score': 0})
    context_data: Dict[str, Any] = state.get('context_result', {'is_relevant': False})

    # [1] Critical Fail 검사: 질문과 관련이 없는가?
    is_critical_fail = context_data.get('is_relevant', False) == False
    
    # 1. 프롬프트 포맷팅
    system_msg = prompts["evaluator_system"].format(
        level=state["target_level"],
        grammar_analysis=json.dumps(grammar_data), 
        context_analysis=json.dumps(context_data)  
    )
    
    messages = [
        SystemMessage(content=system_msg),
        HumanMessage(content=f"사용자 발화: {state['user_text']}")
    ]
    
    # 2. Critical Fail 시 LLM 호출 생략 및 강제 점수 부여
    if is_critical_fail:
        total_score = CRITICAL_FAIL_SCORE
        accuracy = 0
        fluency = 0
        logger.warning(f"🚨 Critical Fail: 관련성 없음. 점수 {CRITICAL_FAIL_SCORE}점 강제 부여.")
    else:
        # Critical Fail이 아닐 경우 LLM에게 서브 스코어를 요청
        response = llm.invoke(messages)
        accuracy, fluency = 0, 0
        try:
            data = json.loads(response.content)
            accuracy = int(data.get('accuracy_score', 0))
            fluency = int(data.get('fluency_score', 0))
        except Exception:
            logger.error("❌ 평가 JSON 파싱/데이터 오류. 서브 점수 0점 처리.")

        # 3. Python 코드로 최종 점수 계산
        total_score = round((accuracy * WEIGHT_ACCURACY) + (fluency * WEIGHT_FLUENCY))

    # 4. 결과 반환
    is_pass = "Pass" if total_score >= PASS_THRESHOLD else "Fail"

    result = {
        "score": total_score,
        "result": is_pass,
        "reason": f"정확도({accuracy}점 x {WEIGHT_ACCURACY}) + 유창성({fluency}점 x {WEIGHT_FLUENCY})",
        "sub_scores": {"accuracy": accuracy, "fluency": fluency}
    }
        
    logger.info(f"✅ 최종 점수 산출 완료: {total_score}점 ({is_pass})")
    
    return {"score_result": result}