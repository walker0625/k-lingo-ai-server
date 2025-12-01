## scenario, quest progress state table
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel
from sqlmodel import Field, SQLModel
from enum import Enum
from sqlalchemy.types import JSON
from sqlalchemy import Column
from .scenario import StageType

class ProgressState(Enum):
    INIT = 0    ## 시나리오 스테이지 생성 상태, 시작전
    START = 1   ## 시나리오 스테이지 시작 상태
    DOING = 2   ## 시나리오 스테이지 진행 상태 (WRITING, SPEAKING)
    DONE  = 3   ## 시나리오 스테이지 결과 처리 상태(종료 상태)
    REPORT = 4  ## 시나리오 전체 종료 상태(리포트 완료)

# Models
class Progress(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id : int = Field(foreign_key="user.id")
    scenario_id: int = Field(foreign_key="scenario.id")
    stage_type: StageType
    state_type: ProgressState = Field(default=ProgressState.START)
    scenario: dict[str,Any] = Field(default={}, sa_column=Column(JSON))
    result: dict[str,Any] = Field(default={}, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
class ProgressResponse(BaseModel):
    id: int
    user_id: int
    scenario_id: int
    stage_type: StageType
    state_type: ProgressState
    scenario: dict[str,Any]
    result: dict[str,Any]
    created_at: datetime
    updated_at: datetime
    
class ProgressCreate(BaseModel):
    user_id: int
    scenario_id: int
    stage_type: StageType
    scenario: dict[str,Any]
