## scenario, quest progress state management api
from pydantic import BaseModel
from db.model.scenario import StageType
from db.model.progress import ProgressState
from common.evaluation import GradeType
from common.evaluation import EvalutionType, evaluate, grade

class ProgressInfo(BaseModel):
    user_id: int
    scenario_id: int
    stage_type: StageType       ## READING, LISTENING, WRITING, SPEAKING
    state_type: ProgressState   ## START, DOING, DONE

class ProgressRLInfo(ProgressInfo):
    """
        Reading, Listening Progress Info
    """
    result_time: int        # stage progress time(second)
    wrong_idx: list[int]    # incorrect answer index list
    
class ProgressScore(BaseModel):
    score: float
    desc: str

class ProgressResult(BaseModel):
    grade: GradeType = GradeType.F     # Grade for points
    average_score: float = 0.0         # point ( 0 ~ 100)
    top_percent: float = 0.0           # Grades are in the top few percen
    scores: list[ProgressScore] = []   # detailed scores
    
# class WriteProgressResult(ProgressResult):
#     pass

# class SpeakProgressResult(ProgressResult):
#     pass

def evaluate_reading_grade(stage_progress:ProgressRLInfo):
    _clear_score = evaluate(EvalutionType.CLEAR_TIME, stage_progress.result_time)
    _correct_score = evaluate(EvalutionType.WRONG_INDEX, len(stage_progress.wrong_idx))
    total_point = _clear_score + _correct_score
    return grade(total_point)

def average_score(scores:list[ProgressScore]):
    if not scores:
        return 0.0
    total = sum([score.score for score in scores])
    return total / len(scores)