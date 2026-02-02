from typing import TypedDict, Optional, List, Dict, Any

class AssessmentState(TypedDict):
    """LangGraph 상태 정의"""
    user_text: str
    question: str
    context: str
    target_level: int
    
    # [Analysis Results]
    grammar_result: Optional[Dict[str, Any]]
    context_result: Optional[Dict[str, Any]]
    
    # [Evaluation Results]
    score_result: Optional[Dict[str, Any]]
    final_feedback: Optional[str]
    
    # [Control]
    next_worker: Optional[str]
    revision_count: int
    
    # [Error Handling] - 노드 실패 추적
    error_states: Optional[Dict[str, str]]  # {"linguist": "LLM_TIMEOUT", "context_analyst": None}
    retry_counts: Optional[Dict[str, int]]  # {"linguist": 2, "context_analyst": 0}