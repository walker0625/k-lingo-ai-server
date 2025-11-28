from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from sqlmodel import Field, SQLModel, Relationship
from enum import Enum

class UserInterview(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    interview_id: int = Field(foreign_key="interview.id")
    answer: str
    created_at: datetime = Field(default_factory=datetime.now)
    ## User Interview Relation
    interview: "Interview" = Relationship(back_populates="user_interview")
    user: "User" = Relationship(back_populates="user_interview")

class InterviewLevel(Enum):
    EASY = 1
    NORMAL = 2
    HARD = 3

class Interview(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    type_code: InterviewLevel
    eng: str
    kor: str
    eng_key: str
    kor_key: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    ## User Interview Relation
    user_interview: list["UserInterview"] = Relationship(back_populates="interview")#, link_model=UserInterview)

class InterviewCreate(BaseModel):
    type_code: InterviewLevel
    eng: str
    kor: str
    eng_key: str
    kor_key: str

class InterviewResponse(BaseModel):
    id: int
    type_code: InterviewLevel
    eng: str
    kor: str
    eng_key: str
    kor_key: str
    pronunciation: str | None = None
    created_at: datetime
    

class UserInterviewCreate(BaseModel):
    interview_id: int
    answer: str
    user_id: Optional[int]
    
class UserInterviewResponse(BaseModel):
    id: int
    user_id: int
    interview_id: int
    username: str
    interview_kor: str
    interview_eng: str
    interview_kor_key: str
    interview_eng_key: str
    answer: str
    created_at: datetime