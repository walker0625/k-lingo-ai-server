## Processing user character and equipment purchases
import os, random, json
from langchain_openai import ChatOpenAI
from typing import Annotated, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlmodel import Session, select, desc
from common.ko_util import korean_to_english_pronunciation
from db.session import  SessionDep, get_current_active_user
from db.redis import StateStore
from db.model.user import User
from db.model.scenario import StageType
from db.model.interview import (
    Interview, UserInterview, InterviewLevel,
    InterviewCreate, InterviewResponse, UserInterviewCreate, UserInterviewResponse
)
from api.general.service.scenario_dto import QuestWriteInfo, WriteData, QuestSpeakInfo, SpeakData
from api.general.scenario import QuestLevel
from api.speaking.speaking_service import SpeakingService

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

@router.post("/answer/post/{rooom_id}", response_model=list[UserInterviewResponse],
            status_code=status.HTTP_201_CREATED)
async def add_user_answer(
    answers: list[UserInterviewCreate],
    room_id: int, session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_user)],
    background_task: BackgroundTasks
):
    """
        사용자 인터뷰 답변 입력 처리(user는 현재 로그인한 유저로 처리)
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

        ## Writing Stage & Redis 처리
        background_task.add_task(gen_write_stage_to_redis,session,room_id,_user)
        ## Speaking Stage & Redis 처리
        background_task.add_task(gen_speak_stage_to_redis,results,room_id,_user)
        
    return results
## generate writing stage & save redis
async def gen_write_stage_to_redis(session: Session, room_id:int, current_user: User):
    try:
        logger.info("****** generate write stage")
        write_problem_json = get_writing_questions(session, current_user.id)
        store = StateStore()
        
        ## write info redis 저장
        questWriteInfo = QuestWriteInfo(
            index=1, difficulty=QuestLevel.EASY,
            room_id=room_id,
            question=[]
        )
        for info in write_problem_json['question']:
            questWriteInfo.question.append(
                WriteData.model_validate(info, from_attributes=True)
            )
        logger.info(questWriteInfo)
        await store.save_ready_stage(StageType.WRITING, current_user.username, questWriteInfo.model_dump_json())
        logger.info("****** generate write stage")
    except Exception as e:
        logger.warning(e)
## generate speaking stage & save redis
async def gen_speak_stage_to_redis(user_interview:list[UserInterviewResponse],
                                    room_id:int, current_user: User):
    try:
        logger.info("****** generate speak stage")
        user_id = current_user.id
        interview_ids = [interview.interview_id for interview in user_interview]
        speaking_problem_json = SpeakingService().generate_speaking_problem(user_id, interview_ids)
        store = StateStore()

        logger.info(speaking_problem_json)
        ## speak info redis 저장
        questSpeakInfo = QuestSpeakInfo(
            index=1, difficulty=QuestLevel.EASY,
            room_id=room_id,
            audio=[]
        )
        for info in json.loads(speaking_problem_json)['audio']:
            speak_data = SpeakData.model_validate(info, from_attributes=True)
            speak_data.voice_data = info['base64']
            questSpeakInfo.audio.append(speak_data)
        logger.info(questSpeakInfo)
        await store.save_ready_stage(StageType.SPEAKING, current_user.username, questSpeakInfo.model_dump_json())
        logger.info("****** generate speak stage")
    except Exception as e:
        logger.warning(e)

# @router.get("/get/{level}", response_model=list[InterviewResponse])
# def get_interview(level:int, session : SessionDep):
#     """레벨에 해당하는 인터뷰 리스트 (상:3, 중:2, 하:1)"""
#     statement = select(Interview).where(Interview.type_code == InterviewLevel(level))
#     result = session.exec(statement).all()
#     return result

# @router.get("/answer/get/{user_id}", response_model=list[UserInterviewResponse])
# def get_user_answer(user_id:int, session : SessionDep, level:int = 0):
#     """레벨에 해당하는 인터뷰 리스트 (상:3, 중:2, 하:1, 전체 : 0)"""
#     _user: User | None = session.get(User, user_id)
#     if not _user:
#         raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail=f"User not found"
#             )
#     _answeres = _user.user_interview
#     result = []
#     for _answer in _answeres:
#         _interview = _answer.interview
#         if level != 0 and level != _interview.type_code != InterviewLevel(level):
#             continue
#         result.append(UserInterviewResponse(
#             id = _answer.id, user_id=_user.id, interview_id=_answer.interview_id,
#             username=_user.username, interview_kor=_interview.kor, interview_eng=_interview.eng,
#             interview_kor_key=_interview.kor_key, interview_eng_key=_interview.eng_key,
#             answer=_answer.answer, created_at=_answer.created_at
#         ))
#     return result

# @router.post("/post", response_model=InterviewResponse, status_code=status.HTTP_201_CREATED)
# def add_interview(answer: InterviewCreate, session: SessionDep):
#     """
#         사용자 인터뷰 기초 데이터 입력 처리
#     """
#     ## Create new item
#     new_answer = Interview(
#         type_code = answer.type_code,
#         eng = answer.eng,
#         kor = answer.kor,
#         eng_key = answer.eng_key,
#         kor_key = answer.kor_key
#     )
#     session.add(new_answer)
#     session.commit()
#     session.refresh(new_answer)
#     return new_answer

# def sampling_interview_list(
#     all_interview_list:list[InterviewResponse], 
#     user_interview_list:list[InterviewResponse],
#     max_number = 5
# ):
#     ### 전체 인터뷰 리스트에서 최대 5개가져오기
#     ### 유저의 인터뷰 히스토리 제외하고 레벨 1번부터 시작해서 순서대로 최대 5개까지 가져오기
#     ## exclude user interview list from all interview list
#     # target_number = 5
#     all_sample_list = [item for item in all_interview_list if item not in user_interview_list]
#     target_list = []
#     ## level 1 list
#     sample_list = [item for item in all_sample_list if item.type_code == InterviewLevel.EASY]
#     ## pick 5 items in level 1 list
#     sample_number = max_number if len(sample_list) >= max_number else len(sample_list)
#     target_list = random.sample(sample_list,sample_number)
#     ## if < 5, pick remaining list
#     if len(target_list) < max_number:
#         sample_number = max_number - len(target_list)
#         print(sample_number, max_number, len(target_list))
#         sample_list = [item for item in all_sample_list if item.type_code == InterviewLevel.NORMAL]
#         sample_number = sample_number if len(sample_list) >= sample_number else len(sample_list)
#         target_list.extend(random.sample(sample_list,sample_number))
#     ## if < 5, pick remaining list
#     if len(target_list) < max_number:
#         sample_number = max_number - len(target_list)
#         print(sample_number, max_number, len(target_list))
#         sample_list = [item for item in all_sample_list if item.type_code == InterviewLevel.HARD]
#         sample_number = sample_number if len(sample_list) >= sample_number else len(sample_list)
#         target_list.extend(random.sample(sample_list,sample_number))
#     return target_list


# =========================================================
# 쓰기 문제 생성 메서드 (유지)
# =========================================================
def _process_single_question(
    user_int: UserInterview, interview: Interview
) -> Dict[str, Any]:
    
    openai_key = os.getenv("OPENAI_API_KEY")
    
    llm = ChatOpenAI(
        model="gpt-4o", 
        temperature=0, 
        api_key=openai_key,
        # 아래 model_kwargs를 사용하면 LLM이 JSON을 출력하도록 강제됩니다.
        model_kwargs={"response_format": {"type": "json_object"}}
    )
    
    """
    개별 질문 처리: 발음과 번역을 생성 (동기 함수)
    """
    kor_q = interview.kor if interview.kor else ""
    eng_q = interview.eng if interview.eng else ""
    eng_ans = user_int.answer if user_int.answer else ""
    
    prompt = f"""
        You are a Korean language tutor.

        Input Data:
        - Korean Question: "{kor_q}"
        - User's Answer (English): "{eng_ans}"      
        Task:
        1. Translate the "User's Answer" into natural, polite Korean (Honorifics).      
        Output Format (JSON only, no markdown):
        {{
                    "answer_kor": "..."
        }}
        """

    response = llm.invoke(prompt)
    content = response.content.strip()
    
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    
    llm_result = json.loads(content)
    
    result_data = {
        "word_data": {"kor": kor_q, "eng": eng_q, "pronunciation": ""},
        "answer": eng_ans,
        "answer_kor": ""
    }
    
    result_data["answer_kor"] = llm_result.get("answer_kor", eng_ans)
    
    try:
        result_data["word_data"]["pronunciation"] = korean_to_english_pronunciation(kor_q)
    except NameError:
        # korean_to_english_pronunciation 함수가 정의되지 않은 경우를 대비
        result_data["word_data"]["pronunciation"] = f"Pronunciation for: {kor_q}" 
        
    return result_data

def get_writing_questions(
    session: Session, user_id: int
) -> Dict[str, Any]:
    """
    쓰기 문제 생성 (동기 함수로 변환)
    """
    print(f"\n{'='*60}")
    print(f"📝 쓰기 문제 생성 요청 (User ID: {user_id})")
    try:
        # 1. DB 쿼리: created_at 기준 내림차순
        statement = (
            select(UserInterview, Interview)
            .join(Interview, UserInterview.interview_id == Interview.id)
            .where(UserInterview.user_id == user_id)
            .order_by(desc(UserInterview.created_at))
            .limit(5)
        )
        
        # 동기 세션에서 쿼리 실행 (session.exec().all()은 동기적으로 결과를 반환)
        results = session.exec(statement).all()
        
        if not results:
            print(f"✅ User ID {user_id}에 대한 결과 없음")
            return {"user_id": user_id, "question": []}
            
        # 2. 순차적 동기 처리
        processed_questions = []
        for user_int, interview in results:
            processed_questions.append(
                _process_single_question(user_int, interview)
            )
            
        print(f"✅ 총 {len(processed_questions)}개 문제 생성 완료")
        return {"user_id": user_id, "question": processed_questions}
        
    except Exception as e:
        print(f"❌ 서버 에러: {e}")
        import traceback
        traceback.print_exc()
        return {"user_id": user_id, "question": []}