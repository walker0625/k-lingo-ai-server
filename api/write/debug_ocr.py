import sys
import os
import traceback

print(f"Python Executable: {sys.executable}")

print("\n[1] Numpy Check")
try:
    import numpy
    print(f"Numpy Version: {numpy.__version__}")
except ImportError as e:
    print(f"Numpy Load Failed: {e}")

print("\n[2] PaddleOCR Load Check")
try:
    # 라이브러리 충돌 방지 환경변수 설정
    os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
    
    from paddleocr import PaddleOCR
    # 기본 옵션으로 로딩 시도
    ocr = PaddleOCR(lang='korean', show_log=False, enable_mkldnn=False)
    print("\nSuccess! PaddleOCR loaded.")
except Exception:
    print("\nFailure! Traceback:")
    print("="*50)
    traceback.print_exc()
    print("="*50)