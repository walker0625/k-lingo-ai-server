import os, requests, json, time, io, numpy as np, ollama, random
from datetime import datetime
from PIL import Image
from paddleocr import PaddleOCR
from dotenv import load_dotenv

# 쓰기 문제 생성용 추가
from langchain_openai import ChatOpenAI
from sqlmodel import Session, select
from db.model.interview import Interview, UserInterview

load_dotenv()


class WriteService:
    def __init__(self):
        # PaddleOCR 로딩
        try:
            self.paddle = PaddleOCR(
                lang="korean",
                show_log=False,
                enable_mkldnn=False,
                use_gpu=False,
                use_angle_cls=True,
                ocr_version="PP-OCRv4",
            )
        except:
            self.paddle = None

        self.naver_url = os.getenv("NAVER_OCR_URL")
        self.naver_key = os.getenv("NAVER_SECRET_KEY")
        self.ollama_model = "hf.co/LGAI-EXAONE/EXAONE-4.0-1.2B-GGUF:Q4_K_M"
        
        # LLM 추가 (쓰기 문제 번역용)
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0)

    def run_naver(self, file_bytes, filename):
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
        except:
            return "Naver OCR 실패"

    def run_paddle(self, file_bytes):
        if not self.paddle:
            return "Paddle 모델 없음"
        img = np.array(Image.open(io.BytesIO(file_bytes)).convert("RGB"))
        # cls=False로 설정해야 더 빠르고 조용함
        result = self.paddle.ocr(img, cls=False)
        if not result or not result[0]:
            return ""
        return " ".join([line[1][0] for line in result[0]])

    def run_check(self, text, question):
        try:
            res = ollama.chat(
                model=self.ollama_model,
                messages=[
                    {
                        "role": "system",
                        "content": "질문에 예/아니오로 답하고 이유를 설명해.",
                    },
                    {"role": "user", "content": f"내용: {text}\n질문: {question}"},
                ],
            )
            return res["message"]["content"]
        except:
            return "AI 응답 실패"

    async def process_immigration(self, file, mode="naver"):
        content = await file.read()

        if mode == "paddle":
            text = self.run_paddle(content)
        else:
            text = self.run_naver(content, file.filename)

        questions = [
            "양식이 맞나요?",
            "이름과 서명이 있나요?",
            "한글이나 영어로 적혔나요?",
        ]
        validations = [
            {"question": q, "answer": self.run_check(text, q)} for q in questions
        ]

        return {"mode": mode, "text": text, "validations": validations}
    
    # ============================================
    # 쓰기 문제 생성 메서드 (NEW)
    # ============================================
    
    async def translate_to_korean(self, english_answer: str, korean_question: str) -> str:
        """영어 답변을 한글로 번역"""
        prompt = f"""
당신은 전문 번역가입니다.

질문: {korean_question}
영어 답변: {english_answer}

위 영어 답변을 자연스러운 한국어로 번역하세요.
정중한 표현(존댓말)을 사용하세요.

번역된 한국어만 출력하세요:
"""
        try:
            response = await self.llm.ainvoke(prompt)
            return response.content.strip()
        except Exception as e:
            print(f"[Translation Error] {e}")
            return "[번역 실패]"
    
    async def get_writing_questions(self, session: Session, user_id: int):
        """쓰기 문제 생성: 사용자가 답변한 질문 중 5개 랜덤 + 답변 번역"""
        
        try:
            # 1. 사용자가 답변한 데이터 조회
            statement = (
                select(
                    UserInterview.interview_id,
                    Interview.kor,
                    Interview.eng,
                    UserInterview.answer
                )
                .join(Interview, UserInterview.interview_id == Interview.id)
                .where(UserInterview.user_id == user_id)
            )
            results = session.exec(statement).all()
            
            if not results:
                return {
                    "status": "error",
                    "message": "사전 인터뷰 이력이 없습니다."
                }
            
            # 2. 랜덤 5개 선택
            selected = random.sample(list(results), min(5, len(results)))
            
            # 3. 영어 답변 → 한글 번역
            questions = []
            for row in selected:
                korean_answer = await self.translate_to_korean(
                    english_answer=row.answer,
                    korean_question=row.kor
                )
                
                questions.append({
                    "interview_id": row.interview_id,
                    "korean_question": row.kor,
                    "english_question": row.eng,
                    "expected_answer": korean_answer  # 예상 답변 (한글)
                })
            
            return {
                "status": "success",
                "user_id": user_id,
                "total_questions": len(questions),
                "questions": questions
            }
            
        except Exception as e:
            print(f"[Get Writing Questions Error] {e}")
            import traceback
            traceback.print_exc()
            return {
                "status": "error",
                "message": str(e)
            }