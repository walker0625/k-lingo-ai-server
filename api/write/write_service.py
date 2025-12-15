import os
import json
import base64
import asyncio
import difflib
import redis.asyncio as redis
from datetime import datetime
from typing import List, Dict, Any
from fastapi import UploadFile
from openai import AsyncOpenAI
from sqlalchemy.orm import Session


class WriteService:
    # 한글 자소 분리를 위한 상수
    CHO_LIST = [
        "ㄱ",
        "ㄲ",
        "ㄴ",
        "ㄷ",
        "ㄸ",
        "ㄹ",
        "ㅁ",
        "ㅂ",
        "ㅃ",
        "ㅅ",
        "ㅆ",
        "ㅇ",
        "ㅈ",
        "ㅉ",
        "ㅊ",
        "ㅋ",
        "ㅌ",
        "ㅍ",
        "ㅎ",
    ]
    JUNG_LIST = [
        "ㅏ",
        "ㅐ",
        "ㅑ",
        "ㅒ",
        "ㅓ",
        "ㅔ",
        "ㅕ",
        "ㅖ",
        "ㅗ",
        "ㅘ",
        "ㅙ",
        "ㅚ",
        "ㅛ",
        "ㅜ",
        "ㅝ",
        "ㅞ",
        "ㅟ",
        "ㅠ",
        "ㅡ",
        "ㅢ",
        "ㅣ",
    ]
    JONG_LIST = [
        "",
        "ㄱ",
        "ㄲ",
        "ㄳ",
        "ㄴ",
        "ㄵ",
        "ㄶ",
        "ㄷ",
        "ㄹ",
        "ㄺ",
        "ㄻ",
        "ㄼ",
        "ㄽ",
        "ㄾ",
        "ㄿ",
        "ㅀ",
        "ㅁ",
        "ㅂ",
        "ㅄ",
        "ㅅ",
        "ㅆ",
        "ㅇ",
        "ㅈ",
        "ㅊ",
        "ㅋ",
        "ㅌ",
        "ㅍ",
        "ㅎ",
    ]

    def __init__(self):
        # 1. OpenAI 클라이언트 설정
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            print("⚠️ 경고: OPENAI_API_KEY가 설정되지 않았습니다.")

        self.client = AsyncOpenAI(api_key=self.api_key)

        # 2. Redis 설정
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = os.getenv("REDIS_PORT", "6379")
        self.redis_url = f"redis://{redis_host}:{redis_port}"

        try:
            self.redis = redis.from_url(self.redis_url, decode_responses=True)
            print(f"✅ Redis Connected: {self.redis_url}")
        except Exception as e:
            print(f"❌ Redis Connection Failed: {e}")

    async def get_writing_questions(
        self, session: Session, user_id: int
    ) -> List[Dict[str, Any]]:
        return []

    async def evaluate_tracing(
        self, username: str, target_texts: List[str], files: List[UploadFile]
    ) -> List[Dict[str, Any]]:

        # [입력 데이터 전처리]
        if len(target_texts) == 1 and len(files) > 1 and "," in target_texts[0]:
            target_texts = [t.strip() for t in target_texts[0].split(",")]

        results = []

        for target_text, file in zip(target_texts, files):
            try:
                content = await file.read()
                base64_image = base64.b64encode(content).decode("utf-8")

                # 1. OpenAI로 OCR 수행
                ocr_text = await self._ocr_with_gpt(base64_image)
                print(f"DEBUG: OpenAI OCR Result: {ocr_text} (Target: {target_text})")

                # 2. [수정됨] 자소 분리 기반 점수 계산
                score = self._calculate_score_jamo(target_text, ocr_text)

                # 3. AI 피드백 생성
                ai_feedback = await self._generate_feedback_with_gpt(
                    base64_image, target_text, ocr_text, score
                )

                # 4. Redis 데이터 업데이트
                await self._update_redis_history(username, score, ai_feedback)

                # 5. 결과 반환 구성
                is_pass = score >= 70
                result = {
                    "display": {
                        "is_pass": is_pass,
                        "message": ai_feedback.get("message", "참 잘했어요!"),
                        "correction": ai_feedback.get(
                            "correction", "조금 더 정확하게 써보세요."
                        ),
                    },
                    "record": {
                        "score": score,
                        "target": target_text,
                        "input": ocr_text,
                        "stage": "writing",
                    },
                }
                results.append(result)

            except Exception as e:
                print(f"❌ 평가 중 에러: {e}")
                results.append(
                    {
                        "display": {
                            "is_pass": False,
                            "message": "오류가 발생했습니다.",
                            "correction": "",
                        },
                        "record": {
                            "score": 0,
                            "target": target_text,
                            "input": "",
                            "stage": "writing",
                        },
                    }
                )
            finally:
                await file.seek(0)

        return results

    async def _ocr_with_gpt(self, base64_image: str) -> str:
        """OpenAI Vision을 사용하여 이미지 내의 한글 텍스트 추출"""
        system_prompt = """
        You are an expert Korean OCR engine. 
        Read the handwritten Korean text in the image. 
        Output ONLY the text found. 
        Ignore spaces and minor artifacts.
        If the text is messy but recognizable, try to correct it to the nearest meaningful word.
        If no text is found, return empty string.
        """

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Extract the handwritten text."},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                },
                            },
                        ],
                    },
                ],
                temperature=0.0,
            )
            content = response.choices[0].message.content
            return content.strip() if content else ""
        except Exception as e:
            print(f"GPT OCR Error: {e}")
            return ""

    def _decompose_hangul(self, text: str) -> str:
        """
        [신규] 한글 문자열을 초성/중성/종성으로 분해하여 반환합니다.
        예: '감사' -> 'ㄱㅏㅁㅅㅏ'
        """
        result = ""
        for char in text:
            if "가" <= char <= "힣":
                char_code = ord(char) - 0xAC00
                cho = char_code // 588
                jung = (char_code % 588) // 28
                jong = char_code % 28

                result += self.CHO_LIST[cho]
                result += self.JUNG_LIST[jung]
                if jong > 0:
                    result += self.JONG_LIST[jong]
            else:
                result += char
        return result

    def _calculate_score_jamo(self, target_text: str, ocr_text: str) -> int:
        """
        [수정됨] 자소 단위로 분해하여 유사도를 계산합니다.
        훨씬 더 관대한 채점이 가능합니다.
        """
        # 공백 제거
        target_clean = target_text.replace(" ", "").replace("\n", "")
        ocr_clean = ocr_text.replace(" ", "").replace("\n", "")

        if not ocr_clean:
            return 0

        # 자소 분해 (예: '글' -> 'ㄱㅡㄹ')
        target_jamo = self._decompose_hangul(target_clean)
        ocr_jamo = self._decompose_hangul(ocr_clean)

        # 자소 단위 비교
        matcher = difflib.SequenceMatcher(None, target_jamo, ocr_jamo)
        score = int(matcher.ratio() * 100)

        print(
            f"DEBUG: Score Calculation -> Target: {target_jamo}, Input: {ocr_jamo}, Score: {score}"
        )
        return score

    async def _generate_feedback_with_gpt(
        self, base64_image: str, target: str, ocr_input: str, score: int
    ) -> Dict[str, str]:
        """GPT-4o를 사용하여 피드백 생성"""
        system_prompt = """
        당신은 친절한 한국어 선생님입니다.
        학생의 필기 이미지와 인식된 텍스트, 점수를 보고 피드백을 JSON으로 주세요.
        
        [가이드]
        1. 점수가 90점 이상이면 칭찬 위주.
        2. 점수가 낮으면 어떤 글자가 틀렸는지, 획을 어떻게 그어야 하는지 구체적으로 조언.
        3. 반환 형식은 반드시 JSON이어야 함.
        """

        user_content = f"목표: {target}, 인식됨: {ocr_input}, 점수: {score}"

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_content},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                },
                            },
                        ],
                    },
                ],
                response_format={"type": "json_object"},
                temperature=0.7,
            )
            return json.loads(response.choices[0].message.content)
        except Exception:
            return {
                "message": "참 잘했어요!" if score > 70 else "조금 더 연습해 볼까요?",
                "correction": "글자 모양을 목표 단어와 똑같이 써보세요.",
            }

    async def _update_redis_history(self, username: str, score: int, feedback: dict):
        """Redis 업데이트 로직 분리"""
        try:
            redis_key = f"KLINGO-CURRENT:{username}"
            raw_data = await self.redis.get(redis_key)
            data = json.loads(raw_data) if raw_data else {}

            if "result" not in data or not isinstance(data["result"], dict):
                data["result"] = {}
            if "scores" not in data["result"]:
                data["result"]["scores"] = []

            # 마이그레이션 로직 포함
            if "scores" in data and isinstance(data["scores"], list):
                data["result"]["scores"].extend(data["scores"])
                del data["scores"]

            data["result"]["scores"].append(
                {"score": score, "desc": feedback.get("correction", "")}
            )
            data["updated_at"] = datetime.utcnow().isoformat()

            await self.redis.set(redis_key, json.dumps(data, ensure_ascii=False))
        except Exception as e:
            print(f"⚠️ Redis Update Error: {e}")
