import os
import uuid
import base64
import io  
import soundfile as sf
import librosa # 추가: 리샘플링을 위해 필요
from common.path import AUDIOS_DIR

from dotenv import load_dotenv
from fastapi import HTTPException

from openai import OpenAI

from api.chat.chat_service import ChatService
from api.listening.dto.listening_dto import ListeningResponse
from loguru import logger

class ListeningService:
    
    def __init__(self):
        load_dotenv()
        self.chat_service = ChatService()
        self.client = OpenAI()
    
    def make_audio_base64_from_text(self, audio_text: str) -> ListeningResponse:
        
        try:
            # 1. OpenAI TTS API 호출
            response = self.client.audio.speech.create(
                model="gpt-4o-mini-tts",
                voice="echo",           
                input=audio_text,
                response_format="wav"   
            )
            
            # 바이너리 데이터 추출 (이 시점에서는 24kHz)
            audio_bytes = response.content

            # static/audios 디렉토리 생성
            os.makedirs(AUDIOS_DIR, exist_ok=True)

            # UUID로 파일명 생성
            filename = f"{uuid.uuid4()}.wav"
            output_path = os.path.join(AUDIOS_DIR, filename)

            # ================= [핵심 수정 부분] =================
            # 2. 리샘플링 및 저장 (24kHz -> 16kHz)
            # io.BytesIO를 사용하여 메모리 상의 데이터를 librosa로 로드합니다.
            # sr=16000: 강제로 16kHz로 변환하여 로드
            y, sr = librosa.load(io.BytesIO(audio_bytes), sr=16000, mono=True)
            
            # 3. 16-bit PCM 포맷으로 저장 (언리얼/MetaHuman 표준)
            # subtype='PCM_16'이 16비트 깊이를 보장합니다.
            sf.write(output_path, y, 16000, subtype='PCM_16')
            
            logger.info(f"오디오 변환 및 저장 완료 (16kHz, 16bit): {output_path}")
            # ===================================================

            # 저장된 파일을 읽어서 Base64 인코딩
            with open(output_path, "rb") as f:
                full_wav_content = f.read()

            audio_base64 = base64.b64encode(full_wav_content).decode('utf-8')
            
            return ListeningResponse(audio_text=audio_text, audio_base64=audio_base64)
            
        except Exception as e:
            logger.error(f"오디오 파일 생성 실패: {e}")
            raise HTTPException(status_code=500, detail=str(e))