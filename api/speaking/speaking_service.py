import io
import os
import uuid
import shutil
import json 
from typing import List
import soundfile as sf

from common.path import INPUT_DIR
from common.ko_util import korean_to_english_pronunciation

from fastapi import UploadFile, HTTPException
from sqlmodel import create_engine, Session, select

from langchain_community.chat_models import ChatOllama
from agent.judge.workflow import create_assessment_graph
from agent.judge.states import AssessmentState

from db.model.user import User
from db.model.character import Character 
from db.model.user_store import UserCharacter
from db.model.interview import (
    Interview, UserInterview, InterviewLevel,
    InterviewCreate, InterviewResponse, UserInterviewCreate, UserInterviewResponse
)

from db.redis import StateStore

from api.listening.listening_service import ListeningService
from api.speaking.dto.speaking_dto import SpeakingResponse

from loguru import logger

DATABASE_URL="postgresql://klingo:klingo@100.100.53.32:5432/k-lingo"
engine = create_engine(DATABASE_URL)

from sqlmodel import SQLModel

try:
    SQLModel.metadata.create_all(engine)
except Exception as e:
    logger.warning(f"SQLModel create_all warning (expected if tables exist): {e}")

class SpeakingService:
    _asr_pipeline = None 
    
    def __init__(self):
        self.pipe = self._get_pipeline()
    
    # 최초 요청 시 로드하는 Lazy Singleton 메서드
    @classmethod
    def _get_pipeline(cls):
        if cls._asr_pipeline is None:
            
            # 💡 모델 로딩이 필요한 시점에야 import 실행 (Lazy Loading)
            from transformers import pipeline
            import torch
            
            try:
                # 💡 GPU 사용 여부 확인 및 장치 설정
                device = "cuda:0" if torch.cuda.is_available() else "cpu"
                logger.info(f"ASR Pipeline Device set to: {device} (Lazy Load)")
                
                # 모델 초기화
                cls._asr_pipeline = pipeline(
                    "automatic-speech-recognition", 
                    model="seastar105/whisper-small-komixv2",
                    device=device 
                )
                
                logger.info("ASR Pipeline successfully loaded.")
            except Exception as e:
                logger.error(f"FATAL ASR LOAD ERROR during lazy load: {e}")
                raise HTTPException(status_code=503, detail="AI 서비스 초기화 실패")

        return cls._asr_pipeline
    
    async def listen_speaking_and_judge(self, username, question, audio_file: UploadFile) -> SpeakingResponse:
        
        file_name = 'speaking_' + str(uuid.uuid4()) + '.wav'
        file_path = os.path.join(INPUT_DIR, file_name)
        
        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(audio_file.file, buffer)
            
            # soundfile로 오디오 로드
            audio_array, sampling_rate = sf.read(file_path)
            
            # 오디오 시간 계산
            audio_duration = len(audio_array) / sampling_rate
            
            logger.info(f"오디오 처리 중: {audio_duration:.2f}초")
            
            # 💡 싱글톤 self.pipe 사용 (이미 __init__에서 할당됨)
            result = self.pipe(audio_array)
            answer = result['text']
            
            assessment_data = self.judge_speaking(question, answer)
            
            grammar_score = assessment_data.get('grammar_result', {}).get('score')
            context_score = assessment_data.get('context_result', {}).get('context_score')
            final_overall_score = assessment_data.get('score_result', {}).get('score')
            final_feedback = assessment_data.get('final_feedback')
            
            response_object = SpeakingResponse(
                grammar_score=grammar_score,
                context_score=context_score,
                final_overall_score=final_overall_score,
                final_feedback=final_feedback
            )
            
            # redis에 result값 업데이트(저장값이 문자열이라 조회 -> 수정 -> 재저장으로 진행)
            redis = StateStore()
        
            ## 1. 조회
            stored_str = await redis.load_user_state("KLINGO-CURRENT", username)
            current_data = json.loads(stored_str)
        
            # 현재 평가 결과 객체 생성
            new_score_entry = {
                "score": final_overall_score,
                "desc": final_feedback
            }
        
            # 'result' 키가 없거나 딕셔너리가 아니면 초기화 (기존 데이터 호환성 유지)
            if "result" not in current_data or not isinstance(current_data["result"], dict):
                current_data["result"] = {}
                
            # 'result' 딕셔너리 안에 'scores' 키가 없거나 리스트가 아니면 초기화
            if "scores" not in current_data["result"] or not isinstance(current_data["result"]["scores"], list):
                current_data["result"]["scores"] = []
            
            # 새로운 점수 객체를 'result' -> 'scores' 리스트에 추가
            current_data["result"]["scores"].append(new_score_entry)
        
            state_data_json = json.dumps(current_data, ensure_ascii=False)

            await redis.save_user_state("KLINGO-CURRENT", username, state_data_json)
        
            return response_object
        
        except sf.LibsndfileError as e:
            logger.error(f"오디오 파일 읽기 실패: {e}")
            raise HTTPException(400, "유효하지 않은 WAV 파일입니다")
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)
                
    def generate_speaking_problem(self, user_id: int, interview_ids: List[int]) -> str:

        audio_data_list = []

        with Session(engine) as session:

            # 1. 쿼리 실행: ID 리스트에 해당하는 모든 인터뷰 항목을 조회
            statement = select(Interview).where(Interview.id.in_(interview_ids))
            interviews = session.exec(statement).all() 

            # 2. 결과가 없을 경우 예외 처리
            if not interviews:
                print("Error: Interview IDs not found or list is empty.")
                raise HTTPException(status_code=500, detail="No interviews found for the provided IDs.")

            # 3. 반복문 내에서 각 항목을 처리하고 결과를 리스트에 추가
            for interview in interviews:
                try:
                    # 3-1. TTS (Text-to-Speech) 서비스 호출
                    service = ListeningService() 
                    response = service.make_audio_base64_from_text(interview.kor)

                    # 3-2. 한국어 발음 표기 생성 (korean_to_english_pronunciation 함수 사용)
                    pronunciation = korean_to_english_pronunciation(interview.kor)

                    # 3-3. 각 항목을 원하는 JSON 'audio' 리스트의 형태로 가공
                    audio_item = {
                        "kor": interview.kor,
                        "eng": interview.eng,
                        "pronunciation": pronunciation,
                        "base64": response.audio_base64
                    }

                    audio_data_list.append(audio_item)

                    print(f"Processed: {interview.kor}")

                except Exception as e:
                    # 서비스 호출 중 발생하는 예외 처리
                    print(f"Error processing interview ID {interview.id}: {e}")
                    continue # 문제 발생 항목은 건너뛰고 다음 항목으로 진행

        # 4. 최종 JSON 구조 생성
        final_json_data = {
            "user_id": user_id,
            "audio": audio_data_list
        }

        # 5. 딕셔너리를 JSON 문자열로 변환하여 반환
        # ensure_ascii=False는 한글이 깨지지 않도록 합니다.
        return json.dumps(final_json_data, ensure_ascii=False)
    
    def judge_speaking(self, question: str, answer: str) -> SpeakingResponse:
        
        # 1. LLM 설정 (JSON 모드 및 낮은 온도 설정)
        try:
            # EXAONE 모델 사용 시 Ollama 호환성 및 JSON 모드 필수
            llm = ChatOllama(
                # qwen:14b-chat - 제미나이 추천
                # llama3:8b-instruct-q4_K_M - 제미나이 추천
                # qwen3-vl:8b - 응답이 없음 : 양자화 모델 변경 test           
                # deepseek-r1:8b - 응답이 없음 : 양자화 모델 변경 test           
                model="llama3:8b-instruct-q4_K_M",
                format="json",
                temperature=0.0,
                num_gpu=-1 # -1 : gpu 사용하도록 설정 / 0 : cpu 사용하도록 설정
            )
        except Exception as e:
            logger.error(f"❌ LLM 설정 실패: Ollama 서버가 실행 중인지, 모델이 설치되었는지 확인하세요. 에러: {e}")
            return

        # 2. 그래프 생성
        app = create_assessment_graph(llm)

        # 3. 입력 데이터 (AssessmentState의 모든 키를 포함하도록 초기화)
        inputs: AssessmentState = {
            "question": question,
            "user_text": answer,
            "context": "입국 심사",
            "target_level": 1, # TODO 동적으로 발화 레벨 추후 조정

            # [디버깅 핵심] 모든 상태를 None/초기값으로 명시
            "grammar_result": None,
            "context_result": None,
            "score_result": None,
            "final_feedback": None,
            "next_worker": None,
            "revision_count": 0
        }

        logger.info("========================================")
        logger.info("🚀 K-Lingo 평가 에이전트 실행 중...")
        logger.info(f"사용자 입력: {inputs['user_text']} (목표 {inputs['target_level']}급)")
        logger.info("========================================")

        # 4. 실행 및 결과 출력
        result = None
        
        try:
            # recursion_limit을 설정하여 무한 루프 시 강제 종료 (디버깅에 도움)
            result = app.invoke(inputs, config={"recursion_limit": 30}) 

            # 결과 출력 시 .get() 메서드를 사용하여 KeyError 방지
            final_score = result.get('score_result', {}).get('score', 'N/A')
            final_feedback = result.get('final_feedback', '피드백이 생성되지 않음')

            logger.info("========================================")
            logger.info(f"✅ 최종 평가 완료: 점수 {final_score}")
            logger.info(f"피드백: {final_feedback.strip()}")
            logger.info("========================================")

        except Exception as e:
            logger.error(f"\n[❌ LangGraph 실행 중 심각한 에러 발생]: {e}")
            logger.error("이 에러는 보통 LLM의 출력 문제나 그래프 구성 오류로 발생합니다.")
            if result:
                # 에러 발생 직전의 상태를 출력하여 어느 노드에서 멈췄는지 추적
                logger.error(f"마지막 상태: {result.get('next_worker', 'N/A')}")

        return result