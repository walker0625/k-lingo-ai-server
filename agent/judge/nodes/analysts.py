import json
import yaml
from pathlib import Path
from langchain_core.messages import SystemMessage, HumanMessage
from ..states import AssessmentState
from ..utils.sejong_criteria import get_sejong_criteria
from ..logger import get_logger
from typing import Dict, Any

logger = get_logger("Analyst")

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
    
    response = llm.invoke(messages)
    
    try:
        result = json.loads(response.content)
        logger.info("✅ 문법 분석 완료")
    except Exception as e:
        logger.error(f"❌ 문법 분석 결과 파싱 실패: {e}")
        result = {"score": 0, "issues": [f"파싱 실패: {e}"]} 
        
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
    
    response = llm.invoke(messages)
    try:
        # Llama 모델의 마크다운 JSON 블록 처리
        json_text = response.content.strip()
        if json_text.startswith("```json"):
            json_text = json_text.split("```json")[1].split("```")[0].strip()
        
        result = json.loads(json_text)
        logger.info("✅ 맥락 분석 완료")
    except Exception as e:
        logger.error(f"❌ 맥락 분석 결과 파싱 실패: {e}")
        # 동문서답 여부를 확인할 수 없으므로 is_relevant: False로 간주 (Worst Case Fallback)
        result = {"context_score": 0, "is_relevant": False, "reason": "시스템 오류"}
        
    return {"context_result": result}