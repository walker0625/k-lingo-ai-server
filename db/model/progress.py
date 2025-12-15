## scenario, quest progress state table
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel
from sqlmodel import Field, SQLModel, func
from enum import Enum
from sqlalchemy import Column, Enum as SQLEnum
from sqlalchemy.types import JSON
from db.model.scenario import StageType
from sqlalchemy.orm import column_property

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
    room_id: int  ## 클라이언트에서 생성된 게임방 번호
    stage_type: StageType = Field(
        sa_column=Column(
            SQLEnum(StageType, name="stage_type", create_type=True),
            nullable=False
        )
    )
    state_type: ProgressState = Field(default=ProgressState.START)
    scenario: dict[str,Any] = Field(default={}, sa_column=Column(JSON))
    result: dict[str,Any] = Field(default={}, sa_column=Column(JSON))
    average_score: float = Field(default=0.0)
    # top_n: Optional[float] = Field(
    #     default=None,
    #     # sa_column=column_property(
    #     #     func.cal_stage_top_percent(id,scenario_id,stage_type),
    #     #     deferred=True
    #     # ),
    #     sa_column_kwargs={
    #         # "server_default": func.now(),
    #         "onupdate": func.cal_stage_top_percent(id,scenario_id,stage_type)
    #     }
    # )
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(
        default_factory=datetime.now,
        sa_column_kwargs={
            "server_default": func.now(),
            "onupdate": func.now()
        }
    )
    
class ProgressResponse(BaseModel):
    id: int
    user_id: int
    scenario_id: int
    room_id: int  ## 클라이언트에서 생성된 게임방 번호
    stage_type: StageType
    state_type: ProgressState
    scenario: dict[str,Any]
    result: dict[str,Any]
    average_score: float
    # top_n: Optional[float] = 0.0
    created_at: datetime
    updated_at: datetime
    
class ProgressCreate(BaseModel):
    user_id: int
    scenario_id: int
    stage_type: StageType
    scenario: dict[str,Any]
