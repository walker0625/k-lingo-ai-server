import json
from fastapi import APIRouter, HTTPException, status, Depends
from sqlmodel import select, Session, text
from db.session import  SessionDep, get_current_active_user
from typing import Annotated
from db.model.user import User
from db.model.scenario import (
    Scenario,ScenarioResponse, Stage, StageType, QuestLevel, ReadingQuest, ListeningQuest
)
from api.general.service.scenario_service_RL import gen_read_or_listen_quest
from api.general.service.scenario_dto import QuestBase, QuestReadInfo, QuestListenInfo, QuestWriteInfo, QuestSpeakInfo
from db.redis import StateStore
from db.model.progress import ProgressResponse, ProgressState, Progress #, ProgressCreate
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
        (scenario view 용)시나리오 리스트
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
        (scenario view 용)시나리오 리스트
    """
    statement = select(Stage)
    results = session.exec(statement).all()
    return results

@router.get("/{scenario_id}/{stage_id}/{level}", response_model=QuestBase)
def get_stage(scenario_id:int, stage_id:int, level:int, session : SessionDep):
    """
        (정보 확인용)시나리오 ID, 스테이지 ID, 레벨로 스테이지 퀘스트 정보 가져오기
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

# @router.get("/stages/{scenario_id}/{stage_type}/{level}", response_model=QuestBase)
# def get_stage_by_type(scenario_id:int, stage_type:int, level:int, session : SessionDep):
#     """
#         (Depricate)시나리오 ID, 스테이지 유형(읽기:1, 듣기:2, 쓰기:3, 말하기:4), 레벨로 스테이지 퀘스트 정보 가져오기
#     """
#     _stage_type = StageType(stage_type)
#     statement = select(Stage).where(
#         Stage.scenario_id == scenario_id,
#         Stage.type_code == _stage_type
#     )
#     stages =  session.exec(statement).all()
#     if not stages and len(stages) <= 0:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Stage not found"
#         )
#     quest = stages[0].quest
#     quest_info = gen_read_or_listen_quest(
#         _stage_type,
#         [ReadingQuest(**q) for q in quest] ## 타입에 따른 바인딩
#             if _stage_type == StageType.READING
#             else [ListeningQuest(**q) for q in quest],
#         QuestLevel(level))
#     quest_info.index = scenario_id ## 시나리오 번호로 변경하여 전송
#     return quest_info

@router.get("/stages/redis/{room_id}/{scenario_id}/{stage_type}/{level}", 
            response_model=QuestReadInfo | QuestListenInfo | QuestWriteInfo | QuestSpeakInfo)
async def get_stage_by_type_with_redis(
    room_id:int, scenario_id:int, stage_type:int, level:int,
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
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Need to set up redis"
        )
    saved_progress = await store.load_progress_state(current_user.username)
    if saved_progress:
        user_progress = ProgressResponse(**saved_progress)
        ## 스테이지가 진행 상태인 다른 스테이지의 진행 중인 시나리오가 있는 경우 해당 시나리오 전송
        if user_progress.state_type != ProgressState.DONE and user_progress.state_type != ProgressState.REPORT:
            # user_progress.scenario_id == scenario_id and user_progress.stage_type == StageType(stage_type) and \
            ## 타입 체크(기존의 진행중인 것이 있으면 진행중에 정보 그대로 리턴)
            if user_progress.stage_type == StageType.READING:
                return QuestReadInfo.model_validate(user_progress.scenario, from_attributes=True)
            elif user_progress.stage_type == StageType.LISTENING:
                return QuestListenInfo.model_validate(user_progress.scenario, from_attributes=True)
            elif user_progress.stage_type == StageType.WRITING:
                return QuestWriteInfo.model_validate(user_progress.scenario, from_attributes=True)
            elif user_progress.stage_type == StageType.SPEAKING:
                return QuestSpeakInfo.model_validate(user_progress.scenario, from_attributes=True)
    logger.info(f"****** stage type : {_stage_type}")
    quest_info = None
    if _stage_type == StageType.READING or _stage_type == StageType.LISTENING:
        ## 저장된 것이 없는 경우 Reading, Listening => 생성 후 리턴
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
        quest_info.room_id = room_id   ## 해당 게임룸 번호로 변경
    else:
        ## 저장된 것이 없는 경우 Writing, Speaking => Redis 사전 생성 정보 조회 후 리턴
        quest_info = await store.load_ready_stage(_stage_type,current_user.username)
        logger.info(quest_info)
            
    progress = Progress(
        user_id=current_user.id,
        scenario_id=scenario_id,
        room_id=room_id,
        stage_type=StageType(stage_type),
        scenario=quest_info.model_dump(mode='json') \
            if _stage_type == StageType.READING or _stage_type == StageType.LISTENING else quest_info
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
async def stage_result(result: ProgressRLInfo, session: SessionDep):
    """
        Reading, Listening Stage 결과 처리 ( state type은 디폴트값으로 진행 )
    """
    # Check if user exists
    statement = select(User).where(User.id == result.user_id)
    existing_user = session.exec(statement).first()
    if not existing_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    # Check redis
    store = StateStore()
    if not store:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Need to set up Redis"
        )
    saved_progress = await store.load_progress_state(existing_user.username)
    if not saved_progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Your Scenario not found"
        )
    ## scenario id, stage type 체크
    user_progress = ProgressResponse(**saved_progress)
    logger.info(user_progress)
    ## stage type Reading, Listening 아니면 잘못된 타입 에러
    if user_progress.stage_type != StageType.READING and user_progress.stage_type != StageType.LISTENING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{StageType.READING} or {StageType.LISTENING} is only available"
        )    
    
    ## 잘못된 scenario, type이 다르면 오류 발생    
    if user_progress.scenario_id != result.scenario_id or user_progress.stage_type != result.stage_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Your Scenario({result.scenario_id}) Stage({result.stage_type}) not found"
        )    
    ## 평가 result
    _clear_score = evaluate(EvalutionType.CLEAR_TIME,result.result_time)
    _wrong_score = evaluate(EvalutionType.WRONG_INDEX,len(result.wrong_idx))
    _total_score = _clear_score+_wrong_score
    # update progress result
    _result = ProgressResult(
        grade=grade(_total_score),
        average_score=_total_score,
        top_percent=None ## 구현 필요 => 해당 시나리오, 스테이지에 대한 완료 결과만 읽어 (소팅인덱스+1)/갯수로 결과 생성
    )
    ## 결과 및 완료 처리
    user_progress.result = _result.model_dump(mode='json')
    user_progress.state_type = ProgressState.DONE
    await store.save_progress_state(existing_user.username,user_progress)
    ## DB의 progress 정보 조회 후 업데이트(progress id 어떻게 체크??)
    statement = select(Progress).where(Progress.id == user_progress.id)
    db_progress = session.exec(statement).first()
    db_progress.state_type = ProgressState.DONE
    db_progress.result = _result.model_dump(mode='json')
    db_progress.average_score = _result.average_score  ## 스테이지 점수 저장, top percent 계산시 사용
    session.add(db_progress)
    session.commit()
    session.refresh(db_progress)
    ## Top 계산
    _result.top_percent = cal_stage_top_percent(session, db_progress.id, 
            db_progress.scenario_id, db_progress.stage_type, db_progress.average_score);
    return _result

def cal_stage_top_percent(session:Session, progress_id:int, 
        scenario_id:int, stage_type:StageType, average_score:float=0.0) -> float:
    ## Progress 처리 결과에 대한 Top 퍼센트 계산 count / total count
    total_count_sql = f"""
        SELECT COUNT(*) cnt FROM progress
        WHERE  scenario_id = {scenario_id} and stage_type = '{stage_type.name}'
	    and (state_type = 'DONE' or state_type = 'REPORT');"""
    count_sql = f"""
        SELECT COUNT(*) cnt FROM progress
        WHERE  scenario_id = {scenario_id} and stage_type = '{stage_type.name}' and average_score < {average_score}
	    and (state_type = 'DONE' or state_type = 'REPORT');"""
    # order_sql = f"""SELECT r FROM (
    #     SELECT id, RANK() OVER (PARTITION BY scenario_id, stage_type
    #                ORDER BY average_score DESC) AS r
    #     FROM progress
    #     WHERE scenario_id = {scenario_id} and stage_type = '{stage_type.name}'
    #         and (state_type = 'DONE' or state_type = 'REPORT')
    # ) AS ranked_scores
    # WHERE id = {progress_id};"""
    total_count_result = session.exec(text(total_count_sql)).first()
    count_result = session.exec(text(count_sql)).first()
    if not total_count_result or len(total_count_result) <= 0:
        _total_count = 0
    else:
        _total_count = total_count_result[0]
    if not count_result or len(count_result) <= 0:
        _count = 0.0
    else:
        _count = count_result[0]
    if _count <= 0.0 or _total_count <= 0.0:
        result = 100.0
    else:
        result = round((_total_count - _count -1) / _total_count, 3)
    return result