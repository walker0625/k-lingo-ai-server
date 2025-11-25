import os, requests, json, time, io, numpy as np, ollama
from datetime import datetime
from PIL import Image
from paddleocr import PaddleOCR
from dotenv import load_dotenv

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
