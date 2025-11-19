import os
import logging.config

# 로깅 설정 딕셔너리
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False, # 기존 로거 비활성화 여부
    
    # 로그 포맷 정의
    "formatters": {
        "default": {
            "format": "%(asctime)s %(levelname)s %(name)s:%(lineno)d %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    
    # 로그 핸들러 정의 (어디로 보낼지)
    "handlers": {
        "console": {
            "class": "logging.StreamHandler", # 콘솔(터미널)로 출력
            "formatter": "default",
            "level": "DEBUG",
            "stream": "ext://sys.stdout", # 표준 출력 사용
        },
    },
    
    # 로거 정의
    "loggers": {
        # uvicorn 액세스 로그
        "uvicorn.access": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False, # 상위 로거로 전파 X
        },
        # uvicorn 에러 로그
        "uvicorn.error": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        # 애플리케이션 루트 로거
        "app": {
            "handlers": ["console"],
            "level": "INFO" if os.environ["APP_MODE"] == "1" else "DEBUG", # 개발 시 DEBUG, 운영 시 INFO
            "propagate": False,
        },
    },
    
    # 루트 로거 (모든 로거의 최상위)
    "root": {
        "handlers": ["console"],
        "level": "WARNING", # 기본 레벨은 WARNING
    },
}

def setup_logging():
    """ 로깅 설정 적용 """
    logging.config.dictConfig(LOGGING_CONFIG)