import logging

import os
import uuid
import wave
import base64
from common.path import AUDIOS_DIR

from dotenv import load_dotenv
from fastapi import HTTPException

from elevenlabs.client import ElevenLabs

from api.chat.chat_service import ChatService
from api.listening.dto.listening_dto import ListeningResponse

logger = logging.getLogger(__name__)

class ListeningService:
    
    def __init__(self):
        load_dotenv()
        self.chat_service = ChatService()
    
    def make_audio_base64_from_text(self, audio_text: str) -> ListeningResponse:
        
        try:
            client = ElevenLabs(
                api_key=os.getenv("ELEVENLABS_API_KEY"),
            )
            
            audio = client.text_to_speech.convert(
                text=audio_text,
                voice_id="JBFqnCBsd6RMkjVDRZzb",
                model_id="eleven_flash_v2_5", # 가장 빠르고 저렴
                output_format="pcm_16000", # 16kHz, 가장 작음
            )
            
            # Generator를 bytes로 변환
            audio_bytes = b''.join(audio)

            # static/audios 디렉토리 생성 (없으면)
            os.makedirs(AUDIOS_DIR, exist_ok=True)

            # UUID로 파일명 생성
            filename = f"{uuid.uuid4()}.wav"
            output_path = os.path.join(AUDIOS_DIR, filename)

            with wave.open(output_path, "wb") as wav_file:
                wav_file.setnchannels(1)        # Mono
                wav_file.setsampwidth(2)        # 16-bit (2 bytes)
                wav_file.setframerate(16000)    # 16kHz (pcm_16000)
                wav_file.writeframes(audio_bytes)

            print(f"오디오 파일 저장 완료: {output_path}")

            # 저장된 전체 WAV 파일(+파일 정보)를 읽어옴
            with open(output_path, "rb") as f:
                full_wav_content = f.read()

            audio_base64 = base64.b64encode(full_wav_content).decode('utf-8')
            
            return ListeningResponse(audio_text=audio_text, audio_base64=audio_base64)
            
        except Exception as e:
            logger.error(f"오디오 파일 생성 실패: {e}")
            raise HTTPException(status_code=500, detail=str(e))