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
from difflib import SequenceMatcher

# 쓰기 문제 생성용
from langchain_openai import ChatOpenAI
from sqlmodel import Session, select, desc

# DB 모델
from db.model.interview import Interview, UserInterview

# ✅ 유틸 함수 (발음 변환용)
from common.ko_util import korean_to_english_pronunciation

load_dotenv()


class WriteService:
    def __init__(self):
        print("🔧 WriteService 초기화 시작...")

        # 1. PaddleOCR 초기화
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

        # 2. LLM 초기화 (JSON 모드)
        try:
            openai_key = os.getenv("OPENAI_API_KEY")
            if not openai_key:
                print("⚠️ OPENAI_API_KEY가 없습니다.")
                self.llm = None
            else:
                self.llm = ChatOpenAI(
                    model="gpt-4o",
                    temperature=0,
                    api_key=openai_key,
                    model_kwargs={"response_format": {"type": "json_object"}},
                )
                print("✅ ChatOpenAI 초기화 성공")
        except Exception as e:
            print(f"❌ ChatOpenAI 초기화 실패: {e}")
            self.llm = None

        print("✅ WriteService 초기화 완료")

    # =========================================================
    # 1. OCR 및 파일 처리 (내부 헬퍼)
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

    async def _perform_ocr(self, file, mode="paddle"):
        """(내부용) 이미지에서 텍스트 추출"""
        content = await file.read()
        if mode == "paddle":
            text = self.run_paddle(content)
        else:
            text = self.run_naver(content, file.filename)
        return text

    # =========================================================
    # 2. 쓰기 문제 생성 (DB 조회 O, 비동기 병렬 처리)
    # =========================================================
    async def _process_single_question(
        self, user_int: UserInterview, interview: Interview
    ) -> Dict[str, Any]:
        """개별 질문 처리: 유틸 함수로 발음 생성, LLM으로 번역 생성"""
        kor_q = interview.kor if interview.kor else ""
        eng_q = interview.eng if interview.eng else ""
        eng_ans = user_int.answer if user_int.answer else ""

        # 1. 발음 생성 (ko_util 함수 사용)
        try:
            pronunciation = korean_to_english_pronunciation(kor_q)
        except Exception as e:
            print(f"⚠️ 발음 변환 실패: {e}")
            pronunciation = ""

        result_data = {
            "word_data": {"kor": kor_q, "eng": eng_q, "pronunciation": pronunciation},
            "answer": eng_ans,
            "answer_kor": "",
        }

        if not self.llm or not eng_ans:
            return result_data

        # 2. 번역 생성 (LLM 비동기 호출)
        try:
            prompt = f"""
            You are a Korean language tutor.
            Translate "User's Answer" into natural, polite Korean (Honorifics).
            
            Context: 
            - Question: "{kor_q}"
            - User's Answer (English): "{eng_ans}"
            
            Output JSON only: {{ "answer_kor": "..." }}
            """

            response = await self.llm.ainvoke(prompt)
            content = response.content.strip()

            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            llm_result = json.loads(content)
            result_data["answer_kor"] = llm_result.get("answer_kor", eng_ans)

        except Exception as e:
            print(f"⚠️ LLM 번역 실패 (ID: {user_int.id}): {e}")
            result_data["answer_kor"] = eng_ans

        return result_data

    async def get_writing_questions(
        self, session: Session, user_id: int
    ) -> Dict[str, Any]:
        """쓰기 문제 5개 생성 (병렬 처리)"""
        print(f"\n{'='*60}")
        print(f"📝 쓰기 문제 생성 요청 (User ID: {user_id})")

        try:
            # DB 쿼리
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

            # 병렬 처리 (asyncio.gather)
            tasks = [
                self._process_single_question(user_int, interview)
                for user_int, interview in results
            ]
            processed_questions = await asyncio.gather(*tasks)

            print(f"✅ 총 {len(processed_questions)}개 문제 생성 완료")
            return {"user_id": user_id, "question": processed_questions}

        except Exception as e:
            print(f"❌ 문제 생성 에러: {e}")
            return {"user_id": user_id, "question": []}

    # =========================================================
    # 3. 쓰기 평가 및 채점 (다중 파일 지원, 하이브리드 평가)
    # =========================================================
    async def _get_correction_feedback(self, target: str, wrong_input: str) -> str:
        """LLM 피드백 생성 (비동기)"""
        if not self.llm:
            return "오타가 있습니다."

        prompt = f"""
        You are a Korean handwriting teacher.
        Target: "{target}"
        Student wrote (OCR): "{wrong_input}"
        Briefly explain the mistake in Korean. Example: "'녕'을 '넝'으로 쓰셨네요."
        Output only the Korean feedback string.
        """
        try:
            res = await self.llm.ainvoke(prompt)
            return res.content.strip().replace('"', "")
        except:
            return "글자가 조금 틀렸습니다."

    async def _evaluate_single_image(self, target_text: str, file) -> Dict[str, Any]:
        """단일 이미지 평가 로직 (OCR -> 채점 -> 피드백)"""
        # 1. OCR
        user_input = await self._perform_ocr(file, mode="paddle")
        user_input = user_input.strip()

        # 방어 로직
        if not user_input:
            return {
                "display": {
                    "is_pass": False,
                    "message": "글자가 안 보여요. 다시 써주세요!",
                    "correction": "",
                },
                "record": {"score": 0, "target": target_text, "input": ""},
            }

        # 2. 점수 계산 (Python difflib)
        clean_target = (
            target_text.replace(" ", "").replace(".", "").replace("?", "").strip()
        )
        clean_user = (
            user_input.replace(" ", "").replace(".", "").replace("?", "").strip()
        )

        matcher = SequenceMatcher(None, clean_target, clean_user)
        score = int(matcher.ratio() * 100)

        # 3. 결과 분기 (Hybrid Strategy)
        display_message = ""
        is_pass = False
        correction_text = ""

        # 평가 기준: 90점(완벽), 60점(통과)
        if score >= 90:
            is_pass = True
            display_message = "완벽해요! 글씨가 정말 예쁘시네요. 🎉"
        elif score >= 60:
            is_pass = True
            display_message = "통과! (조금 더 또박또박 써볼까요?)"
            # LLM 호출 (비동기)
            correction_text = await self._get_correction_feedback(
                target_text, user_input
            )
        else:
            is_pass = False
            display_message = "글자가 많이 달라요. 다시 한번 써보세요."
            correction_text = f"인식된 글자: {user_input}"

        return {
            "display": {
                "is_pass": is_pass,  # [UI용] 성공/실패 효과음 트리거
                "message": display_message,  # [UI용] 말풍선 텍스트
                "correction": correction_text,  # [UI용] 틀린 부분 힌트
            },
            "record": {
                "score": score,  # [기록용] 최종 에이전트에게 전달될 점수
                "target": target_text,  # [기록용] 정답
                "input": user_input,  # [기록용] 사용자가 쓴 것
                "stage": "writing",
            },
        }

    async def evaluate_tracing(
        self, target_text: str, files: List
    ) -> List[Dict[str, Any]]:
        """
        [대량 채점] 여러 장의 이미지를 받아서 각각 채점 후 리스트로 반환
        """
        results = []
        for file in files:
            # 파일 포인터 초기화 (안전장치)
            await file.seek(0)
            result = await self._evaluate_single_image(target_text, file)
            results.append(result)

        return results
