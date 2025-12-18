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
            print("경고: OPENAI_API_KEY가 설정되지 않았습니다.")

        self.client = AsyncOpenAI(api_key=self.api_key)

        # 2. Redis 설정
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = os.getenv("REDIS_PORT", "6379")
        self.redis_url = f"redis://{redis_host}:{redis_port}"

        try:
            self.redis = redis.from_url(self.redis_url, decode_responses=True)
            print(f"Redis Connected: {self.redis_url}")
        except Exception as e:
            print(f"Redis Connection Failed: {e}")

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

                # 2. 자소 분리 기반 점수 계산 (짧은 단어용 조정)
                score = self._calculate_score_jamo_strict(target_text, ocr_text)

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
                        "message": ai_feedback.get("message", "Great job!"),
                        "correction": ai_feedback.get(
                            "correction", "Try writing more accurately."
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
                print(f"평가 중 에러: {e}")
                results.append(
                    {
                        "display": {
                            "is_pass": False,
                            "message": "An error occurred.",
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
        한글 문자열을 초성/중성/종성으로 분해하여 반환합니다.
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

    def _calculate_score_jamo_strict(self, target_text: str, ocr_text: str) -> int:
        """
        [짧은 단어용 엄격한 채점]
        단어가 짧기 때문에 한 글자 오류도 큰 감점으로 처리
        """
        # 공백 제거
        target_clean = target_text.replace(" ", "").replace("\n", "")
        ocr_clean = ocr_text.replace(" ", "").replace("\n", "")

        if not ocr_clean:
            return 0

        # 완전 일치 시 100점
        if target_clean == ocr_clean:
            return 100

        # 자소 분해 (예: '글' -> 'ㄱㅡㄹ')
        target_jamo = self._decompose_hangul(target_clean)
        ocr_jamo = self._decompose_hangul(ocr_clean)

        # 자소 단위 비교
        matcher = difflib.SequenceMatcher(None, target_jamo, ocr_jamo)
        similarity = matcher.ratio()

        # 짧은 단어는 엄격하게 채점 (90% 미만 유사도는 대폭 감점)
        if similarity >= 0.95:
            score = 95
        elif similarity >= 0.90:
            score = 85
        elif similarity >= 0.80:
            score = 70
        elif similarity >= 0.70:
            score = 55
        elif similarity >= 0.60:
            score = 40
        else:
            score = int(similarity * 50)  # 60% 미만은 더 낮게

        print(
            f"DEBUG: Strict Score -> Target: '{target_clean}' ({target_jamo}), "
            f"Input: '{ocr_clean}' ({ocr_jamo}), Similarity: {similarity:.2%}, Score: {score}"
        )
        return score

    async def _generate_feedback_with_gpt(
        self, base64_image: str, target: str, ocr_input: str, score: int
    ) -> Dict[str, str]:
        """GPT-4o를 사용하여 피드백 생성 (영어 출력, 짧은 단어용)"""
        system_prompt = """
        You are a kind but precise Korean handwriting teacher.
        Students are practicing SHORT Korean words (5-7 characters max).
        Look at the handwriting image and provide specific feedback in JSON format.
        
        [Feedback Principles for Short Words]
        1. Score 95-100: Perfect! Excellent handwriting
        2. Score 85-94: Very good, minor stroke improvements needed
        3. Score 70-84: Good attempt, point out 1-2 specific character errors
        4. Score 55-69: Several errors, identify which characters need practice
        5. Score below 55: Most characters incorrect, suggest fundamental practice
        
        [JSON Format]
        {
            "message": "Encouraging message (1 sentence)",
            "correction": "Specific correction for wrong characters"
        }
        
        **CRITICAL: All feedback must be in English.**
        Since words are short, even one wrong character is significant.
        """

        user_content = f"""
        [Grading Result]
        - Target Word: {target} (SHORT word, 5-7 chars)
        - Student Wrote: {ocr_input}
        - Score: {score} points
        
        Analyze which specific characters are wrong and provide precise feedback.
        """

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

            result = json.loads(response.choices[0].message.content)
            print(f"GPT Feedback Generated: {result}")
            return result

        except Exception as e:
            print(f"GPT Feedback Failed, Using Fallback: {e}")
            return self._generate_fallback_feedback(target, ocr_input, score)

    def _generate_fallback_feedback(
        self, target: str, ocr_input: str, score: int
    ) -> Dict[str, str]:
        """
        [영어 버전 - 짧은 단어용]
        """
        target_clean = target.replace(" ", "")
        ocr_clean = ocr_input.replace(" ", "")

        # 글자 단위로 비교
        wrong_chars = []
        for i, (t_char, o_char) in enumerate(zip(target_clean, ocr_clean)):
            if t_char != o_char:
                wrong_chars.append(f"'{t_char}'")

        # 점수별 피드백
        if score >= 95:
            return {
                "message": "Perfect! Excellent handwriting!",
                "correction": "Keep practicing to maintain this level.",
            }
        elif score >= 85:
            correction = (
                f"Almost perfect! Check {wrong_chars[0]} stroke order."
                if wrong_chars
                else "Minor improvements in stroke consistency."
            )
            return {"message": "Very good work!", "correction": correction}
        elif score >= 70:
            correction = (
                f"Practice {', '.join(wrong_chars[:2])} more carefully."
                if wrong_chars
                else f"Focus on writing '{target_clean}' with clearer strokes."
            )
            return {"message": "Good attempt!", "correction": correction}
        elif score >= 55:
            correction = (
                f"In '{target_clean}', characters {', '.join(wrong_chars[:3])} need correction."
                if wrong_chars
                else f"Review how to write '{target_clean}' step by step."
            )
            return {"message": "More practice needed.", "correction": correction}
        else:
            return {
                "message": f"Let's practice '{target_clean}' again slowly.",
                "correction": f"Target is '{target_clean}' but recognition shows '{ocr_clean}'. Practice each character separately: {', '.join(list(target_clean))}.",
            }

    async def _update_redis_history(self, username: str, score: int, feedback: dict):
        """Redis 업데이트"""
        try:
            redis_key = f"KLINGO-CURRENT:{username}"
            raw_data = await self.redis.get(redis_key)
            data = json.loads(raw_data) if raw_data else {}

            if "result" not in data or not isinstance(data["result"], dict):
                data["result"] = {}
            if "scores" not in data["result"]:
                data["result"]["scores"] = []

            # 마이그레이션
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
