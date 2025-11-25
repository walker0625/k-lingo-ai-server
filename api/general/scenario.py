import os, logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from db.session import  SessionDep
from db.model.scenario import Scenario,ScenarioResponse, Stage, StageType, QuestLevel, ReadingQuest, ListeningQuest
from api.general.service.scenario_service import QuestReadOrListenInfo, quest_words, gen_read_or_listen_quest

## logger
logger = logging.getLogger("app")
## user router
router = APIRouter()

# Routes
@router.get("/", response_model=list[ScenarioResponse])
def get_scenarios(session : SessionDep):
    """
        시나리오 리스트
    """
    statement = select(Scenario)
    _scenarios = session.exec(statement).all()
    results = []
    for _scenario in _scenarios:
        results.append(ScenarioResponse(
            id = _scenario.id,
            lang = _scenario.lang_code.name,
            title = _scenario.title,
            desc = _scenario.desc,
            created_at = _scenario.created_at,
            updated_at = _scenario.updated_at,
            stages = _scenario.stages
        ))
    return results

@router.get("/stages", response_model=list[Stage])
def get_stages(session : SessionDep):
    """
        시나리오 리스트
    """
    statement = select(Stage)
    results = session.exec(statement).all()
    return results

@router.get("/{scenario_id}/{stage_id}/{level}", response_model=QuestReadOrListenInfo)
def get_stage(scenario_id:int, stage_id:int, level:int, session : SessionDep):
    """
        시나리오 ID, 스테이지 ID, 레벨로 스테이지 퀘스트 정보 가져오기
    """
    # scenario = session.get(Scenario, scenario_id)
    # if not scenario:
    #     raise HTTPException(
    #         status_code=status.HTTP_404_NOT_FOUND,
    #         detail="Scenario not found"
    #     )
    statement = select(Stage).where(
        Stage.scenario_id == scenario_id,
        Stage.id == stage_id
    )
    stages =  session.exec(statement).all()#scenario.stages
    if not stages and len(stages) <= 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stage not found"
        )
    quest = stages[0].quest
    stage_type = stages[0].type_code
    quest_info = gen_read_or_listen_quest(
        stage_type,
        [ReadingQuest(**q) for q in quest] ## 타입에 따른 바인딩
            if StageType(stage_type) == StageType.READING
            else [ListeningQuest(**q) for q in quest],
        QuestLevel(level))
    return quest_info

# Routes
@router.get("/stages/{scenario_id}/{stage_type}/{level}", response_model=QuestReadOrListenInfo)
def get_stage_by_type(scenario_id:int, stage_type:int, level:int, session : SessionDep):
    """
        시나리오 ID, 스테이지 유형(읽기:1, 듣기:2, 쓰기:3, 말하기:4), 레벨로 스테이지 퀘스트 정보 가져오기
    """
    _stage_type = StageType(stage_type)
    statement = select(Stage).where(
        Stage.scenario_id == scenario_id,
        Stage.type_code == _stage_type
    )
    stages =  session.exec(statement).all()
    if not stages and len(stages) <= 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stage not found"
        )
    quest = stages[0].quest
    quest_info = gen_read_or_listen_quest(
        _stage_type,
        [ReadingQuest(**q) for q in quest] ## 타입에 따른 바인딩
            if _stage_type == StageType.READING
            else [ListeningQuest(**q) for q in quest],
        QuestLevel(level))
    return quest_info