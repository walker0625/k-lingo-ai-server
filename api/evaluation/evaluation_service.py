import os
import json
import re

from loguru import logger
from fastapi import HTTPException
from api.evaluation.dto.evaluation_dto import EvaluationResponse

from openai import OpenAI

from langchain_core.prompts import load_prompt
from sqlmodel import select


from db.model.progress import Progress
from common.path import PROMPT_DIR

class EvaluationService:
    
    def __init__(self):
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    
    def _fetch_room_data(self, room_id: int, session: any) -> dict:
        
        logger.info(f"DB Fetching data for room_id: {room_id}")
        
        statement = select(Progress.result).where(Progress.room_id == room_id)
        results = session.exec(statement).all() 
        
        return results
        
    def _parse_llm_json(self, content: str) -> dict:
        """LLM의 응답(문자열)에서 JSON 부분만 추출하여 파싱합니다."""
        try:
            # 마크다운 코드 블록(```json ... ```) 제거
            cleaned = re.sub(r"```json\s*|\s*```", "", content).strip()
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"JSON Parsing Error: {e} \nContent: {content}")
            raise HTTPException(status_code=500, detail="AI 응답 형식이 올바르지 않습니다.")

    def evaluate_room(self, room_id: int, session: any) -> EvaluationResponse:
        
        # 1. DB에서 학습 데이터 조회
        user_data_dict = self._fetch_room_data(room_id, session)
        user_data_json_str = json.dumps(user_data_dict, ensure_ascii=False, indent=2)

        # 2. YAML에서 프롬프트 템플릿 로드
        template = load_prompt(PROMPT_DIR / "evaluation.yaml", encoding="utf-8")
    
        # 3. 데이터 주입 ({INPUT_JSON_DATA} 치환)
        final_prompt = template.format(INPUT_JSON_DATA = user_data_json_str)
        
        # 4. llm으로 결과 생성
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",  
                messages=[
                    {'role': 'system', 'content': 'You are a helpful assistant designed to output JSON.'}, # JSON 모드 사용 시 시스템 프롬프트에 JSON 언급 권장
                    {'role': 'user', 'content': final_prompt}
                ],
                temperature=0.2,
                # [중요] 강제로 올바른 JSON 포맷을 뱉게 하는 설정
                response_format={"type": "json_object"} 
            )
            
            content = response.choices[0].message.content
            
            # 5. 결과 파싱 및 반환
            result_dict = self._parse_llm_json(content)
            
            return EvaluationResponse(**result_dict)

        except Exception as e:
            logger.error(f"Ollama 호출 중 오류 발생: {e}")
            raise HTTPException(status_code=500, detail="AI 평가 생성 실패")