from enum import Enum
from pydantic import BaseModel

class GradeType(Enum):
    S = 'S'
    A = 'A'
    B = 'B'
    C = 'C'
    D = 'D'
    F = 'F'

class EvalutionType(Enum):
    CLEAR_TIME = 1
    WRONG_INDEX = 2

class EvalutionRule(BaseModel):
    interval:list[int]
    score:list[float]

EVALUTION_TABLE = {
    EvalutionType.CLEAR_TIME : EvalutionRule(
        interval=[180,240,300],
        score=[30.0,20.0,10.0]
    ),
    EvalutionType.WRONG_INDEX : EvalutionRule(
        interval=[0,1,2,3,4,5,6,7,8,9,10],
        score=[70.0,63.0,56.0,49.0,42.0,35.0,28.0,21.0,14.0,78.0,0.0]
    )
}

def evaluate(evalution_type:EvalutionType, score:int) -> float:
    """
        wrong index, clear time에 대한 평가 점수 계산
        (기준 추가시 인터벌과 스코어 추가 필요)
    """
    if score < 0:
        return 0.0
    TIME_INTERVAL = EVALUTION_TABLE[evalution_type].interval
    SCORE_INTERVAL = EVALUTION_TABLE[evalution_type].score
    for _time, _score in zip(TIME_INTERVAL,SCORE_INTERVAL):
        if score <= _time:
            return _score
    return 0.0

def grade(total_score:float) -> GradeType:
    if total_score >= 95:
        return GradeType.S
    if total_score >= 85:
        return GradeType.A
    if total_score >= 75:
        return GradeType.B
    if total_score >= 60:
        return GradeType.C
    if total_score >= 40:
        return GradeType.D
    return GradeType.F