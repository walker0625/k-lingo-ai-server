## Processing user character and equipment purchases

import random
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from db.session import  SessionDep, get_current_active_user
from db.model.user import User
from db.model.interview import (
    Interview, UserInterview, InterviewLevel,
    InterviewCreate, InterviewResponse, UserInterviewCreate, UserInterviewResponse
)
## logger
from loguru import logger
## user router
router = APIRouter()

# Routes
@router.get("/hello", response_model=list[InterviewResponse])
def get_my_interviews(
    session : SessionDep, 
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """접속한 사용자의 초기 인터뷰 리스트, 이전 히스토리 참고하여 랜덤 생성"""
    logger.info(current_user)
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found"
        )
    ## 1. user interview list, all interview list
    _user_interview_list = current_user.user_interview
    ## user interview list의 각각의 interview 정보를 가져와 변경
    user_interview_list = []
    for _user_interview in _user_interview_list:
        user_interview_list.append(InterviewResponse.model_validate(_user_interview.interview, from_attributes=True))
    ## transform Interview SQLModel Class To InterviewResponse BaseModel    
    _all_interview_list = session.exec(select(Interview)).all()
    all_interview_list = [InterviewResponse.model_validate(item, from_attributes=True) for item in _all_interview_list]
    ## 2. exclude previous interview list
    sample_list = sampling_interview_list(all_interview_list, user_interview_list)
    return sample_list
 
@router.post("/answer/post", response_model=list[UserInterviewResponse],
             status_code=status.HTTP_201_CREATED)
def add_user_answer(
    answers: list[UserInterviewCreate], session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """
        사용자 인터뷰 답변 입력 처리
    """
    ## user checker
    logger.info(current_user)
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found"
        )
    _user = current_user
    logger.info(answers)
    _new_answers = []
    for _answer in answers:
        _interview = session.get(Interview,_answer.interview_id)
        if not _interview:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Interview{_answer.interview_id} not found"
            )
        ## Create new item
        _new_answer = UserInterview(
            user_id = _user.id,
            interview_id = _answer.interview_id,
            answer = _answer.answer
        )
        _new_answers.append(_new_answer)
    results = []
    for _new_answer in _new_answers:
        session.add(_new_answer)
        session.commit()
        session.refresh(_new_answer)
        results.append(UserInterviewResponse(
            id = _new_answer.id,
            user_id = _new_answer.user_id,
            interview_id = _new_answer.interview_id,
            username = _new_answer.user.username,
            interview_kor = _new_answer.interview.kor,
            interview_eng = _new_answer.interview.eng,
            interview_kor_key = _new_answer.interview.kor_key,
            interview_eng_key = _new_answer.interview.eng_key,
            answer = _new_answer.answer,
            created_at = _new_answer.created_at
        ))
    return results

@router.get("/get/{level}", response_model=list[InterviewResponse])
def get_interview(level:int, session : SessionDep):
    """레벨에 해당하는 인터뷰 리스트 (상:3, 중:2, 하:1)"""
    statement = select(Interview).where(Interview.type_code == InterviewLevel(level))
    result = session.exec(statement).all()
    return result

@router.post("/post", response_model=InterviewResponse, status_code=status.HTTP_201_CREATED)
def add_interview(answer: InterviewCreate, session: SessionDep):
    """
        사용자 인터뷰 기초 데이터 입력 처리
    """
    ## Create new item
    new_answer = Interview(
        type_code = answer.type_code,
        eng = answer.eng,
        kor = answer.kor,
        eng_key = answer.eng_key,
        kor_key = answer.kor_key
    )
    session.add(new_answer)
    session.commit()
    session.refresh(new_answer)
    return new_answer

def sampling_interview_list(
    all_interview_list:list[InterviewResponse], 
    user_interview_list:list[InterviewResponse],
    max_number = 5
):
    ### 전체 인터뷰 리스트에서 최대 5개가져오기
    ### 유저의 인터뷰 히스토리 제외하고 레벨 1번부터 시작해서 순서대로 최대 5개까지 가져오기
    ## exclude user interview list from all interview list
    # target_number = 5
    all_sample_list = [item for item in all_interview_list if item not in user_interview_list]
    target_list = []
    ## level 1 list
    sample_list = [item for item in all_sample_list if item.type_code == InterviewLevel.EASY]
    ## pick 5 items in level 1 list
    sample_number = max_number if len(sample_list) >= max_number else len(sample_list)
    target_list = random.sample(sample_list,sample_number)
    ## if < 5, pick remaining list
    if len(target_list) < max_number:
        sample_number = max_number - len(target_list)
        print(sample_number, max_number, len(target_list))
        sample_list = [item for item in all_sample_list if item.type_code == InterviewLevel.NORMAL]
        sample_number = sample_number if len(sample_list) >= sample_number else len(sample_list)
        target_list.extend(random.sample(sample_list,sample_number))
    ## if < 5, pick remaining list
    if len(target_list) < max_number:
        sample_number = max_number - len(target_list)
        print(sample_number, max_number, len(target_list))
        sample_list = [item for item in all_sample_list if item.type_code == InterviewLevel.HARD]
        sample_number = sample_number if len(sample_list) >= sample_number else len(sample_list)
        target_list.extend(random.sample(sample_list,sample_number))
    return target_list