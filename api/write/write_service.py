import os
import json
import base64
import asyncio
import difflib
import cv2
import numpy as np
import redis.asyncio as redis
from datetime import datetime
from typing import List, Dict, Any, Tuple
from fastapi import UploadFile, HTTPException
from openai import AsyncOpenAI
from sqlalchemy.orm import Session
from paddleocr import PaddleOCR


class WriteService:
    def __init__(self):
        # 1. OpenAI 클라이언트 설정
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            print("⚠️ 경고: OPENAI_API_KEY가 설정되지 않았습니다.")

        self.client = AsyncOpenAI(api_key=self.api_key)

        # 2. Redis 설정 (.env 파일 내용 반영)
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = os.getenv("REDIS_PORT", "6379")

        # Redis 연결
        self.redis_url = f"redis://{redis_host}:{redis_port}"

        try:
            self.redis = redis.from_url(self.redis_url, decode_responses=True)
            print(f"✅ Redis Connected: {self.redis_url}")
        except Exception as e:
            print(f"❌ Redis Connection Failed: {e}")

        # 3. PaddleOCR 모델 로드
        print("Loading PaddleOCR Model (CPU Mode)...")
        self.ocr = PaddleOCR(
            use_angle_cls=True, lang="korean", use_gpu=False, show_log=False
        )

    async def get_writing_questions(
        self, session: Session, user_id: int
    ) -> List[Dict[str, Any]]:
        return []

    async def evaluate_tracing(
        self, username: str, target_texts: List[str], files: List[UploadFile]
    ) -> List[Dict[str, Any]]:
        """
        사용자가 쓴 글씨 이미지를 평가하고,
        Redis의 result 내부에 scores 리스트로 저장합니다.
        구조: { "result": { "scores": [{"score": n, "desc": "..."}] } }
        """

        # [입력 데이터 전처리] - 콤마로 구분된 텍스트 처리
        if len(target_texts) == 1 and len(files) > 1 and "," in target_texts[0]:
            print(f"DEBUG: 감지됨 - 합쳐진 텍스트를 분리합니다: {target_texts[0]}")
            target_texts = [t.strip() for t in target_texts[0].split(",")]

        results = []

        for target_text, file in zip(target_texts, files):
            try:
                content = await file.read()
                nparr = np.frombuffer(content, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                if img is None:
                    raise ValueError("이미지 파일을 읽을 수 없습니다.")

                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

                # 1. 점수 계산
                ocr_text, score = self._calculate_score_local(img_rgb, target_text)

                # 2. AI 피드백 생성
                base64_image = base64.b64encode(content).decode("utf-8")
                ai_feedback = await self._generate_feedback_with_gpt(
                    base64_image, target_text, ocr_text, score
                )

                # =========================================================
                # ✅ 3. Redis 데이터 업데이트 (구조 변경 적용)
                # 목표 구조: { "result": { "scores": [...] }, ... }
                # =========================================================
                current_history = []
                try:
                    redis_key = f"KLINGO-CURRENT:{username}"
                    raw_data = await self.redis.get(redis_key)

                    if raw_data:
                        try:
                            data = json.loads(raw_data)
                        except json.JSONDecodeError:
                            data = {}
                    else:
                        data = {}

                    # A. 'result' 키가 없거나 딕셔너리가 아니면 초기화
                    if "result" not in data or not isinstance(data["result"], dict):
                        data["result"] = {}

                    # B. 'result' 안에 'scores' 리스트 초기화
                    if "scores" not in data["result"]:
                        data["result"]["scores"] = []

                    # 만약 result['scores']가 리스트가 아니면 강제 초기화
                    if not isinstance(data["result"]["scores"], list):
                        data["result"]["scores"] = []

                    # C. [마이그레이션] 루트 레벨에 있는 'scores'가 있다면 안으로 이동
                    if "scores" in data and isinstance(data["scores"], list):
                        # 기존 루트 scores 데이터를 result/scores로 이동
                        data["result"]["scores"].extend(data["scores"])
                        # 이동 후 루트 키 삭제
                        del data["scores"]

                    # D. 새로운 평가 결과 객체 생성
                    score_value = int(score) if isinstance(score, (int, float)) else 0
                    correction_text = ai_feedback.get("correction", "")
                    score_obj = {"score": score_value, "desc": correction_text}

                    # E. 데이터 추가
                    data["result"]["scores"].append(score_obj)
                    data["updated_at"] = datetime.utcnow().isoformat()

                    # Redis 저장
                    await self.redis.set(
                        redis_key, json.dumps(data, ensure_ascii=False)
                    )

                    current_history = data["result"]["scores"]
                    print(
                        f"💰 [Redis] User '{username}' added score: {score_value}. Total: {len(current_history)} records."
                    )

                except Exception as redis_error:
                    print(f"⚠️ Redis Error: {redis_error}")
                    pass

                # 4. 결과 반환 구성
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
                            "message": "평가 중 오류가 발생했습니다.",
                            "correction": "다시 시도해 주세요.",
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

    def _calculate_score_local(
        self, img_array: np.ndarray, target_text: str
    ) -> Tuple[str, int]:
        """
        PaddleOCR + difflib.SequenceMatcher로 점수 계산
        """
        try:
            result = self.ocr.ocr(img_array, cls=True)
            ocr_text = ""
            if result and result[0]:
                for line in result[0]:
                    if line and len(line) > 1 and line[1]:
                        text_part = line[1][0]
                        ocr_text += text_part

            ocr_text_clean = ocr_text.replace(" ", "")
            target_clean = target_text.replace(" ", "")

            if not ocr_text_clean:
                return "", 0

            matcher = difflib.SequenceMatcher(None, target_clean, ocr_text_clean)
            score = int(matcher.ratio() * 100)
            return ocr_text, score

        except Exception as e:
            print(f"PaddleOCR Error: {e}")
            return "", 0

    async def _generate_feedback_with_gpt(
        self, base64_image: str, target: str, ocr_input: str, score: int
    ) -> Dict[str, str]:
        """
        GPT-4o를 사용하여 학습자에게 줄 피드백 생성
        """
        system_prompt = """
        당신은 한국어 글쓰기 선생님입니다.
        제공된 이미지와 계산된 점수를 바탕으로, 학생에게 줄 격려 메시지와 교정 내용을 JSON으로 작성하세요.

        [규칙]
        1. 점수({score}점)는 절대 변경하지 마세요.
        2. 점수가 70점 미만이면 구체적인 교정 사항(모양, 획순 등)을, 70점 이상이면 칭찬을 위주로 작성하세요.
        3. OCR이 읽은 글자({ocr_input})가 목표 글자({target})와 다르다면 그 부분을 짚어주세요.
        4. 모든 격려 메시지와 교정 내용은 반드시 영어(English)로 작성해야 합니다.
        5. 절대 응답에 이모티콘이 들어가서는 안됩니다.
        
        응답 포맷:
        {
            "message": "학생에게 건네는 부드러운 말투의 피드백",
            "correction": "글씨 모양, 크기, 획 등에 대한 구체적인 조언"
        }
        """

        user_content = f"""
        - 목표 단어: {target}
        - OCR 인식 결과: {ocr_input}
        - 계산된 점수: {score}점
        
        이 데이터를 바탕으로 피드백을 주세요.
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
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"GPT Error: {e}")
            return {
                "message": "잘 썼어요!" if score > 70 else "조금 더 연습해 볼까요?",
                "correction": "글자 모양을 목표 단어와 똑같이 써보세요.",
            }
