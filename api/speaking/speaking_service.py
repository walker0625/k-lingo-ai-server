import logging
import io
import os
import uuid
import shutil
import soundfile as sf
# 💡 transformers, pipeline import는 함수 내부로 옮겨 초기 로딩을 방지합니다.

from common.path import INPUT_DIR
from fastapi import UploadFile, HTTPException

from api.chat.chat_service import ChatService
from api.speaking.dto.speaking_dto import SpeakingResponse

logger = logging.getLogger(__name__)

class SpeakingService:
    # 💡 클래스 변수를 사용하여 모델과 ChatService를 싱글톤으로 관리
    _asr_pipeline = None 
    _chat_service = None
    
    def __init__(self):
        # 인스턴스 변수에 싱글톤 객체 할당
        self.pipe = self._get_pipeline()
        self.chat_service = self._get_chat_service()
    
    # 💡 ASR 파이프라인을 최초 요청 시 로드하는 Lazy Singleton 메서드
    @classmethod
    def _get_pipeline(cls):
        if cls._asr_pipeline is None:
            # 🛑 이 블록이 실행될 때야 비로소 torch 로딩이 발생합니다.
            
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