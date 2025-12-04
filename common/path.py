from pathlib import Path

_PATH_FILE = Path(__file__).resolve()

# 프로젝트 루트
PROJECT_ROOT = _PATH_FILE.parent.parent

# 정적 자원(STATIC) 디렉토리
STATIC_DIR = PROJECT_ROOT / "static"

# 각 파일 디렉토리
AUDIOS_DIR = STATIC_DIR / "audios"
IMAGES_DIR = STATIC_DIR / "images" 
INPUT_DIR = STATIC_DIR / "input"
OUTPUT_DIR = STATIC_DIR / "output"

PROMPT_DIR = PROJECT_ROOT / "prompt"