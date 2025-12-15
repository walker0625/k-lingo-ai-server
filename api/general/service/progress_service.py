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
    
class ProgressResult(BaseModel):
    grade: GradeType            # Grade for points
    average_score: float        # point ( 0 ~ 100)
    top_percent: float | None   # Grades are in the top few percen
    
class WriteProgressResult(ProgressResult):
    pass

class SpeakProgressResult(ProgressResult):
    pass

def evaluate_reading_grade(stage_progress:ProgressRLInfo):
    _clear_score = evaluate(EvalutionType.CLEAR_TIME, stage_progress.result_time)
    _correct_score = evaluate(EvalutionType.WRONG_INDEX, len(stage_progress.wrong_idx))
    total_point = _clear_score + _correct_score
    return grade(total_point)