# agent/judge/nodes/tutor.py (전체 파일)
import json
import re
from langchain_core.messages import SystemMessage, HumanMessage
from ..states import AssessmentState
from .analysts import prompts
from ..logger import get_logger

logger = get_logger("Tutor")

def extract_json_from_markdown(text: str) -> str:
    """Markdown JSON 블록을 안전하게 추출합니다."""
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text

def feedback_tutor(state: AssessmentState, llm) -> dict:
    logger.info("👩‍🏫 피드백 생성 시작...")
    
    score_data = state.get("score_result", {"score": 0, "result": "Fail"})
    
    # 데이터 직렬화 (ensure_ascii=False로 한글 깨짐 방지)
    grammar_errors_str = json.dumps(state.get('grammar_result', {'issues': ['분석 데이터 없음']}).get('issues', ['없음']), ensure_ascii=False)
    context_errors_str = json.dumps(state.get('context_result', {'reason': '분석 데이터 없음'}).get('reason', '없음'), ensure_ascii=False)

    # 1. 시스템 프롬프트 포맷팅
    system_msg = prompts["tutor_system"].format(
        score=score_data.get("score", 0),
        result=score_data.get("result", "Fail"),
        level=state["target_level"],
        grammar_errors=grammar_errors_str,
        context_errors=context_errors_str
    )
    
    # 2. 휴먼 메시지 구성 (최종 출력 지침 재강조)
    input_msg = (
        f"학습자 발화: {state['user_text']}\n"
        f"평가 내용: {score_data}\n\n"
        "[출력 지침] 위에 제공된 평가 내용을 바탕으로 **반드시 영어로** 교육적 피드백을 작성하세요. "
        "결과는 JSON: {\"message\": \"...\"} 형식으로 출력해야 합니다."
    )
    
    messages = [
        SystemMessage(content=system_msg),
        HumanMessage(content=input_msg)
    ]
    
    response = llm.invoke(messages)
    raw_content = response.content.strip()
    final_feedback = raw_content

    # 3. LLM 응답 파싱
    try:
        json_text = extract_json_from_markdown(raw_content)
        feedback_json = json.loads(json_text)
        
        # 'message' 키에서 최종 피드백 추출
        final_feedback = feedback_json.get("message", final_feedback) 
        
        logger.info("✅ 피드백 생성 완료 (JSON 파싱 성공)")
        
    except Exception:
        logger.error("❌ 피드백 JSON 파싱 실패. 원본 텍스트를 피드백으로 사용합니다.")
        
    return {
        "final_feedback": final_feedback,
        "revision_count": state.get("revision_count", 0) + 1
    }