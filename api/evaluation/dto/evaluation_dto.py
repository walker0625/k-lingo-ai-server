from pydantic import BaseModel, Field
from typing import List, Dict, Any

class FeedbackSummaryDetail(BaseModel):
    title: str
    message: str

class ScenarioResult(BaseModel):
    scenario_type: str
    display_name: str
    final_score: int
    grade: str
    feedback_summary: FeedbackSummaryDetail
    action_item: str

class TotalResult(BaseModel):
    final_score: int
    grade: str
    feedback_summary: str

class EvaluationResponse(BaseModel):
    total_result: TotalResult
    scenario_results: List[ScenarioResult]