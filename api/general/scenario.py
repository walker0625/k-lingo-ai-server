import json
from fastapi import APIRouter, HTTPException, status, Depends
from sqlmodel import select
from db.session import  SessionDep, get_current_active_user
from typing import Annotated
from db.model.user import User
from db.model.scenario import (
    Scenario,ScenarioResponse, Stage, StageType, QuestLevel, ReadingQuest, ListeningQuest
)
from api.general.service.scenario_service import QuestReadOrListenInfo, gen_read_or_listen_quest
from db.redis import StateStore
from db.model.progress import ProgressResponse, ProgressState, Progress, ProgressCreate
from .service.progress_service import ProgressRLInfo, ProgressResult
from common.evaluation import EvalutionType, evaluate, grade
## logger
from loguru import logger
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
            stages = list(session.exec(select(Stage).where(Stage.scenario_id == _scenario.id)).all()) #_scenario.stages
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
    quest_info.index = scenario_id
    return quest_info

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
    quest_info.index = scenario_id ## 시나리오 번호로 변경하여 전송
    return quest_info

@router.get("/stages/redis/{scenario_id}/{stage_type}/{level}", response_model=QuestReadOrListenInfo)
async def get_stage_by_type_with_redis(
    scenario_id:int, stage_type:int, level:int,
    session : SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """
        시나리오 ID, 스테이지 유형(읽기:1, 듣기:2, 쓰기:3, 말하기:4), 레벨로 스테이지 퀘스트 정보 가져오기
        [ 시나리오 생성 후 평가 결과 처리를 위해 redis에 저장 ]
    """
    _stage_type = StageType(stage_type)
    ## redis에 종료안된 상태(state_type not DONE, REPORT)의 데이터 확인
    ## 있으면 해당 내용 전송하고 끝(초기 상태 저장하는 것을 가정)
    ## 동시에 하나의 시나리오만 처리 하는 것을 가정하고 진행
    ## 중간에 스테이지를 변경 할 경우 진행중인 스테이지가 있는 것을 알려줌??
    store = StateStore()
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Need to set up redis"
        )
    saved_progress = await store.load_progress_state(current_user.username)
    if saved_progress and saved_progress:
        user_progress = ProgressResponse(**saved_progress)
        ## 다른 스테이지의 진행 중인 시나리오가 있는 경우 해당 시나리오 전송
        ## 스테이지가 진행 중인 상태인 경우
        if user_progress.state_type != ProgressState.DONE and user_progress.state_type != ProgressState.REPORT:
            # user_progress.scenario_id == scenario_id and user_progress.stage_type == StageType(stage_type) and \
            ## 타입 체크, READING/LISTENING 인 경우
            if _stage_type == StageType.READING or StageType.LISTENING:
                return QuestReadOrListenInfo.model_validate(user_progress.scenario, from_attributes=True)
        ## WRITING, SPEAKING 인경우 추가 처리 필요

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
    quest_info.index = scenario_id ## 시나리오 번호로 변경하여 전송
    
    progress = Progress(
        user_id=current_user.id,
        scenario_id=scenario_id,
        stage_type=StageType(stage_type),
        scenario=quest_info.model_dump(mode='json')
    )
    logger.info("****** new progress")
    logger.info(progress)
    session.add(progress)
    session.commit()
    session.refresh(progress)
    logger.info(progress)
    logger.info("****** new redis")
    ### redis에 초기 상태 저장
    ### 초기 상태 DB 저장 검토 필요, 최종 결과 만 저장하는 경우 불필요함
    await store.save_progress_state(
        current_user.username,
        ProgressResponse.model_validate(progress, from_attributes=True)
    )
    return quest_info

@router.post("/stage/result/post", response_model=ProgressResult, status_code=status.HTTP_201_CREATED)
async def register(result: ProgressRLInfo, session: SessionDep):
    """
        Reading, Listening Stage 결과 처리
    """
    # Check if user exists
    statement = select(User).where(User.id == result.user_id)
    existing_user = session.exec(statement).first()
    if not existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found"
        )
    # Check redis
    store = StateStore()
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Need to set up Redis"
        )
    saved_progress = await store.load_progress_state(existing_user.username)
    if not saved_progress:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your Scenario not found"
        )
    _clear_point = evaluate(EvalutionType.CLEAR_TIME,result.result_time)
    _wrong_point = evaluate(EvalutionType.WRONG_INDEX,len(result.wrong_idx))
    _total_point = _clear_point+_wrong_point
    # update progress result
    _result = ProgressResult(
        grade=grade(_total_point),
        point=_total_point,
        top_percent=0.23 ## 구현 필요 => 해당 시나리오, 스테이지에 대한 완료 결과만 읽어 (소팅인덱스+1)/갯수로 결과 생성
    )
    user_progress = ProgressResponse(**saved_progress)
    logger.info(user_progress)
    ## 결과 및 완료 처리
    user_progress.result = _result.model_dump(mode='json')
    user_progress.state_type = ProgressState.DONE
    await store.save_progress_state(existing_user.username,user_progress)
    ## DB의 progress 정보 조회 후 업데이트(progress id 어떻게 체크??)
    statement = select(Progress).where(Progress.id == user_progress.id)
    db_progress = session.exec(statement).first()
    db_progress.state_type = ProgressState.DONE
    db_progress.result = _result.model_dump(mode='json')
    session.add(db_progress)
    session.commit()
    session.refresh(db_progress)
    return _result