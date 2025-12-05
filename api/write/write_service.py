import os
import json
import base64
import asyncio
import difflib
import cv2
import numpy as np
from typing import List, Dict, Any, Tuple
from fastapi import UploadFile, HTTPException
from openai import AsyncOpenAI
from sqlalchemy.orm import Session
from paddleocr import PaddleOCR


class WriteService:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            print("⚠️ 경고: OPENAI_API_KEY가 설정되지 않았습니다.")

        self.client = AsyncOpenAI(api_key=self.api_key)

        print("Loading PaddleOCR Model (CPU Mode)...")
        # [수정] use_gpu=False 추가하여 CPU 모드 강제
        self.ocr = PaddleOCR(
            use_angle_cls=True, lang="korean", use_gpu=False, show_log=False
        )

    async def get_writing_questions(
        self, session: Session, user_id: int
    ) -> List[Dict[str, Any]]:
        return []

    async def evaluate_tracing(
        self, target_texts: List[str], files: List[UploadFile]
    ) -> List[Dict[str, Any]]:
        # [입력 데이터 전처리] Swagger/List 입력 오류 방지용 분리 로직
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

                # [수정] 인식률 향상을 위해 BGR -> RGB 변환
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

                # 1. Local 점수 계산 (RGB 이미지 사용)
                ocr_text, score = self._calculate_score_local(img_rgb, target_text)

                # 2. AI 피드백 생성
                base64_image = base64.b64encode(content).decode("utf-8")
                ai_feedback = await self._generate_feedback_with_gpt(
                    base64_image, target_text, ocr_text, score
                )

                # 3. 반환값 구성을 위한 변수 분리
                is_pass = score >= 70
                display_message = ai_feedback.get("message", "참 잘했어요!")
                correction_text = ai_feedback.get(
                    "correction", "조금 더 정확하게 써보세요."
                )
                user_input = ocr_text

                # 4. 결과 구성
                result = {
                    "display": {
                        "is_pass": is_pass,
                        "message": display_message,
                        "correction": correction_text,
                    },
                    "record": {
                        "score": score,
                        "target": target_text,
                        "input": user_input,
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
        [Local Logic] PaddleOCR + difflib.SequenceMatcher
        """
        try:
            # PaddleOCR 수행
            result = self.ocr.ocr(img_array, cls=True)

            ocr_text = ""
            # result 구조 안전하게 파싱
            if result and result[0]:
                for line in result[0]:
                    # line 구조: [[x,y], [text, confidence]]
                    if line and len(line) > 1 and line[1]:
                        text_part = line[1][0]
                        ocr_text += text_part

            # 공백 제거
            ocr_text = ocr_text.replace(" ", "")
            target_clean = target_text.replace(" ", "")

            # 인식된 텍스트가 없으면 0점
            if not ocr_text:
                print(f"DEBUG: OCR 인식 실패 (Empty Result) for Target: {target_clean}")
                return "", 0

            # 유사도 계산
            matcher = difflib.SequenceMatcher(None, target_clean, ocr_text)
            accuracy = matcher.ratio() * 100
            score = int(accuracy)

            print(f"DEBUG: Target={target_clean}, OCR={ocr_text}, Score={score}")
            return ocr_text, score

        except Exception as e:
            print(f"PaddleOCR Error: {e}")
            return "", 0

    async def _generate_feedback_with_gpt(
        self, base64_image: str, target: str, ocr_input: str, score: int
    ) -> Dict[str, str]:
        system_prompt = """
        당신은 한국어 글쓰기 선생님입니다.
        제공된 이미지와 계산된 점수를 바탕으로, 학생에게 줄 격려 메시지와 교정 내용을 JSON으로 작성하세요.

        [규칙]
        1. 점수({score}점)는 절대 변경하지 마세요.
        2. 점수가 70점 미만이면 구체적인 교정 사항(모양, 획순 등)을, 70점 이상이면 칭찬을 위주로 작성하세요.
        3. OCR이 읽은 글자({ocr_input})가 목표 글자({target})와 다르다면 그 부분을 짚어주세요.
        
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
