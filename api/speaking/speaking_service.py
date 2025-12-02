import logging
import io
import os
import uuid
import shutil
import json 
from typing import List, Dict, Any
import soundfile as sf

from common.path import INPUT_DIR
from common.ko_util import korean_to_english_pronunciation

from fastapi import UploadFile, HTTPException
from sqlmodel import create_engine, Session, select

from db.model.user import User
from db.model.character import Character 
from db.model.user_store import UserCharacter
from db.model.interview import (
    Interview, UserInterview, InterviewLevel,
    InterviewCreate, InterviewResponse, UserInterviewCreate, UserInterviewResponse
)

from api.chat.chat_service import ChatService
from api.listening.listening_service import ListeningService
from api.speaking.dto.speaking_dto import SpeakingResponse

logger = logging.getLogger(__name__)

DATABASE_URL="postgresql://klingo:klingo@100.100.53.32:5432/k-lingo"
engine = create_engine(DATABASE_URL)

from sqlmodel import SQLModel

try:
    SQLModel.metadata.create_all(engine)
except Exception as e:
    logger.warning(f"SQLModel create_all warning (expected if tables exist): {e}")

class SpeakingService:
    _asr_pipeline = None 
    _chat_service = None
    
    def __init__(self):
        self.pipe = self._get_pipeline()
        self.chat_service = self._get_chat_service()
    
    # 최초 요청 시 로드하는 Lazy Singleton 메서드
    @classmethod
    def _get_pipeline(cls):
        if cls._asr_pipeline is None:
            # 🛑 이 블록이 실행될 때야 비로소 torch 로딩이 발생
            
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

    # 💡 ChatService 싱글톤 관리를 위한 메서드
    @classmethod
    def _get_chat_service(cls):
        if cls._chat_service is None:
            cls._chat_service = ChatService()
        return cls._chat_service

    def listen_speaking_and_answer(self, audio_file: UploadFile) -> SpeakingResponse:
        
        if audio_file.content_type != "audio/wav":
            raise HTTPException(400, "WAV 파일만 지원합니다")
        
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
            
            # TODO prompt 공통화 및 파일 관리 필요
            answer = self.chat_service.ask_question(system_prompt='너는 입국 심사관이야' , user_prompt=result['text'])
            
            return SpeakingResponse(answer=answer)
            
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