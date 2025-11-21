import os, logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from db.session import  SessionDep
from db.model.scenario import (
    Scenario, Stage, StageType, ReadQuest, QuestReadInfo, QuestLevel,
    quest_words, gen_read_quest
)

## logger
logger = logging.getLogger("app")
## user router
router = APIRouter()

# Routes
@router.get("/{scenario_id}/{stage_id}/{level}", response_model=QuestReadInfo)
def get_stage(scenario_id:int, stage_id:int, level:int, session : SessionDep):
    """
        시나리오 ID, 스테이지 ID, 레벨로 스테이지 퀘스트 정보 생성
    """
    scenario = session.get(Scenario, scenario_id)
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found"
        )
    stages = scenario.stages
    logger.info("**** stage info")
    logger.info(stages)
    if not stages and len(stages) <= 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stage not found"
        )
    quest = stages[0].quest
    logger.info(quest)
    quest_info = gen_read_quest([ReadQuest(**q) for q in quest], QuestLevel.EASY)
    # quest_words([ReadQuest(**q) for q in quest], StageType.READING, level)
    logger.info(quest_info)
    return quest_info

# Routes
@router.get("/{scenario_title}/{stage_title}/{level}")
def get_stage_by_title(scenario_title:str, stage_title:str, level:int, session : SessionDep):
    return {"result":"ok"}