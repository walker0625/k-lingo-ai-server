import logging
from paddleocr import PaddleOCR
from PIL import Image
import io
from fastapi import UploadFile
import numpy as np
import ollama

logger = logging.getLogger(__name__)


class EduService:
    def __init__(self):
        try:
            logger.info("PaddleOCR 모델 로딩 중...")
            self.ocr = PaddleOCR(
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                lang='korean'
            )
            logger.info("PaddleOCR 모델 로딩 완료")
            
            self.ollama_model = "hf.co/LGAI-EXAONE/EXAONE-4.0-1.2B-GGUF:Q4_K_M"
            
        except Exception as e:
            logger.error(f"모델 로딩 실패: {str(e)}")
            self.ocr = None

    def process_ocr(self, image: Image) -> str:
        """OCR 처리"""
        if not self.ocr:
            raise Exception("OCR 모델이 로드되지 않았습니다")

        image_np = np.array(image)
        result = self.ocr.predict(input=image_np)
        
        logger.info(f"Result type: {type(result)}")
        logger.info(f"Result length: {len(result) if result else 0}")
        
        if not result or len(result) == 0:
            return ""
        
        # 각 결과 객체 확인
        texts = []
        for idx, res in enumerate(result):
            logger.info(f"Result {idx} type: {type(res)}")
            logger.info(f"Result {idx} is dict: {isinstance(res, dict)}")
            
            # 딕셔너리인 경우 직접 접근
            if isinstance(res, dict):
                logger.info(f"Dict keys: {res.keys()}")
                logger.info(f"Dict content: {res}")
                
                # OCR 결과 추출
                if 'rec_texts' in res:
                    for text in res['rec_texts']:
                        texts.append(text)
                elif 'text' in res:
                    texts.append(res['text'])
            # 객체인 경우
            else:
                # 모든 속성 출력
                logger.info(f"Object attributes: {[attr for attr in dir(res) if not attr.startswith('_')]}")
                
                # print() 메서드로 내용 확인
                if hasattr(res, 'print'):
                    logger.info("Calling res.print():")
                    res.print()
        
        extracted_text = "\n".join(texts)
        logger.info(f"최종 추출된 텍스트: {extracted_text}")
        return extracted_text

    def evaluate_with_ollama(self, ocr_text: str, question: str) -> str:
        """Ollama로 평가"""
        try:
            response = ollama.chat(
                model=self.ollama_model,
                messages=[
                    {
                        'role': 'system',
                        'content': '너는 입국 심사서 검증 전문가야. 주어진 텍스트를 보고 질문에 "예" 또는 "아니오"로 답하고 간단한 이유를 한 문장으로 설명해.'
                    },
                    {
                        'role': 'user',
                        'content': f"텍스트:\n{ocr_text}\n\n질문: {question}"
                    }
                ]
            )
            return response['message']['content']
        except Exception as e:
            logger.error(f"Ollama 평가 중 오류: {e}")
            return f"평가 오류: {str(e)}"

    async def extract_text_from_image(self, file: UploadFile):
        """이미지에서 텍스트 추출"""
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")

        ocr_result = self.process_ocr(image)
        
        return {"success": True, "extracted_text": ocr_result}

    async def validate_immigration_form(self, file: UploadFile) -> dict:
        """입국 심사서 검증"""
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")

        ocr_text = self.process_ocr(image)

        questions = [
            "이 입국 심사서가 올바르게 작성되었나요?",
            "필수 필드(성명, 국적, 여권번호, 생년월일)가 모두 채워져 있나요?",
            "한글로 명확하게 작성되어 있나요?",
        ]

        validations = []
        for question in questions:
            answer = self.evaluate_with_ollama(ocr_text, question)
            validations.append({"question": question, "answer": answer})

        return {
            "success": True,
            "extracted_text": ocr_text,
            "validations": validations
        }