import os
import json
import asyncio
import requests
import time
import io
import numpy as np
from datetime import datetime
from typing import Dict, Any, List
from PIL import Image
from paddleocr import PaddleOCR
from dotenv import load_dotenv

# 쓰기 문제 생성용
from langchain_openai import ChatOpenAI
from sqlmodel import Session, select, desc

# DB 모델
from db.model.interview import Interview, UserInterview

load_dotenv()


class WriteService:
    def __init__(self):
        print("🔧 WriteService 초기화 시작...")

        # 1. PaddleOCR 초기화 (글자 인식용 - 복구됨)
        try:
            self.paddle = PaddleOCR(
                lang="korean",
                show_log=False,
                enable_mkldnn=False,
                use_gpu=False,
                use_angle_cls=True,
                ocr_version="PP-OCRv4",
            )
            print("✅ PaddleOCR 초기화 성공")
        except Exception as e:
            print(f"⚠️ PaddleOCR 초기화 실패: {e}")
            self.paddle = None

        self.naver_url = os.getenv("NAVER_OCR_URL")
        self.naver_key = os.getenv("NAVER_SECRET_KEY")

        # 2. LLM 초기화 (번역 및 발음 생성용)
        try:
            openai_key = os.getenv("OPENAI_API_KEY")
            if not openai_key:
                print("⚠️ OPENAI_API_KEY가 없습니다.")
                self.llm = None
            else:
                self.llm = ChatOpenAI(model="gpt-4o", temperature=0, api_key=openai_key)
                print("✅ ChatOpenAI 초기화 성공")
        except Exception as e:
            print(f"❌ ChatOpenAI 초기화 실패: {e}")
            self.llm = None

        print("✅ WriteService 초기화 완료")

    # =========================================================
    # OCR 관련 메서드
    # =========================================================
    def run_naver(self, file_bytes, filename):
        """네이버 OCR 호출"""
        try:
            data = {
                "images": [{"format": "jpg", "name": "demo"}],
                "requestId": datetime.now().strftime("%Y%m%d_%H%M%S"),
                "version": "V2",
                "timestamp": int(time.time() * 1000),
            }
            headers = {"X-OCR-SECRET": self.naver_key}
            resp = requests.post(
                self.naver_url,
                headers=headers,
                data={"message": json.dumps(data)},
                files=[("file", (filename, file_bytes))],
            )

            texts = [
                f["inferText"]
                for img in resp.json().get("images", [])
                for f in img.get("fields", [])
            ]
            return " ".join(texts)
        except Exception as e:
            print(f"❌ Naver OCR 실패: {e}")
            return "Naver OCR 실패"

    def run_paddle(self, file_bytes):
        """PaddleOCR 호출"""
        if not self.paddle:
            return "Paddle 모델 없음"
        try:
            img = np.array(Image.open(io.BytesIO(file_bytes)).convert("RGB"))
            result = self.paddle.ocr(img, cls=False)
            if not result or not result[0]:
                return ""
            return " ".join([line[1][0] for line in result[0]])
        except Exception as e:
            print(f"❌ Paddle OCR 실패: {e}")
            return ""

    async def process_immigration(self, file, mode="naver"):
        """
        [수정됨] 이미지에서 텍스트만 추출합니다.
        (기존의 ollama validation 로직은 제거했습니다.)
        """
        content = await file.read()

        if mode == "paddle":
            text = self.run_paddle(content)
        else:
            text = self.run_naver(content, file.filename)

        # 검증(Validation) 로직 삭제됨 -> 오직 텍스트만 반환
        return {"mode": mode, "text": text}

    # =========================================================
    # 쓰기 문제 생성 메서드
    # =========================================================
    async def _process_single_question(
        self, user_int: UserInterview, interview: Interview
    ) -> Dict[str, Any]:
        """
        개별 질문 처리: LLM을 호출하여 발음과 번역을 생성
        """
        kor_q = interview.kor if interview.kor else ""
        eng_q = interview.eng if interview.eng else ""
        eng_ans = user_int.answer if user_int.answer else ""

        result_data = {
            "word_data": {"kor": kor_q, "eng": eng_q, "pronunciation": ""},
            "answer": eng_ans,
            "answer_kor": "",
        }

        if not self.llm or not eng_ans:
            return result_data

        try:
            prompt = f"""
            You are a Korean language tutor.
            
            Input Data:
            - Korean Question: "{kor_q}"
            - User's Answer (English): "{eng_ans}"

            Task:
            1. Provide the Romanized pronunciation of the "Korean Question". 
               (Use standard Romanization, reflect sound changes like 'hap-ni-da' instead of 'hab-ni-da').
            2. Translate the "User's Answer" into natural, polite Korean (Honorifics).

            Output Format (JSON only, no markdown):
            {{
                "pronunciation": "...", 
                "answer_kor": "..."
            }}
            """

            response = await self.llm.ainvoke(prompt)
            content = response.content.strip()

            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            llm_result = json.loads(content)

            result_data["word_data"]["pronunciation"] = llm_result.get(
                "pronunciation", ""
            )
            result_data["answer_kor"] = llm_result.get("answer_kor", eng_ans)

        except Exception as e:
            print(f"⚠️ LLM 처리 실패 (ID: {user_int.id}): {e}")
            result_data["answer_kor"] = eng_ans

        return result_data

    async def get_writing_questions(
        self, session: Session, user_id: int
    ) -> Dict[str, Any]:

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

            results = session.exec(statement).all()

            if not results:
                return {"user_id": user_id, "question": []}

            # 2. 병렬 처리
            tasks = [
                self._process_single_question(user_int, interview)
                for user_int, interview in results
            ]

            processed_questions = await asyncio.gather(*tasks)

            print(f"✅ 총 {len(processed_questions)}개 문제 생성 완료")

            return {"user_id": user_id, "question": processed_questions}

        except Exception as e:
            print(f"❌ 서버 에러: {e}")
            import traceback

            traceback.print_exc()
            return {"user_id": user_id, "question": []}
