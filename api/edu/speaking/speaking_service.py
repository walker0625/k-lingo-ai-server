from transformers import pipeline
import logging
from fastapi import UploadFile, HTTPException
import io
import soundfile as sf

from api.chat.chat_service import ChatService
from api.edu.speaking.dto.speaking_dto import SpeakingResponse

logger = logging.getLogger(__name__)

class SpeakingService:
    
    def __init__(self):
        self.chat_service = ChatService()
    
    def listen_speaking_and_answer(self, audio_file: UploadFile) -> SpeakingResponse:
        
        # WAV 파일 체크
        if audio_file.content_type != "audio/wav":
            raise HTTPException(400, "WAV 파일만 지원합니다")
        
        # 메모리에서 직접 읽기
        audio_bytes = audio_file.file.read()
        
        try:
            # soundfile로 오디오 로드
            audio_array, sampling_rate = sf.read(io.BytesIO(audio_bytes))
            
            # 오디오 시간 계산
            audio_duration = len(audio_array) / sampling_rate
            
            logger.info(f"오디오 처리 중: {audio_duration:.2f}초")
            
            # Whisper 파이프라인 실행
            pipe = pipeline(
                "automatic-speech-recognition", 
                model="seastar105/whisper-small-komixv2"
            )
            result = pipe(audio_array)
            
            # TODO prompt 공통화 및 파일 관리 필요
            answer = self.chat_service.ask_question(system_prompt='너는 입국 심사관이야' , user_prompt=result['text'])
            
            return SpeakingResponse(answer=answer)
            
        except sf.LibsndfileError as e:
            logger.error(f"오디오 파일 읽기 실패: {e}")
            raise HTTPException(400, "유효하지 않은 WAV 파일입니다")